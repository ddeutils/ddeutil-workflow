import pytest
from ddeutil.workflow.exceptions import StageException
from ddeutil.workflow.result import Result
from ddeutil.workflow.stages import EmptyStage, PyStage, Stage
from pydantic import TypeAdapter, ValidationError


def test_stage():
    stage: Stage = EmptyStage.model_validate(
        {"name": "Empty Stage", "echo": "hello world"}
    )
    assert stage.iden == "Empty Stage"
    assert stage.name == "Empty Stage"
    assert stage == EmptyStage(name="Empty Stage", echo="hello world")

    # NOTE: Copy the stage model with adding the id field.
    new_stage: Stage = stage.model_copy(update={"id": "stage-empty"})
    assert id(stage) != id(new_stage)
    assert new_stage.iden == "stage-empty"

    # NOTE: Passing run_id directly to a Stage object.
    stage: Stage = EmptyStage.model_validate(
        {"id": "dummy", "name": "Empty Stage", "echo": "hello world"}
    )
    assert stage.id == "dummy"
    assert stage.iden == "dummy"
    assert not stage.is_skipped(params={})

    stage: Stage = TypeAdapter(Stage).validate_python(
        {"name": "Empty Stage", "echo": "hello world"}
    )
    assert isinstance(stage, EmptyStage)


def test_stage_empty_execute():
    stage: EmptyStage = EmptyStage(name="Empty Stage", echo="hello world")
    rs: Result = stage.handler_execute(params={})

    assert isinstance(rs, Result)
    assert 0 == rs.status
    assert {} == rs.context

    stage: EmptyStage = EmptyStage(
        name="Empty Stage", echo="hello world\nand this is newline to echo"
    )
    rs: Result = stage.handler_execute(params={})
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
    stage: PyStage = PyStage.model_validate(
        {
            "name": "Test if condition",
            "if": '"${{ params.name }}" == "foo"',
            "run": """message: str = 'Hello World'\nprint(message)""",
        }
    )
    assert not stage.is_skipped(params={"params": {"name": "foo"}})
    assert stage.is_skipped(params={"params": {"name": "bar"}})


def test_stage_if_condition_raise(test_path):
    stage: PyStage = PyStage.model_validate(
        {
            "name": "Test if condition",
            "if": '"${{ params.name }}"',
            "run": """message: str = 'Hello World'\nprint(message)""",
        }
    )

    with pytest.raises(StageException):
        stage.is_skipped({"params": {"name": "foo"}})


def test_stage_get_outputs():
    stage: Stage = EmptyStage.model_validate(
        {"name": "Empty Stage", "echo": "hello world"}
    )
    outputs = {
        "stages": {
            "first-stage": {"outputs": {"foo": "bar"}},
            "4083404693": {"outputs": {"foo": "baz"}},
        },
    }
    stage.extras = {"stage_default_id": False}
    assert stage.get_outputs(outputs) == {}

    stage.extras = {"stage_default_id": True}
    assert stage.get_outputs(outputs) == {"foo": "baz"}

    stage: Stage = EmptyStage.model_validate(
        {"id": "first-stage", "name": "Empty Stage", "echo": "hello world"}
    )
    assert stage.get_outputs(outputs) == {"foo": "bar"}
