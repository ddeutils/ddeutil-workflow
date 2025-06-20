from threading import Event

import pytest
from ddeutil.workflow import CANCEL
from ddeutil.workflow.errors import StageError
from ddeutil.workflow.result import FAILED, SKIP, SUCCESS, Result
from ddeutil.workflow.stages import EmptyStage, Stage
from pydantic import ValidationError


def test_empty_stage():
    stage: Stage = EmptyStage.model_validate(
        {"name": "Empty Stage", "echo": "hello world"}
    )
    assert stage.iden == "Empty Stage"
    assert stage == EmptyStage(name="Empty Stage", echo="hello world")
    assert not stage.is_nested

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

    stage: Stage = EmptyStage.model_validate(
        {"name": "Empty Stage", "desc": "\nThis is a test stage\n\tnewline"},
    )
    assert stage.desc == "This is a test stage\n\tnewline"


def test_empty_stage_execute():
    stage: EmptyStage = EmptyStage(name="Empty Stage", echo="hello world")
    rs: Result = stage.execute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {"status": SUCCESS}

    stage: EmptyStage = EmptyStage(
        name="Empty Stage", echo="hello world\nand this is newline to echo"
    )
    rs: Result = stage.execute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {"status": SUCCESS}

    stage: EmptyStage = EmptyStage(name="Empty Stage")
    rs: Result = stage.execute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {"status": SUCCESS}

    stage: EmptyStage = EmptyStage(name="Empty Stage", sleep=5.1)
    rs: Result = stage.execute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {"status": SUCCESS}

    stage: Stage = EmptyStage.model_validate(
        {"name": "Empty Stage", "desc": "\nThis is a test stage\n\tnewline"},
    )
    rs: Result = stage.execute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {"status": SUCCESS}


def test_empty_stage_raise():

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


def test_empty_stage_if_condition():
    stage: EmptyStage = EmptyStage.model_validate(
        {
            "name": "If Condition",
            "if": '"${{ params.name }}" == "foo"',
            "echo": "Hello world",
        }
    )
    assert not stage.is_skipped(params={"params": {"name": "foo"}})
    assert stage.is_skipped(params={"params": {"name": "bar"}})

    stage: EmptyStage = EmptyStage.model_validate(
        {
            "name": "If Condition Raise",
            "if": '"${{ params.name }}"',
            "echo": "Hello World",
        }
    )

    # NOTE: Raise if the returning type after eval does not match with boolean.
    with pytest.raises(StageError):
        stage.is_skipped({"params": {"name": "foo"}})


def test_empty_stage_get_outputs():
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


@pytest.mark.asyncio
async def test_empty_stage_axec():
    stage: EmptyStage = EmptyStage(name="Empty Stage")
    rs: Result = await stage.axecute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {"status": SUCCESS}

    stage: EmptyStage = EmptyStage(name="Empty Stage", echo="hello world")
    rs: Result = await stage.axecute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {"status": SUCCESS}

    stage: EmptyStage = EmptyStage(
        name="Empty Stage", echo="hello world", sleep=5.01
    )
    rs: Result = await stage.axecute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {"status": SUCCESS}

    stage: EmptyStage = EmptyStage(
        name="Empty Stage",
        echo=(
            "Hello World\nThis is the newline message.\nI want to test newline "
            "string doing well."
        ),
        sleep=0.01,
    )
    rs: Result = await stage.axecute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {"status": SUCCESS}


@pytest.mark.asyncio
async def test_empty_stage_axec_cancel():
    event = Event()
    event.set()

    stage: EmptyStage = EmptyStage(name="Empty Stage")
    rs: Result = await stage.axecute(params={}, event=event)
    assert rs.status == CANCEL
    assert rs.context == {
        "status": CANCEL,
        "errors": {
            "name": "StageCancelError",
            "message": "Execution was canceled from the event before start parallel.",
        },
    }


@pytest.mark.asyncio
async def test_empty_stage_if_condition_async():
    stage: EmptyStage = EmptyStage.model_validate(
        {
            "name": "If Condition",
            "if": '"${{ params.name }}" == "foo"',
            "echo": "Hello world",
        }
    )
    rs: Result = await stage.axecute(params={"params": {"name": "foo"}})
    assert rs.status == SUCCESS

    rs: Result = await stage.axecute(params={"params": {"name": "bar"}})
    assert rs.status == SKIP
    assert rs.context == {"status": SKIP}

    stage: EmptyStage = EmptyStage.model_validate(
        {
            "name": "If Condition Raise",
            "if": '"${{ params.name }}"',
            "echo": "Hello World",
        }
    )

    # NOTE: Raise if the returning type after eval does not match with boolean.
    # with pytest.raises(StageError):
    rs: Result = await stage.axecute({"params": {"name": "foo"}})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "StageError",
            "message": "TypeError: Return type of condition does not be boolean",
        },
    }
