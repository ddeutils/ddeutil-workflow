from datetime import datetime
from inspect import isfunction
from threading import Event

import pytest
from ddeutil.workflow import (
    CANCEL,
    FAILED,
    SUCCESS,
    ParallelStage,
    Result,
    Workflow,
)
from ddeutil.workflow.exceptions import StageException
from ddeutil.workflow.stages import (
    BashStage,
    CallStage,
    ForEachStage,
    PyStage,
    RaiseStage,
    Stage,
)
from pydantic import TypeAdapter

from .utils import MockEvent, dump_yaml_context


def test_bash_stage_exec():
    stage: BashStage = BashStage(
        name="Bash Stage",
        bash='echo "Hello World";\nVAR=\'Foo\';\necho "Variable $VAR";',
    )
    rs: Result = stage.handler_execute({})
    assert rs.context == {
        "return_code": 0,
        "stdout": "Hello World\nVariable Foo",
        "stderr": None,
    }


def test_bash_stage_exec_with_env():
    stage: BashStage = BashStage(
        name="Bash Stage", bash='echo "ENV $$FOO";', env={"FOO": "Bar"}
    )
    rs: Result = stage.handler_execute({})
    assert rs.context == {
        "return_code": 0,
        "stdout": "ENV Bar",
        "stderr": None,
    }


def test_bash_stage_exec_raise():
    stage: BashStage = BashStage(
        name="Bash Stage",
        bash='echo "Test Raise Error case with failed" >&2;\n' "exit 1;",
    )

    # NOTE: Raise error from bash that force exit 1.
    with pytest.raises(StageException):
        stage.handler_execute({}, raise_error=True)

    rs: Result = stage.handler_execute({}, raise_error=False)
    assert rs.status == FAILED
    assert rs.context == {
        "errors": {
            "name": "StageException",
            "message": (
                "Subprocess: Test Raise Error case with failed\n"
                "---( statement )---\n"
                '```bash\necho "Test Raise Error case with failed" >&2;\n'
                "exit 1;\n"
                "```"
            ),
        }
    }


