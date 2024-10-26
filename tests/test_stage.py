import pytest
from ddeutil.workflow import Workflow
from ddeutil.workflow.exceptions import StageException
from ddeutil.workflow.stage import EmptyStage, Stage
from ddeutil.workflow.utils import Result
from pydantic import ValidationError


def test_stage():
    stage: Stage = EmptyStage.model_validate(
        {"name": "Empty Stage", "echo": "hello world"}
    )
    new_stage: Stage = stage.model_copy(update={"run_id": "dummy"})
    assert "dummy" == new_stage.run_id
    assert id(stage) != id(new_stage)


def test_stage_empty():
    stage: Stage = EmptyStage.model_validate(
        {"name": "Empty Stage", "echo": "hello world"}
    )
    rs: Result = stage.execute(params={})
    assert 0 == rs.status
    assert {} == rs.context

    stage.run_id = "demo"
    assert "demo" == stage.run_id


def test_stage_empty_name_raise():
    with pytest.raises(ValidationError):
        EmptyStage.model_validate(
            {
                "run_id": "demo",
                "name": "Empty ${{ params.name }}",
                "echo": "hello world",
            }
        )


def test_stage_condition():
    params = {"name": "foo"}
    workflow = Workflow.from_loader(name="wf-condition", externals={})
    stage = workflow.job("condition-job").stage(stage_id="condition-stage")

    assert not stage.is_skipped(params=workflow.parameterize(params))
    assert stage.is_skipped(params=workflow.parameterize({"name": "bar"}))
    assert {"name": "foo"} == params


def test_stage_condition_raise():
    workflow: Workflow = Workflow.from_loader(
        name="wf-condition-raise", externals={}
    )
    stage: Stage = workflow.job("condition-job").stage("condition-stage")

    with pytest.raises(StageException):
        stage.is_skipped({"params": {"name": "foo"}})
