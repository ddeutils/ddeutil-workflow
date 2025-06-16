from datetime import datetime

import pytest
from ddeutil.workflow import WorkflowError
from ddeutil.workflow.conf import config
from ddeutil.workflow.result import SUCCESS, Result
from ddeutil.workflow.workflow import (
    NORMAL,
    Workflow,
)


def test_workflow_validate_release():
    workflow: Workflow = Workflow.model_validate(
        {"name": "wf-common-not-set-event"}
    )
    assert workflow.validate_release(datetime.now())
    assert workflow.validate_release(datetime(2025, 5, 1, 12, 1))
    assert workflow.validate_release(datetime(2025, 5, 1, 11, 12))
    assert workflow.validate_release(datetime(2025, 5, 1, 10, 25, 59, 150))

    workflow: Workflow = Workflow.model_validate(
        {
            "name": "wf-common-validate",
            "on": {
                "schedule": [
                    {"cronjob": "*/3 * * * *", "timezone": "Asia/Bangkok"},
                ],
            },
        }
    )
    assert workflow.validate_release(datetime(2025, 5, 1, 1, 9))

    with pytest.raises(WorkflowError):
        workflow.validate_release(datetime(2025, 5, 1, 1, 10))

    with pytest.raises(WorkflowError):
        workflow.validate_release(datetime(2025, 5, 1, 1, 1))

    assert workflow.validate_release(datetime(2025, 5, 1, 1, 3))
    assert workflow.validate_release(datetime(2025, 5, 1, 1, 3, 10, 100))

    workflow: Workflow = Workflow.model_validate(
        {
            "name": "wf-common-validate",
            "on": {
                "schedule": [
                    {"cronjob": "* * * * *", "timezone": "Asia/Bangkok"},
                ],
            },
        }
    )

    assert workflow.validate_release(datetime(2025, 5, 1, 1, 9))
    assert workflow.validate_release(datetime(2025, 5, 1, 1, 10))
    assert workflow.validate_release(datetime(2025, 5, 1, 1, 1))
    assert workflow.validate_release(datetime(2025, 5, 1, 1, 3))
    assert workflow.validate_release(datetime(2025, 5, 1, 1, 3, 10, 100))


def test_workflow_release():
    workflow: Workflow = Workflow.model_validate(
        obj={
            "name": "wf-scheduling-common",
            "jobs": {
                "first-job": {
                    "stages": [
                        {"name": "First Stage", "id": "first-stage"},
                        {"name": "Second Stage", "id": "second-stage"},
                    ]
                }
            },
            "extra": {"enable_write_audit": False},
        }
    )
    release: datetime = datetime.now().replace(second=0, microsecond=0)
    rs: Result = workflow.release(
        release=release,
        params={"asat-dt": datetime(2024, 10, 1)},
    )
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "params": {"asat-dt": datetime(2024, 10, 1, 0, 0)},
        "release": {
            "type": NORMAL,
            "logical_date": release,
        },
        "jobs": {
            "first-job": {
                "status": SUCCESS,
                "stages": {
                    "first-stage": {
                        "outputs": {},
                        "status": SUCCESS,
                    },
                    "second-stage": {
                        "outputs": {},
                        "status": SUCCESS,
                    },
                },
            },
        },
    }


def test_workflow_release_with_datetime():
    workflow: Workflow = Workflow.model_validate(
        obj={
            "name": "wf-scheduling-common",
            "jobs": {
                "first-job": {
                    "stages": [
                        {"name": "First Stage", "id": "first-stage"},
                        {"name": "Second Stage", "id": "second-stage"},
                    ]
                }
            },
            "extra": {"enable_write_audit": False},
        }
    )
    dt: datetime = datetime.now(tz=config.tz).replace(second=0, microsecond=0)
    rs: Result = workflow.release(
        release=dt,
        params={"asat-dt": datetime(2024, 10, 1)},
    )
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "params": {"asat-dt": datetime(2024, 10, 1, 0, 0)},
        "release": {
            "type": NORMAL,
            "logical_date": dt.replace(tzinfo=None),
        },
        "jobs": {
            "first-job": {
                "status": SUCCESS,
                "stages": {
                    "first-stage": {
                        "outputs": {},
                        "status": SUCCESS,
                    },
                    "second-stage": {
                        "outputs": {},
                        "status": SUCCESS,
                    },
                },
            },
        },
    }
