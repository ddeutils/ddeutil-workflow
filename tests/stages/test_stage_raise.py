import pytest
from ddeutil.workflow import FAILED, Result
from ddeutil.workflow.stages import RaiseStage


def test_raise_stage_exec():
    stage: RaiseStage = RaiseStage.model_validate(
        {
            "name": "Raise Stage",
            "raise": (
                "Demo raise error from the raise stage\nThis is the new "
                "line from error message."
            ),
        },
    )
    rs: Result = stage.handler_execute(params={})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "StageError",
            "message": (
                "Demo raise error from the raise stage\n"
                "This is the new line from error message."
            ),
        },
    }


@pytest.mark.asyncio
async def test_raise_stage_axec():
    stage: RaiseStage = RaiseStage.model_validate(
        {"name": "Raise Stage", "raise": "This is test message error"}
    )
    rs: Result = await stage.handler_axecute(params={})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "StageError",
            "message": "This is test message error",
        },
    }
