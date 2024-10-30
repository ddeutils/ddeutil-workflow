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

    stage.run_id = "demo"
    assert "demo" == stage.run_id

    # NOTE: Passing run_id directly to a Stage object.
    stage: Stage = EmptyStage.model_validate(
        {"run_id": "dummy", "name": "Empty Stage", "echo": "hello world"}
    )
    assert stage.run_id == "dummy"


def test_stage_empty_execute():
    stage: Stage = EmptyStage.model_validate(
        {"name": "Empty Stage", "echo": "hello world"}
    )
    rs: Result = stage.execute(params={})
    assert 0 == rs.status
    assert {} == rs.context


def test_stage_empty_raise():

    # NOTE: Raise error when passing template data to the name field.
    with pytest.raises(ValidationError):
        EmptyStage.model_validate(
            {
                "name": "Empty ${{ params.name }}",
                "echo": "hello world",
            }
        )

    # NOTE: Raise error when passing template data to the id field.
    with pytest.raises(ValidationError):
        EmptyStage.model_validate(
            {
                "name": "Empty Stage",
                "id": "stage-${{ params.name }}",
                "echo": "hello world",
            }
        )


def test_stage_if_condition():
    workflow = Workflow.from_loader(name="wf-condition")
    stage: Stage = workflow.job("condition-job").stage(
        stage_id="condition-stage"
    )
    assert not stage.is_skipped(params=workflow.parameterize({"name": "foo"}))
    assert stage.is_skipped(params=workflow.parameterize({"name": "bar"}))


def test_stage_if_condition_raise():
    workflow = Workflow.from_loader(name="wf-condition-raise")
    stage: Stage = workflow.job("condition-job").stage(
        stage_id="condition-stage"
    )
    # NOTE: Raise error because output of if-condition does not be boolean type.
    with pytest.raises(StageException):
        stage.is_skipped({"params": {"name": "foo"}})
