import pytest
from ddeutil.workflow import Workflow
from ddeutil.workflow.exceptions import StageException
from ddeutil.workflow.stage import Stage
from ddeutil.workflow.utils import Result

from tests.utils import override_env


def test_stage_py_raise():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-common", externals={}
    )
    stage: Stage = workflow.job("raise-run").stage(stage_id="raise-error")

    assert stage.id == "raise-error"

    with pytest.raises(StageException):
        stage.execute(params={"x": "Foo"})


def test_stage_py_not_raise():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-common", externals={}
    )
    stage: Stage = workflow.job("raise-run").stage(stage_id="raise-error")

    assert stage.id == "raise-error"

    with override_env({"WORKFLOW_CORE_STAGE_RAISE_ERROR": "false"}):
        rs = stage.execute(params={"x": "Foo"})
        assert rs.status == 1
        assert isinstance(rs.context["error"], ValueError)
        assert rs.context["error_message"] == (
            "ValueError: Testing raise error inside PyStage!!!"
        )


def test_stage_py():
    # NOTE: Get stage from the specific workflow.
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-common", externals={}
    )
    stage: Stage = workflow.job("demo-run").stage(stage_id="run-var")
    assert stage.id == "run-var"

    # NOTE: Start execute with manual stage parameters.
    p = {
        "params": {"name": "Author"},
        "stages": {"hello-world": {"outputs": {"x": "Foo"}}},
    }
    rs = stage.execute(params=p)
    _prepare_rs = stage.set_outputs(rs.context, to=p)
    assert {
        "params": {"name": "Author"},
        "stages": {
            "hello-world": {"outputs": {"x": "Foo"}},
            "run-var": {"outputs": {"x": 1}},
        },
    } == _prepare_rs


def test_stage_py_func():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-python", externals={}
    )
    stage: Stage = workflow.job("second-job").stage(stage_id="create-func")
    assert stage.id == "create-func"

    # NOTE: Start execute with manual stage parameters.
    rs: Result = stage.execute(params={})
    _prepare_rs = stage.set_outputs(rs.context, to={})
    assert ("var_inside", "echo") == tuple(
        _prepare_rs["stages"]["create-func"]["outputs"].keys()
    )
