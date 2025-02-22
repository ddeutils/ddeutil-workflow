from datetime import datetime
from inspect import isfunction
from unittest import mock

import pytest
from ddeutil.core import getdot
from ddeutil.workflow import Workflow
from ddeutil.workflow.conf import Config
from ddeutil.workflow.exceptions import StageException
from ddeutil.workflow.result import Result
from ddeutil.workflow.stage import Stage

from .utils import dump_yaml_context


def test_stage_exec_bash():
    workflow: Workflow = Workflow.from_loader(name="wf-run-common")
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
    workflow: Workflow = Workflow.from_loader(name="wf-run-common")
    stage: Stage = workflow.job("bash-run-env").stage("echo-env")
    rs: Result = stage.handler_execute({})
    assert {
        "return_code": 0,
        "stdout": "Hello World\nVariable Foo\nENV Bar",
        "stderr": None,
    } == rs.context


def test_stage_exec_bash_env_raise():
    workflow: Workflow = Workflow.from_loader(name="wf-run-common")
    stage: Stage = workflow.job("bash-run-env").stage("raise-error")

    # NOTE: Raise error from bash that force exit 1.
    with pytest.raises(StageException):
        stage.handler_execute({})


def test_stage_exec_hook(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_hook_return_type.yml",
        data="""
        tmp-wf-hook-return-type:
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
                - name: "Hook value not valid"
                  id: hook-not-valid
                  uses: tasks-foo-bar
                - name: "Hook does not register"
                  id: hook-not-register
                  uses: tasks/abc@foo
            second-job:
              stages:
                - name: "Extract & Load Local System"
                  id: extract-load
                  uses: tasks/el-csv-to-parquet@polars-dir
                  with:
                    source: src
                    sink: sink
        """,
    ):
        workflow = Workflow.from_loader(name="tmp-wf-hook-return-type")

        stage: Stage = workflow.job("second-job").stage("extract-load")
        rs: Result = stage.handler_execute({})

        assert 0 == rs.status
        assert {"records": 1} == rs.context

        # NOTE: Raise because invalid return type.
        with pytest.raises(StageException):
            stage: Stage = workflow.job("first-job").stage("valid-type")
            stage.handler_execute({})

        # NOTE: Raise because necessary args do not pass.
        with pytest.raises(StageException):
            stage: Stage = workflow.job("first-job").stage("args-necessary")
            stage.handler_execute({})

        # NOTE: Raise because hook does not valid.
        with pytest.raises(StageException):
            stage: Stage = workflow.job("first-job").stage("hook-not-valid")
            stage.handler_execute({})

        # NOTE: Raise because hook does not register.
        with pytest.raises(StageException):
            stage: Stage = workflow.job("first-job").stage("hook-not-register")
            stage.handler_execute({})


@mock.patch.object(Config, "stage_raise_error", True)
def test_stage_exec_py_raise():
    workflow: Workflow = Workflow.from_loader(name="wf-run-common")
    stage: Stage = workflow.job("raise-run").stage(stage_id="raise-error")
    with pytest.raises(StageException):
        stage.handler_execute(params={"x": "Foo"})


@mock.patch.object(Config, "stage_raise_error", False)
def test_stage_exec_py_not_raise():
    workflow: Workflow = Workflow.from_loader(name="wf-run-common")
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
            "message": "ValueError: Testing raise error inside PyStage!!!",
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
                    "message": (
                        "ValueError: Testing raise error inside PyStage!!!"
                    ),
                },
            },
        },
    }


def test_stage_exec_py_with_vars():
    workflow: Workflow = Workflow.from_loader(name="wf-run-common")
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
    workflow: Workflow = Workflow.from_loader(name="wf-run-python")
    stage: Stage = workflow.job("second-job").stage(stage_id="create-func")
    rs = stage.set_outputs(stage.handler_execute(params={}).context, to={})
    assert ("var_inside", "echo") == tuple(
        rs["stages"]["create-func"]["outputs"].keys()
    )
    assert isfunction(rs["stages"]["create-func"]["outputs"]["echo"])


def test_stage_exec_py_create_object():
    workflow: Workflow = Workflow.from_loader(name="wf-run-python-filter")
    stage: Stage = workflow.job("create-job").stage(stage_id="create-stage")
    rs = stage.set_outputs(stage.handler_execute(params={}).context, to={})
    assert len(rs["stages"]["create-stage"]["outputs"]) == 1


def test_stage_exec_trigger():
    workflow = Workflow.from_loader(name="wf-trigger", externals={})
    stage: Stage = workflow.job("trigger-job").stage(stage_id="trigger-stage")
    rs: Result = stage.handler_execute(params={})
    assert all(k in ("params", "jobs") for k in rs.context.keys())
    assert {
        "author-run": "Trigger Runner",
        "run-date": datetime(2024, 8, 1),
    } == rs.context["params"]


def test_stage_exec_trigger_from_workflow():
    workflow = Workflow.from_loader(name="wf-trigger", externals={})
    rs: Result = workflow.execute(params={})
    assert {
        "author-run": "Trigger Runner",
        "run-date": datetime(2024, 8, 1),
    } == getdot(
        "jobs.trigger-job.stages.trigger-stage.outputs.params", rs.context
    )
