from datetime import datetime
from inspect import isfunction
from unittest import mock

import pytest
from ddeutil.core import getdot
from ddeutil.workflow import Workflow
from ddeutil.workflow.conf import Config
from ddeutil.workflow.exceptions import StageException
from ddeutil.workflow.result import Result
from ddeutil.workflow.stages import Stage

from .utils import dump_yaml_context


def test_stage_exec_bash():
    workflow: Workflow = Workflow.from_conf(name="wf-run-common")
    stage: Stage = workflow.job("bash-run").stage("echo")
    rs: Result = stage.handler_execute({})
    assert {
        "return_code": 0,
        "stdout": "Hello World\nVariable Foo",
        "stderr": None,
    } == rs.context

    make_rs: Result = Result()
    rs: Result = stage.handler_execute({}, result=make_rs)
    assert {
        "return_code": 0,
        "stdout": "Hello World\nVariable Foo",
        "stderr": None,
    } == make_rs.context

    # NOTE: Make sure that the result that pass to the handler execution method
    #   is the same object of its return.
    assert make_rs is rs


def test_stage_exec_bash_env():
    workflow: Workflow = Workflow.from_conf(name="wf-run-common")
    stage: Stage = workflow.job("bash-run-env").stage("echo-env")
    rs: Result = stage.handler_execute({})
    assert {
        "return_code": 0,
        "stdout": "Hello World\nVariable Foo\nENV Bar",
        "stderr": None,
    } == rs.context


def test_stage_exec_bash_env_raise():
    workflow: Workflow = Workflow.from_conf(name="wf-run-common")
    stage: Stage = workflow.job("bash-run-env").stage("raise-error")

    # NOTE: Raise error from bash that force exit 1.
    with pytest.raises(StageException):
        stage.handler_execute({})


