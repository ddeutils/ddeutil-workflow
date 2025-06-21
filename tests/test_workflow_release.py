from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from ddeutil.workflow import (
    NORMAL,
    SUCCESS,
    UTC,
    Result,
    Workflow,
    WorkflowError,
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
        run_id="1001",
        runs_metadata={"runs_by": "nobody"},
    )
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "params": {"asat-dt": datetime(2024, 10, 1, 0, 0)},
        "release": {
            "type": NORMAL,
            "logical_date": release.replace(tzinfo=UTC),
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
    dt: datetime = datetime(2025, 1, 18, tzinfo=ZoneInfo("Asia/Bangkok"))
    rs: Result = workflow.release(
        release=dt,
        params={"asat-dt": datetime(2024, 10, 1)},
    )
    assert dt == datetime(2025, 1, 18, tzinfo=ZoneInfo("Asia/Bangkok"))
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "params": {"asat-dt": datetime(2024, 10, 1, 0, 0)},
        "release": {
            "type": NORMAL,
            # NOTE: The date that pass to release method will convert to UTC.
            "logical_date": datetime(2025, 1, 17, 17, tzinfo=UTC),
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
