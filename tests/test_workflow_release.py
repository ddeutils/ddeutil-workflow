from datetime import datetime

from ddeutil.workflow.conf import config
from ddeutil.workflow.result import SUCCESS, Result
from ddeutil.workflow.workflow import (
    Release,
    ReleaseType,
    Workflow,
)


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
    release: Release = Release.from_dt(datetime.now())
    rs: Result = workflow.release(
        release=release,
        params={"asat-dt": datetime(2024, 10, 1)},
    )
    assert rs.status == SUCCESS
    assert rs.context == {
        "params": {"asat-dt": datetime(2024, 10, 1, 0, 0)},
        "release": {
            "type": ReleaseType.DEFAULT,
            "logical_date": release.date,
        },
        "jobs": {
            "first-job": {
                "stages": {
                    "first-stage": {"outputs": {}},
                    "second-stage": {"outputs": {}},
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
        "params": {"asat-dt": datetime(2024, 10, 1, 0, 0)},
        "release": {
            "type": ReleaseType.DEFAULT,
            "logical_date": dt.replace(tzinfo=None),
        },
        "jobs": {
            "first-job": {
                "stages": {
                    "first-stage": {"outputs": {}},
                    "second-stage": {"outputs": {}},
                },
            },
        },
    }