def test_call_stage_exec(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_call_return_type.yml",
        data="""
        tmp-wf-call-return-type:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Necessary argument do not pass"
                  id: args-necessary
                  uses: tasks/mssql-proc@odbc
                  with:
                    params:
                      run_mode: "T"
                      run_date: 2024-08-01
                      source: src
                      target: tgt
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
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-call-return-type")

        stage: Stage = workflow.job("second-job").stage("extract-load")
        rs: Result = stage.handler_execute({})
        assert rs.status == SUCCESS
        assert {"records": 1} == rs.context

        stage: Stage = workflow.job("second-job").stage("async-extract-load")
        rs: Result = stage.handler_execute({})
        assert rs.status == SUCCESS
        assert rs.context == {"records": 1}

        # NOTE: Raise because invalid return type.
        with pytest.raises(StageException):
            stage: Stage = CallStage(
                name="Type not valid", uses="tasks/return-type-not-valid@raise"
            )
            stage.handler_execute({})

        # NOTE: Raise because necessary args do not pass.
        with pytest.raises(StageException):
            stage: Stage = workflow.job("first-job").stage("args-necessary")
            stage.handler_execute({})

        # NOTE: Raise because call does not valid.
        with pytest.raises(StageException):
            stage: Stage = CallStage(name="Not valid", uses="tasks-foo-bar")
            stage.handler_execute({})

        # NOTE: Raise because call does not register.
        with pytest.raises(StageException):
            stage: Stage = CallStage(name="Not register", uses="tasks/abc@foo")
            stage.handler_execute({})

        stage: Stage = CallStage.model_validate(
            {
                "name": "Return with Pydantic Model",
                "id": "return-model",
                "uses": "tasks/gen-type@demo",
                "with": {
                    "args1": "foo",
                    "args2": "conf/path",
                    "args3": {"name": "test", "data": {"input": "hello"}},
                },
            }
        )
        rs: Result = stage.handler_execute({})
        assert rs.status == SUCCESS
        assert rs.context == {"name": "foo", "data": {"key": "value"}}


def test_py_stage_exec_raise():
    stage: PyStage = PyStage(
        name="Raise Error Inside",
        id="raise-error",
        run="raise ValueError('Testing raise error inside PyStage!!!')",
    )

    with pytest.raises(StageException):
        stage.handler_execute(params={"x": "Foo"}, raise_error=True)

    rs = stage.handler_execute(params={"x": "Foo"}, raise_error=False)
    assert rs.status == FAILED
    assert rs.context == {
        "errors": {
            "name": "ValueError",
            "message": "Testing raise error inside PyStage!!!",
        }
    }

    output = stage.set_outputs(rs.context, {})
    assert output == {
        "stages": {
            "raise-error": {
                "outputs": {},
                "errors": {
                    "name": "ValueError",
                    "message": "Testing raise error inside PyStage!!!",
                },
            },
        },
    }


def test_py_stage_exec():
    stage: PyStage = PyStage(
        name="Run Sequence and use var from Above",
        id="run-var",
        vars={"x": "${{ stages.hello-world.outputs.x }}"},
        run=(
            "print(f'Receive x from above with {x}')\n\n"
            "# Change x value\nx: int = 1\n"
            'result.trace.info("Log from result object inside PyStage!!!")'
        ),
    )
    rs: Result = stage.handler_execute(
        params={
            "params": {"name": "Author"},
            "stages": {"hello-world": {"outputs": {"x": "Foo"}}},
        }
    )
    assert rs.status == SUCCESS

    rs = stage.set_outputs(
        stage.handler_execute(
            params={
                "params": {"name": "Author"},
                "stages": {"hello-world": {"outputs": {"x": "Foo"}}},
            }
        ).context,
        to={},
    )
    assert rs == {"stages": {"run-var": {"outputs": {"x": 1}}}}


def test_py_stage_exec_create_func():
    stage: PyStage = PyStage(
        name="Set variable and function",
        id="create-func",
        run=(
            "var_inside: str = 'Create Function Inside'\n"
            'def echo(var: str) -> None:\n\tprint(f"Echo {var}")\n'
            "echo(var_inside)"
        ),
    )
    rs: Result = stage.handler_execute(params={})
    assert rs.status == SUCCESS

    rs: dict = stage.set_outputs(rs.context, {})
    assert isfunction(rs["stages"]["create-func"]["outputs"]["echo"])
    assert (
        rs["stages"]["create-func"]["outputs"]["var_inside"]
        == "Create Function Inside"
    )


def test_py_stage_exec_create_object():
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


def test_stage_exec_trigger_raise():
    stage: Stage = TypeAdapter(Stage).validate_python(
        {
            "name": "Trigger to raise workflow",
            "trigger": "wf-run-python-raise",
            "params": {},
        }
    )
    with pytest.raises(StageException):
        stage.handler_execute(params={})


def test_foreach_stage_exec():
    stage: Stage = ForEachStage(
        name="Start run for-each stage",
        id="foreach-stage",
        foreach=[1, 2, 3, 4],
        stages=[
            {"name": "Echo stage", "echo": "Start run with item ${{ item }}"},
            {
                "name": "Final Echo",
                "if": "${{ item }} == 4",
                "echo": "Final stage",
            },
        ],
    )
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
                                "9263488742": {
                                    "outputs": {},
                                    "skipped": True,
                                },
                            },
                        },
                        2: {
                            "item": 2,
                            "stages": {
                                "2709471980": {"outputs": {}},
                                "9263488742": {
                                    "outputs": {},
                                    "skipped": True,
                                },
                            },
                        },
                        3: {
                            "item": 3,
                            "stages": {
                                "2709471980": {"outputs": {}},
                                "9263488742": {
                                    "outputs": {},
                                    "skipped": True,
                                },
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
    stage: ForEachStage = ForEachStage(
        name="Foreach values type not valid",
        id="foreach-raise",
        foreach="${{values.items}}",
    )
    with pytest.raises(StageException):
        stage.handler_execute({"values": {"items": "test"}})

    # NOTE: Raise because foreach item was duplicated.
    stage: ForEachStage = ForEachStage(
        name="Foreach item was duplicated",
        foreach=[1, 1, 2, 3],
    )
    with pytest.raises(StageException):
        stage.handler_execute({})

    stage: ForEachStage = ForEachStage(
        name="Foreach item was duplicated",
        foreach=[1, 1, 2, 3],
        stages=[{"name": "Echo stage", "echo": "Start item ${{ item }}"}],
        use_index_as_key=True,
    )
    rs: Result = stage.handler_execute({})
    assert rs.status == SUCCESS
    assert rs.context == {
        "items": [1, 1, 2, 3],
        "foreach": {
            0: {"item": 1, "stages": {"2709471980": {"outputs": {}}}},
            1: {"item": 1, "stages": {"2709471980": {"outputs": {}}}},
            2: {"item": 2, "stages": {"2709471980": {"outputs": {}}}},
            3: {"item": 3, "stages": {"2709471980": {"outputs": {}}}},
        },
    }


def test_foreach_stage_exec_raise(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_foreach_raise.yml",
        data="""
        tmp-wf-foreach-raise:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Start run for-each stage"
                  id: foreach-stage
                  foreach: [1, 2]
                  concurrent: 2
                  stages:
                    - name: "Echo stage"
                      echo: |
                        Start run with item ${{ item }}
                    - name: "Final Echo"
                      if: ${{ item }} == 2
                      raise: Raise for item equal 2
                    - name: "Sleep stage"
                      sleep: 4
                    - name: "Echo Final"
                      echo: "This stage should not echo because event was set"
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-foreach-raise")
        stage: Stage = workflow.job("first-job").stage("foreach-stage")
        rs: Result = stage.handler_execute({})
        assert rs.status == FAILED
        assert rs.context == {
            "items": [1, 2],
            "foreach": {
                2: {
                    "item": 2,
                    "stages": {"2709471980": {"outputs": {}}},
                    "errors": {
                        "name": "StageException",
                        "message": "Raise for item equal 2",
                    },
                },
                1: {
                    "item": 1,
                    "stages": {
                        "2709471980": {"outputs": {}},
                        "9263488742": {"outputs": {}, "skipped": True},
                        "2238460182": {"outputs": {}},
                    },
                    "errors": {
                        "name": "StageException",
                        "message": "Item-Stage was canceled because event was set.",
                    },
                },
            },
            "errors": {
                2: {
                    "name": "StageException",
                    "message": "Raise for item equal 2",
                },
                1: {
                    "name": "StageException",
                    "message": "Item-Stage was canceled because event was set.",
                },
            },
        }


def test_foreach_stage_exec_concurrent(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_foreach_concurrent.yml",
        data="""
        tmp-wf-foreach-concurrent:
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
        workflow = Workflow.from_conf(name="tmp-wf-foreach-concurrent")
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
                                    "9263488742": {
                                        "outputs": {},
                                        "skipped": True,
                                    },
                                },
                            },
                            2: {
                                "item": 2,
                                "stages": {
                                    "2709471980": {"outputs": {}},
                                    "9263488742": {
                                        "outputs": {},
                                        "skipped": True,
                                    },
                                },
                            },
                            3: {
                                "item": 3,
                                "stages": {
                                    "2709471980": {"outputs": {}},
                                    "9263488742": {
                                        "outputs": {},
                                        "skipped": True,
                                    },
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


def test_foreach_stage_exec_concurrent_with_raise():
    stage: ForEachStage = ForEachStage(
        id="foreach-stage",
        name="Start run for-each stage",
        foreach=[1, 2, 3, 4, 5],
        concurrent=2,
        stages=[
            {
                "name": "Raise with PyStage",
                "run": (
                    "import time\n\nif ${{ item }} == 2:\n\t"
                    'raise ValueError("Raise error for item equal 2")\n'
                    "else:\n\ttime.sleep(3)"
                ),
            },
        ],
        extras={"stage_default_id": False},
    )
    event = MockEvent(n=4)
    rs: Result = stage.set_outputs(
        stage.handler_execute({}, event=event).context, to={}
    )
    assert rs == {
        "stages": {
            "foreach-stage": {
                "outputs": {
                    "items": [1, 2, 3, 4, 5],
                    "foreach": {
                        2: {
                            "item": 2,
                            "stages": {},
                            "errors": {
                                "name": "StageException",
                                "message": "PyStage: ValueError: Raise error for item equal 2",
                            },
                        },
                        3: {"item": 3, "stages": {}},
                        1: {"item": 1, "stages": {}},
                    },
                },
                "errors": {
                    2: {
                        "name": "StageException",
                        "message": "PyStage: ValueError: Raise error for item equal 2",
                    },
                },
            }
        }
    }


def test_parallel_stage_exec(test_path):
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
                        sleep: 1
                      - name: "Skip Stage"
                        if: ${{ branch | rstr }} == "branch02"
                        id: skip-stage
                    branch02:
                      - name: "Echo branch02 stage"
                        echo: |
                          Start run with branch 2
        """,
    ):
        workflow = Workflow.from_conf(
            name="tmp-wf-parallel",
            extras={"stage_raise_error": False},
        )
        stage: Stage = workflow.job("first-job").stage("parallel-stage")
        rs = stage.set_outputs(stage.handler_execute({}).context, to={})
        assert rs == {
            "stages": {
                "parallel-stage": {
                    "outputs": {
                        "parallel": {
                            "branch02": {
                                "branch": "branch02",
                                "stages": {"4967824305": {"outputs": {}}},
                            },
                            "branch01": {
                                "branch": "branch01",
                                "stages": {
                                    "0573477600": {"outputs": {}},
                                    "skip-stage": {
                                        "outputs": {},
                                        "skipped": True,
                                    },
                                },
                            },
                        },
                    },
                },
            },
        }

        event = Event()
        event.set()
        rs: Result = stage.handler_execute({}, event=event)
        assert rs.status == CANCEL
        assert rs.context == {
            "parallel": {},
            "errors": {
                "name": "StageException",
                "message": (
                    "Stage was canceled from event that had set before stage "
                    "parallel execution."
                ),
            },
        }

        event = MockEvent(n=2)
        rs: Result = stage.handler_execute({}, event=event)
        assert rs.status == FAILED
        assert rs.context == {
            "parallel": {
                "branch02": {
                    "branch": "branch02",
                    "stages": {},
                    "errors": {
                        "name": "StageException",
                        "message": "Branch-Stage was canceled from event that had set before stage branch execution.",
                    },
                },
                "branch01": {
                    "branch": "branch01",
                    "stages": {
                        "0573477600": {"outputs": {}},
                        "skip-stage": {"outputs": {}, "skipped": True},
                    },
                },
            },
            "errors": {
                "branch02": {
                    "name": "StageException",
                    "message": "Branch-Stage was canceled from event that had set before stage branch execution.",
                },
            },
        }


def test_parallel_stage_exec_raise():
    stage = ParallelStage(
        name="Parallel Stage Raise",
        parallel={
            "branch01": [
                {
                    "name": "Raise Stage",
                    "raise": "Raise error inside parallel stage.",
                }
            ]
        },
    )
    rs: Result = stage.handler_execute({})
    assert rs.status == FAILED
    assert rs.context == {
        "parallel": {
            "branch01": {
                "branch": "branch01",
                "stages": {},
                "errors": {
                    "name": "StageException",
                    "message": "Raise error inside parallel stage.",
                },
            }
        },
        "errors": {
            "branch01": {
                "name": "StageException",
                "message": "Raise error inside parallel stage.",
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
                  max-loop: 5
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
                                "loop": 1,
                                "item": 1,
                                "stages": {
                                    "2709471980": {"outputs": {}},
                                    "9263488742": {
                                        "outputs": {},
                                        "skipped": True,
                                    },
                                    "3635623619": {"outputs": {"item": 2}},
                                },
                            },
                            2: {
                                "loop": 2,
                                "item": 2,
                                "stages": {
                                    "2709471980": {"outputs": {}},
                                    "9263488742": {
                                        "outputs": {},
                                        "skipped": True,
                                    },
                                    "3635623619": {"outputs": {"item": 3}},
                                },
                            },
                            3: {
                                "loop": 3,
                                "item": 3,
                                "stages": {
                                    "2709471980": {"outputs": {}},
                                    "9263488742": {
                                        "outputs": {},
                                        "skipped": True,
                                    },
                                    "3635623619": {"outputs": {"item": 4}},
                                },
                            },
                            4: {
                                "loop": 4,
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
                      stages:
                        - name: Match name with Bar
                          echo: Hello ${{ params.name }}

                    - case: "foo"
                      stages:
                        - name: Match name with For
                          echo: Hello ${{ params.name }}

                    - case: "_"
                      stages:
                        - name: Else stage
                          echo: Not match any case.
                - name: "Stage raise not has else condition"
                  id: raise-else
                  case: ${{ params.name }}
                  match:
                    - case: "bar"
                      stages:
                        - name: Match name with Bar
                          echo: Hello ${{ params.name }}
                - name: "Stage skip not has else condition"
                  id: not-else
                  case: ${{ params.name }}
                  skip-not-match: true
                  match:
                    - case: "bar"
                      stages:
                        - name: Match name with Bar
                          echo: Hello ${{ params.name }}
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-case-match")
        stage: Stage = workflow.job("first-job").stage("case-stage")
        rs = stage.set_outputs(
            stage.handler_execute({"params": {"name": "bar"}}).context, to={}
        )
        assert rs == {
            "stages": {
                "case-stage": {
                    "outputs": {
                        "case": "bar",
                        "stages": {"3616274431": {"outputs": {}}},
                    },
                },
            },
        }

        rs = stage.set_outputs(
            stage.handler_execute({"params": {"name": "foo"}}).context, to={}
        )
        assert rs == {
            "stages": {
                "case-stage": {
                    "outputs": {
                        "case": "foo",
                        "stages": {"4740784512": {"outputs": {}}},
                    }
                }
            }
        }

        rs = stage.set_outputs(
            stage.handler_execute({"params": {"name": "test"}}).context, to={}
        )
        assert rs == {
            "stages": {
                "case-stage": {
                    "outputs": {
                        "case": "_",
                        "stages": {"5883888894": {"outputs": {}}},
                    }
                }
            }
        }

        # NOTE: Raise because else condition does not set.
        stage: Stage = workflow.job("first-job").stage("raise-else")
        with pytest.raises(StageException):
            stage.handler_execute({"params": {"name": "test"}})

        stage: Stage = workflow.job("first-job").stage("not-else")
        rs = stage.set_outputs(
            stage.handler_execute({"params": {"name": "test"}}).context, to={}
        )
        assert rs == {
            "stages": {
                "not-else": {
                    "outputs": {},
                    "errors": {
                        "name": "StageException",
                        "message": (
                            "Case-Stage was canceled because it does not match "
                            "any case and else condition does not set too."
                        ),
                    },
                }
            }
        }


def test_stage_py_virtual(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_py_virtual.yml",
        data="""
        tmp-wf-py-virtual:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Start run Python on the new Virtual"
                  id: py-virtual
                  deps:
                    - pandas
                  run: |
                    import pandas as pd
                    print(pd)
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-py-virtual")
        stage: Stage = workflow.job("first-job").stage("py-virtual")
        # TODO: This testcase raise error for uv does not exist on GH action.
        try:
            rs = stage.set_outputs(
                stage.handler_execute({"params": {}}).context, to={}
            )
            print(rs)
        except StageException as e:
            print(e)


def test_raise_stage_exec():
    stage: RaiseStage = RaiseStage.model_validate(
        obj={
            "name": "Raise Stage",
            "raise": (
                "Demo raise error from the raise stage\nThis is the new "
                "line from error message."
            ),
        },
    )
    rs: Result = stage.handler_execute(params={}, raise_error=False)
    assert rs.status == FAILED
    assert rs.context == {
        "errors": {
            "name": "StageException",
            "message": (
                "Demo raise error from the raise stage\n"
                "This is the new line from error message."
            ),
        }
    }

    with pytest.raises(StageException):
        stage.handler_execute(params={}, raise_error=True)
