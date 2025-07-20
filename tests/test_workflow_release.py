import shutil
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from ddeutil.workflow import (
    FORCE,
    NORMAL,
    RERUN,
    SKIP,
    SUCCESS,
    UTC,
    EventError,
    Result,
    Workflow,
)


def test_workflow_validate_release():
    workflow: Workflow = Workflow.model_validate(
        {"name": "wf-common-not-set-event"}
    )
    assert workflow.on.validate_dt(datetime.now())
    assert workflow.on.validate_dt(datetime(2025, 5, 1, 12, 1))
    assert workflow.on.validate_dt(datetime(2025, 5, 1, 11, 12))
    assert workflow.on.validate_dt(datetime(2025, 5, 1, 10, 25, 59, 150))

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
    assert workflow.on.validate_dt(datetime(2025, 5, 1, 1, 9))

    with pytest.raises(EventError):
        workflow.on.validate_dt(datetime(2025, 5, 1, 1, 10))

    with pytest.raises(EventError):
        workflow.on.validate_dt(datetime(2025, 5, 1, 1, 1))

    assert workflow.on.validate_dt(datetime(2025, 5, 1, 1, 3))
    assert workflow.on.validate_dt(datetime(2025, 5, 1, 1, 3, 10, 100))

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

    assert workflow.on.validate_dt(datetime(2025, 5, 1, 1, 9))
    assert workflow.on.validate_dt(datetime(2025, 5, 1, 1, 10))
    assert workflow.on.validate_dt(datetime(2025, 5, 1, 1, 1))
    assert workflow.on.validate_dt(datetime(2025, 5, 1, 1, 3))
    assert workflow.on.validate_dt(datetime(2025, 5, 1, 1, 3, 10, 100))


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


def test_workflow_release_with_datetime_force():
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
            "extra": {"enable_write_audit": True},
        }
    )
    dt: datetime = datetime(2025, 1, 18, tzinfo=ZoneInfo("Asia/Bangkok"))
    rs: Result = workflow.release(
        release=dt,
        release_type=FORCE,
        params={"asat-dt": datetime(2024, 10, 1)},
    )
    assert dt == datetime(2025, 1, 18, tzinfo=ZoneInfo("Asia/Bangkok"))
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "params": {"asat-dt": datetime(2024, 10, 1, 0, 0)},
        "release": {
            "type": FORCE,
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


def test_workflow_release_with_datetime(test_path):
    test_audit_skip_path = test_path / "tests_workflow_release_audits"

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
            "extras": {
                "audit_conf": {
                    "type": "file",
                    "path": str(test_audit_skip_path.absolute()),
                }
            },
        }
    )
    dt: datetime = datetime(2025, 1, 18, tzinfo=ZoneInfo("Asia/Bangkok"))
    rs: Result = workflow.release(
        release=dt,
        params={"asat-dt": datetime(2024, 10, 1)},
    )
    assert rs.status == SUCCESS

    rs: Result = workflow.release(
        release=dt,
        params={"asat-dt": datetime(2024, 10, 1)},
    )
    assert rs.status == SKIP
    assert rs.context == {"status": SKIP}

    shutil.rmtree(test_audit_skip_path)


def test_workflow_release_with_auto():
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
            "extra": {"enable_write_audit": True},
        }
    )
    rs: Result = workflow.release(release=datetime.now(), params={})
    assert rs.status == SUCCESS
    assert rs.context["release"]["type"] == NORMAL
    assert rs.context["release"]["logical_date"].tzinfo == UTC


def test_workflow_release_rerun():
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
            "extra": {"enable_write_audit": True},
        }
    )
    with pytest.raises(NotImplementedError):
        workflow.release(release=datetime.now(), params={}, release_type=RERUN)
