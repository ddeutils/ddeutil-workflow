from inspect import isfunction
from unittest import mock

import pytest
from ddeutil.workflow import Workflow
from ddeutil.workflow.conf import Config
from ddeutil.workflow.exceptions import StageException
from ddeutil.workflow.stage import Stage
from ddeutil.workflow.utils import Result


def test_stage_py_raise():
    with mock.patch.object(Config, "stage_raise_error", True):
        workflow: Workflow = Workflow.from_loader(name="wf-run-common")
        stage: Stage = workflow.job("raise-run").stage(stage_id="raise-error")
        with pytest.raises(StageException):
            stage.execute(params={"x": "Foo"})


def test_stage_py_not_raise():
    with mock.patch.object(Config, "stage_raise_error", False):
        workflow: Workflow = Workflow.from_loader(name="wf-run-common")
        stage: Stage = workflow.job("raise-run").stage(stage_id="raise-error")
        rs = stage.execute(params={"x": "Foo"})
        assert rs.status == 1
        assert isinstance(rs.context["error"], ValueError)
        assert rs.context["error_message"] == (
            "ValueError: Testing raise error inside PyStage!!!"
        )


def test_stage_py_with_vars():
    workflow: Workflow = Workflow.from_loader(name="wf-run-common")
    stage: Stage = workflow.job("demo-run").stage(stage_id="run-var")
    assert stage.id == "run-var"

    params = {
        "params": {"name": "Author"},
        "stages": {"hello-world": {"outputs": {"x": "Foo"}}},
    }
    rs_out = stage.set_outputs(stage.execute(params=params).context, to=params)
    assert {
        "params": {"name": "Author"},
        "stages": {
            "hello-world": {"outputs": {"x": "Foo"}},
            "run-var": {"outputs": {"x": 1}},
        },
    } == rs_out


def test_stage_py_func():
    workflow: Workflow = Workflow.from_loader(name="wf-run-python")
    stage: Stage = workflow.job("second-job").stage(stage_id="create-func")
    rs: Result = stage.execute(params={})
    rs_out = stage.set_outputs(rs.context, to={})
    assert ("var_inside", "echo") == tuple(
        rs_out["stages"]["create-func"]["outputs"].keys()
    )
    assert isfunction(rs_out["stages"]["create-func"]["outputs"]["echo"])
