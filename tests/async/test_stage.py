import pytest
from ddeutil.workflow import (
    FAILED,
    SUCCESS,
    BashStage,
    EmptyStage,
    RaiseStage,
    Result,
    StageException,
)


@pytest.mark.asyncio
async def test_empty_stage_axec():
    stage: EmptyStage = EmptyStage(name="Empty Stage")
    rs: Result = await stage.handler_axecute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {}

    stage: EmptyStage = EmptyStage(name="Empty Stage", echo="hello world")
    rs: Result = await stage.handler_axecute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {}

    stage: EmptyStage = EmptyStage(
        name="Empty Stage", echo="hello world", sleep=5.01
    )
    rs: Result = await stage.handler_axecute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {}

    stage: EmptyStage = EmptyStage(
        name="Empty Stage",
        echo=(
            "Hello World\nThis is the newline message.\nI want to test newline "
            "string doing well."
        ),
        sleep=0.01,
    )
    rs: Result = await stage.handler_axecute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {}


@pytest.mark.asyncio
async def test_bash_stage_axec():
    stage: BashStage = BashStage(name="Bash Stage", bash='echo "Hello World"')
    rs: Result = await stage.handler_axecute(params={})
    assert rs.status == SUCCESS


@pytest.mark.asyncio
async def test_raise_stage_exec():
    stage: RaiseStage = RaiseStage.model_validate(
        {"name": "Raise Stage", "raise": "This is test message error"}
    )
    rs: Result = await stage.handler_axecute(params={}, raise_error=False)
    assert rs.status == FAILED
    assert rs.context == {
        "errors": {
            "name": "StageException",
            "message": "This is test message error",
        },
    }

    with pytest.raises(StageException):
        await stage.handler_axecute(params={}, raise_error=True)