def test_stage_exec_call(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_call_return_type.yml",
        data="""
        tmp-wf-call-return-type:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Return type not valid"
                  id: valid-type
                  uses: tasks/return-type-not-valid@raise
                - name: "Necessary argument do not pass"
                  id: args-necessary
                  uses: tasks/mssql-proc@odbc
                  with:
                    params:
                      run_mode: "T"
                      run_date: 2024-08-01
                      source: src
                      target: tgt
                - name: "Call value not valid"
                  id: call-not-valid
                  uses: tasks-foo-bar
                - name: "Call does not register"
                  id: call-not-register
                  uses: tasks/abc@foo
            second-job:
              stages:
                - name: "Extract & Load Local System"
                  id: extract-load
                  uses: tasks/el-csv-to-parquet@polars-dir
                  with:
                    source: src
                    sink: sink
                - name: "Extract & Load Local System"
                  id: async-extract-load
                  uses: tasks/async-el-csv-to-parquet@polars-dir
                  with:
                    source: src
                    sink: sink
                - name: "Return with Pydantic Model"
                  id: return-model
                  uses: tasks/gen-type@demo
                  with:
                    args1: foo
                    args2: conf/path
                    args3:
                      name: test
                      data:
                        input: hello
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-call-return-type")

        stage: Stage = workflow.job("second-job").stage("extract-load")
        rs: Result = stage.handler_execute({})
        assert 0 == rs.status
        assert {"records": 1} == rs.context

        stage: Stage = workflow.job("second-job").stage("async-extract-load")
        rs: Result = stage.handler_execute({})
        assert rs.status == 0
        assert rs.context == {"records": 1}

        # NOTE: Raise because invalid return type.
        with pytest.raises(StageException):
            stage: Stage = workflow.job("first-job").stage("valid-type")
            stage.handler_execute({})

        # NOTE: Raise because necessary args do not pass.
        with pytest.raises(StageException):
            stage: Stage = workflow.job("first-job").stage("args-necessary")
            stage.handler_execute({})

        # NOTE: Raise because call does not valid.
        with pytest.raises(StageException):
            stage: Stage = workflow.job("first-job").stage("call-not-valid")
            stage.handler_execute({})

        # NOTE: Raise because call does not register.
        with pytest.raises(StageException):
            stage: Stage = workflow.job("first-job").stage("call-not-register")
            stage.handler_execute({})

        stage: Stage = workflow.job("second-job").stage("return-model")
        rs: Result = stage.handler_execute({})
        assert rs.status == 0
        assert rs.context == {"name": "foo", "data": {"key": "value"}}


@mock.patch.object(Config, "stage_raise_error", True)
def test_stage_exec_py_raise():
    workflow: Workflow = Workflow.from_conf(name="wf-run-common")
    stage: Stage = workflow.job("raise-run").stage(stage_id="raise-error")
    with pytest.raises(StageException):
        stage.handler_execute(params={"x": "Foo"})


@mock.patch.object(Config, "stage_raise_error", False)
def test_stage_exec_py_not_raise():
    workflow: Workflow = Workflow.from_conf(name="wf-run-common")
    stage: Stage = workflow.job("raise-run").stage(stage_id="raise-error")

    rs = stage.handler_execute(params={"x": "Foo"})

    assert rs.status == 1

    # NOTE:
    #   Context that return from error will be:
    #   {
    #       'error': ValueError("Testing ... PyStage!!!"),
    #       'error_message': "ValueError: Testing ... PyStage!!!",
    #   }
    assert isinstance(rs.context["errors"]["class"], ValueError)
    assert rs.context == {
        "errors": {
            "class": rs.context["errors"]["class"],
            "name": "ValueError",
            "message": "Testing raise error inside PyStage!!!",
        }
    }

    rs_out = stage.set_outputs(rs.context, {})
    assert rs_out == {
        "stages": {
            "raise-error": {
                "outputs": {},
                "errors": {
                    "class": getdot("stages.raise-error.errors.class", rs_out),
                    "name": "ValueError",
                    "message": "Testing raise error inside PyStage!!!",
                },
            },
        },
    }


def test_stage_exec_py_with_vars():
    workflow: Workflow = Workflow.from_conf(name="wf-run-common")
    stage: Stage = workflow.job("demo-run").stage(stage_id="run-var")
    assert stage.id == "run-var"

    params = {
        "params": {"name": "Author"},
        "stages": {"hello-world": {"outputs": {"x": "Foo"}}},
    }
    rs_out = stage.set_outputs(
        stage.handler_execute(params=params).context, to=params
    )
    assert {
        "params": {"name": "Author"},
        "stages": {
            "hello-world": {"outputs": {"x": "Foo"}},
            "run-var": {"outputs": {"x": 1}},
        },
    } == rs_out


def test_stage_exec_py_func():
    workflow: Workflow = Workflow.from_conf(name="wf-run-python")
    stage: Stage = workflow.job("second-job").stage(stage_id="create-func")
    rs = stage.set_outputs(stage.handler_execute(params={}).context, to={})
    assert ("var_inside", "echo") == tuple(
        rs["stages"]["create-func"]["outputs"].keys()
    )
    assert isfunction(rs["stages"]["create-func"]["outputs"]["echo"])


@mock.patch.object(Config, "stage_raise_error", False)
def test_stage_exec_py_result(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_py_result.yml",
        data="""
        tmp-wf-py-result:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Start run python with result argument"
                  id: py-result-stage
                  run: |
                    result.trace.info("Log from result object inside PyStage!!!")
                - name: "Raise error"
                  id: py-raise
                  run: |
                    raise ValueError("test raise error")
        """,
    ):
        workflow: Workflow = Workflow.from_conf(name="tmp-wf-py-result")
        stage: Stage = workflow.job("first-job").stage(
            stage_id="py-result-stage"
        )
        rs: dict = stage.handler_execute(params={}, to={})
        assert rs == {"stages": {"py-result-stage": {"outputs": {}}}}

        stage: Stage = workflow.job("first-job").stage(stage_id="py-raise")
        rs: dict = stage.handler_execute(params={}, to={})
        assert rs == {
            "stages": {
                "py-raise": {
                    "outputs": {},
                    "errors": {
                        "class": rs["stages"]["py-raise"]["errors"]["class"],
                        "name": "ValueError",
                        "message": "test raise error",
                    },
                },
            },
        }


def test_stage_exec_py_create_object():
    workflow: Workflow = Workflow.from_conf(name="wf-run-python-filter")
    stage: Stage = workflow.job("create-job").stage(stage_id="create-stage")
    rs = stage.set_outputs(stage.handler_execute(params={}).context, to={})
    assert len(rs["stages"]["create-stage"]["outputs"]) == 1


def test_stage_exec_trigger():
    workflow = Workflow.from_conf(name="wf-trigger", extras={})
    stage: Stage = workflow.job("trigger-job").stage(stage_id="trigger-stage")
    rs: Result = stage.handler_execute(params={})
    assert all(k in ("params", "jobs") for k in rs.context.keys())
    assert {
        "author-run": "Trigger Runner",
        "run-date": datetime(2024, 8, 1),
    } == rs.context["params"]


def test_stage_exec_foreach(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_foreach.yml",
        data="""
        tmp-wf-foreach:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Start run for-each stage"
                  id: foreach-stage
                  foreach: [1, 2, 3, 4]
                  stages:
                    - name: "Echo stage"
                      echo: |
                        Start run with item ${{ item }}
                    - name: "Final Echo"
                      if: ${{ item }} == 4
                      echo: |
                        Final run
                - name: "Foreach values type not valid"
                  id: foreach-raise
                  foreach: ${{ values.items }}
                  stages:
                    - name: "Echo stage"
                      echo: |
                        Start run with item ${{ item }}
                    - name: "Final Echo"
                      if: ${{ item }} == 4
                      echo: |
                        Final run
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-foreach")
        stage: Stage = workflow.job("first-job").stage("foreach-stage")
        rs = stage.set_outputs(stage.handler_execute({}).context, to={})
        assert rs == {
            "stages": {
                "foreach-stage": {
                    "outputs": {
                        "items": [1, 2, 3, 4],
                        "foreach": {
                            1: {
                                "item": 1,
                                "stages": {
                                    "2709471980": {"outputs": {}},
                                    "9263488742": {"outputs": {}},
                                },
                            },
                            2: {
                                "item": 2,
                                "stages": {
                                    "2709471980": {"outputs": {}},
                                    "9263488742": {"outputs": {}},
                                },
                            },
                            3: {
                                "item": 3,
                                "stages": {
                                    "2709471980": {"outputs": {}},
                                    "9263488742": {"outputs": {}},
                                },
                            },
                            4: {
                                "item": 4,
                                "stages": {
                                    "2709471980": {"outputs": {}},
                                    "9263488742": {"outputs": {}},
                                },
                            },
                        },
                    },
                },
            },
        }

        # NOTE: Raise because type of foreach does not match with list of item.
        stage: Stage = workflow.job("first-job").stage("foreach-raise")
        with pytest.raises(StageException):
            stage.handler_execute({"values": {"items": "test"}})


def test_stage_exec_foreach_concurrent(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_foreach.yml",
        data="""
        tmp-wf-foreach:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Start run for-each stage"
                  id: foreach-stage
                  foreach: [1, 2, 3, 4]
                  concurrent: 3
                  stages:
                    - name: "Echo stage"
                      echo: |
                        Start run with item ${{ item }}
                    - name: "Final Echo"
                      if: ${{ item }} == 4
                      echo: |
                        Final run
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-foreach")
        stage: Stage = workflow.job("first-job").stage("foreach-stage")
        rs = stage.set_outputs(stage.handler_execute({}).context, to={})
        assert rs == {
            "stages": {
                "foreach-stage": {
                    "outputs": {
                        "items": [1, 2, 3, 4],
                        "foreach": {
                            1: {
                                "item": 1,
                                "stages": {
                                    "2709471980": {"outputs": {}},
                                    "9263488742": {"outputs": {}},
                                },
                            },
                            2: {
                                "item": 2,
                                "stages": {
                                    "2709471980": {"outputs": {}},
                                    "9263488742": {"outputs": {}},
                                },
                            },
                            3: {
                                "item": 3,
                                "stages": {
                                    "2709471980": {"outputs": {}},
                                    "9263488742": {"outputs": {}},
                                },
                            },
                            4: {
                                "item": 4,
                                "stages": {
                                    "2709471980": {"outputs": {}},
                                    "9263488742": {"outputs": {}},
                                },
                            },
                        },
                    },
                },
            },
        }


def test_stage_exec_foreach_with_trigger(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_foreach_with_trigger.yml",
        data="""
        tmp-wf-foreach-trigger-task:
          type: Workflow
          params:
            item: int
          jobs:
            first-job:
              stages:
                - name: "Echo"
                  id: hello
                  echo: "Run trigger with item: ${{ params.item }}"

        tmp-wf-foreach-trigger:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Start run for-each stage"
                  id: foreach-stage
                  foreach: [1, 2]
                  stages:
                    - name: "Stage trigger"
                      trigger: tmp-wf-foreach-trigger-task
                      params:
                        item: ${{ item }}
        """,
    ):
        workflow = Workflow.from_conf(
            name="tmp-wf-foreach-trigger",
            extras={"test": "demo"},
        )
        stage: Stage = workflow.job("first-job").stage("foreach-stage")
        rs = stage.set_outputs(stage.handler_execute({}).context, to={})
        assert rs == {
            "stages": {
                "foreach-stage": {
                    "outputs": {
                        "items": [1, 2],
                        "foreach": {
                            1: {
                                "item": 1,
                                "stages": {
                                    "8713259197": {
                                        "outputs": {
                                            "params": {"item": 1},
                                            "jobs": {
                                                "first-job": {
                                                    "stages": {
                                                        "hello": {"outputs": {}}
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                            2: {
                                "item": 2,
                                "stages": {
                                    "8713259197": {
                                        "outputs": {
                                            "params": {"item": 2},
                                            "jobs": {
                                                "first-job": {
                                                    "stages": {
                                                        "hello": {"outputs": {}}
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        }


def test_stage_exec_parallel(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_parallel.yml",
        data="""
        tmp-wf-parallel:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Start run parallel stage"
                  id: parallel-stage
                  parallel:
                    branch01:
                      - name: "Echo branch01 stage"
                        echo: |
                          Start run with branch 1
                        sleep: 5
                    branch02:
                      - name: "Echo branch02 stage"
                        echo: |
                          Start run with branch 2
                        sleep: 1
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-parallel")

        stage: Stage = workflow.job("first-job").stage("parallel-stage")
        rs = stage.set_outputs(stage.handler_execute({}).context, to={})
        assert rs == {
            "stages": {
                "parallel-stage": {
                    "outputs": {
                        "parallel": {
                            "branch02": {
                                "stages": {"4967824305": {"outputs": {}}},
                            },
                            "branch01": {
                                "stages": {"0573477600": {"outputs": {}}},
                            },
                        },
                    },
                },
            },
        }


def test_stage_exec_until(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_until.yml",
        data="""
        tmp-wf-until:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Start run until stage"
                  id: until-stage
                  item: 1
                  until: "${{ item }} > 4"
                  max_until_loop: 5
                  stages:
                    - name: "Echo stage"
                      echo: |
                        Start run with item ${{ item }}
                    - name: "Final Echo"
                      if: ${{ item }} == 4
                      echo: |
                        Final run
                    - name: "Set item"
                      run: |
                        item = ${{ item }}
                        item += 1
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-until")
        stage: Stage = workflow.job("first-job").stage("until-stage")
        rs = stage.set_outputs(stage.handler_execute({}).context, to={})
        assert rs == {
            "stages": {
                "until-stage": {
                    "outputs": {
                        "until": {
                            1: {
                                "item": 1,
                                "stages": {
                                    "2709471980": {"outputs": {}},
                                    "9263488742": {"outputs": {}},
                                    "3635623619": {"outputs": {"item": 2}},
                                },
                            },
                            2: {
                                "item": 2,
                                "stages": {
                                    "2709471980": {"outputs": {}},
                                    "9263488742": {"outputs": {}},
                                    "3635623619": {"outputs": {"item": 3}},
                                },
                            },
                            3: {
                                "item": 3,
                                "stages": {
                                    "2709471980": {"outputs": {}},
                                    "9263488742": {"outputs": {}},
                                    "3635623619": {"outputs": {"item": 4}},
                                },
                            },
                            4: {
                                "item": 4,
                                "stages": {
                                    "2709471980": {"outputs": {}},
                                    "9263488742": {"outputs": {}},
                                    "3635623619": {"outputs": {"item": 5}},
                                },
                            },
                        }
                    }
                }
            }
        }


def test_stage_exec_case_match(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_case_match.yml",
        data="""
        tmp-wf-case-match:
          type: Workflow
          params: { name: str }
          jobs:
            first-job:
              stages:
                - name: "Start run case-match stage"
                  id: case-stage
                  case: ${{ params.name }}
                  match:
                    - case: "bar"
                      stage:
                        name: Match name with Bar
                        echo: Hello ${{ params.name }}

                    - case: "foo"
                      stage:
                        name: Match name with For
                        echo: Hello ${{ params.name }}

                    - case: "_"
                      stage:
                        name: Else stage
                        echo: Not match any case.
                - name: "Stage raise not has else condition"
                  id: raise-else
                  case: ${{ params.name }}
                  match:
                    - case: "bar"
                      stage:
                        name: Match name with Bar
                        echo: Hello ${{ params.name }}
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-case-match")
        stage: Stage = workflow.job("first-job").stage("case-stage")
        rs = stage.set_outputs(
            stage.handler_execute({"params": {"name": "bar"}}).context, to={}
        )
        assert rs == {"stages": {"case-stage": {"outputs": {}}}}

        rs = stage.set_outputs(
            stage.handler_execute({"params": {"name": "foo"}}).context, to={}
        )
        assert rs == {"stages": {"case-stage": {"outputs": {}}}}

        rs = stage.set_outputs(
            stage.handler_execute({"params": {"name": "test"}}).context, to={}
        )
        assert rs == {"stages": {"case-stage": {"outputs": {}}}}

        stage: Stage = workflow.job("first-job").stage("raise-else")
        with pytest.raises(StageException):
            stage.handler_execute({"params": {"name": "test"}})
