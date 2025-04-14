import pytest
from ddeutil.workflow import SUCCESS, EmptyStage, Result


@pytest.mark.asyncio
async def test_stage_empty_axecute():
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
        name="Empty Stage", echo="hello world", sleep=0.01
    )
    rs: Result = await stage.handler_axecute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {}
