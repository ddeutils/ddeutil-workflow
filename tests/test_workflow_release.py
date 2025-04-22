from datetime import datetime

import pytest
from ddeutil.workflow.conf import config
from ddeutil.workflow.result import SUCCESS, Result
from ddeutil.workflow.workflow import (
    Release,
    ReleaseQueue,
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
            "release": release,
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
            "release": Release.from_dt(dt),
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


def test_workflow_release_with_queue():
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
    dt: datetime = datetime.now().replace(second=0, microsecond=0)
    release: Release = Release.from_dt(dt)
    queue = ReleaseQueue(running=[Release.from_dt(dt)])

    # NOTE: Start call workflow release method.
    rs: Result = workflow.release(
        release=release,
        params={"asat-dt": datetime(2024, 10, 1)},
        queue=queue,
    )
    assert rs.status == SUCCESS
    assert rs.context == {
        "params": {"asat-dt": datetime(2024, 10, 1, 0, 0)},
        "release": {
            "type": ReleaseType.DEFAULT,
            "logical_date": release.date,
            "release": release,
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
    assert queue.running == []
    assert queue.complete == [release]


def test_workflow_release_with_queue_raise():
    workflow: Workflow = Workflow(name="wf-scheduling-common")
    dt: datetime = datetime.now().replace(second=0, microsecond=0)

    # NOTE: Raise because the queue is invalid type.
    with pytest.raises(TypeError):
        workflow.release(
            release=dt,
            params={"name": "foo"},
            queue=[Release.from_dt(dt)],
        )

    # NOTE: Raise because the queue is invalid type.
    with pytest.raises(TypeError):
        workflow.release(
            release=dt,
            params={"name": "foo"},
            queue=[],
        )
