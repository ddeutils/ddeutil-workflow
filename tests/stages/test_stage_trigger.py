from datetime import datetime

from ddeutil.workflow import (
    CANCEL,
    FAILED,
    SUCCESS,
    Result,
    Workflow,
)
from ddeutil.workflow.stages import Stage

from src.ddeutil.workflow import TriggerStage

from ..utils import MockEvent


def test_trigger_stage_exec():
    workflow = Workflow.from_conf(name="wf-trigger", extras={})
    stage: Stage = workflow.job("trigger-job").stage(stage_id="trigger-stage")
    rs: Result = stage.handler_execute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "params": {
            "author-run": "Trigger Runner",
            "run-date": datetime(2024, 8, 1, 0, 0),
        },
        "jobs": {
            "first-job": {
                "stages": {
                    "printing": {
                        "outputs": {"x": "Trigger Runner"},
                        "status": SUCCESS,
                    },
                    "setting-x": {"outputs": {"x": 1}, "status": SUCCESS},
                },
                "status": SUCCESS,
            },
            "second-job": {
                "stages": {
                    "create-func": {
                        "outputs": {
                            "var_inside": "Create Function Inside",
                            "echo": "echo",
                        },
                        "status": SUCCESS,
                    },
                    "call-func": {"outputs": {}, "status": SUCCESS},
                    "9150930869": {"outputs": {}, "status": SUCCESS},
                },
                "status": SUCCESS,
            },
            "final-job": {
                "stages": {
                    "1772094681": {
                        "outputs": {
                            "return_code": 0,
                            "stdout": "Hello World",
                            "stderr": None,
                        },
                        "status": SUCCESS,
                    }
                },
                "status": SUCCESS,
            },
        },
    }
    print(rs.info)


def test_trigger_stage_exec_raise(test_path):
    # NOTE: Raise because the workflow name that pass to execution does not exist.
    stage: Stage = TriggerStage.model_validate(
        {
            "name": "Trigger raise with workflow not exist.",
            "trigger": "not-exist-workflow",
            "params": {},
        }
    )
    rs: Result = stage.handler_execute(params={})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "ValueError",
            "message": (
                f"Config 'not-exist-workflow' does not found on the conf path: "
                f"{test_path / 'conf'}."
            ),
        },
    }

    # NOTE: Raise with job execution raise failed status from execution.
    stage: Stage = TriggerStage.model_validate(
        {
            "name": "Trigger raise with failed status",
            "trigger": "wf-run-python-raise",
            "params": {},
        }
    )
    rs: Result = stage.handler_execute(params={})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "StageError",
            "message": (
                "Trigger workflow was failed with:\n"
                "Job execution, 'first-job', was failed."
            ),
        },
    }


def test_trigger_stage_exec_cancel():
    stage: Stage = TriggerStage.model_validate(
        {
            "name": "Trigger to raise workflow",
            "trigger": "wf-run-python-raise",
            "params": {},
        }
    )
    event = MockEvent(n=0)
    rs: Result = stage.handler_execute(params={}, event=event)
    assert rs.status == CANCEL
    assert rs.context == {
        "status": CANCEL,
        "errors": {
            "name": "StageCancelError",
            "message": "Trigger workflow was cancel.",
        },
    }
