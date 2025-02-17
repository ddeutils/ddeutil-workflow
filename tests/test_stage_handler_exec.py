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


def test_stage_exec_bash():
    workflow: Workflow = Workflow.from_loader(name="wf-run-common")
    stage: Stage = workflow.job("bash-run").stage("echo")
    rs: Result = stage.handler_execute({})
    assert {
        "return_code": 0,
        "stdout": "Hello World\nVariable Foo",
        "stderr": None,
    } == rs.context


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


def test_stage_exec_hook():
    workflow: Workflow = Workflow.from_loader(name="wf-hook-return-type")
    stage: Stage = workflow.job("second-job").stage("extract-load")
    rs: Result = stage.handler_execute({})

    assert 0 == rs.status
    assert {"records": 1} == rs.context


def test_stage_exec_hook_raise_return_type():
    workflow: Workflow = Workflow.from_loader(name="wf-hook-return-type")
    stage: Stage = workflow.job("first-job").stage("valid-type")

    with pytest.raises(StageException):
        stage.handler_execute({})


def test_stage_exec_hook_raise_args():
    workflow: Workflow = Workflow.from_loader(name="wf-hook-return-type")
    stage: Stage = workflow.job("first-job").stage("args-necessary")

    with pytest.raises(StageException):
        stage.handler_execute({})


def test_stage_exec_hook_not_valid():
    workflow: Workflow = Workflow.from_loader(name="wf-hook-return-type")
    stage: Stage = workflow.job("first-job").stage("hook-not-valid")

    with pytest.raises(StageException):
        stage.handler_execute({})


def test_stage_exec_hook_not_register():
    workflow: Workflow = Workflow.from_loader(name="wf-hook-return-type")
    stage: Stage = workflow.job("first-job").stage("hook-not-register")

    with pytest.raises(StageException):
        stage.handler_execute({})


def test_stage_exec_py_raise():
    with mock.patch.object(Config, "stage_raise_error", True):
        workflow: Workflow = Workflow.from_loader(name="wf-run-common")
        stage: Stage = workflow.job("raise-run").stage(stage_id="raise-error")
        with pytest.raises(StageException):
            stage.handler_execute(params={"x": "Foo"})


def test_stage_exec_py_not_raise():
    with mock.patch.object(Config, "stage_raise_error", False):
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
        assert isinstance(rs.context["error"], ValueError)
        assert rs.context["error_message"] == (
            "ValueError: Testing raise error inside PyStage!!!"
        )

        rs_out = stage.set_outputs(rs.context, {})
        assert rs_out == {
            "stages": {
                "raise-error": {
                    "outputs": {
                        "error": getdot(
                            "stages.raise-error.outputs.error", rs_out
                        ),
                        "error_message": (
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
    rs: Result = stage.handler_execute(params={})
    rs_out = stage.set_outputs(rs.context, to={})
    assert ("var_inside", "echo") == tuple(
        rs_out["stages"]["create-func"]["outputs"].keys()
    )
    assert isfunction(rs_out["stages"]["create-func"]["outputs"]["echo"])


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
