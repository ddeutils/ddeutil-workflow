from datetime import datetime
from unittest import mock

from ddeutil.workflow.conf import Config
from ddeutil.workflow.result import Result
from ddeutil.workflow.workflow import Release, Workflow, WorkflowQueue


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_run_release():
    workflow: Workflow = Workflow.from_loader(name="wf-scheduling-common")
    current_date: datetime = datetime.now().replace(second=0, microsecond=0)
    release_date: datetime = workflow.on[0].next(current_date).date

    # NOTE: Start call workflow release method.
    rs: Result = workflow.release(
        release=release_date,
        params={"asat-dt": datetime(2024, 10, 1)},
    )
    assert rs.status == 0
    assert rs.context == {
        "params": {"asat-dt": datetime(2024, 10, 1, 0, 0)},
        "release": {
            "status": "success",
            "type": "datetime",
            "logical_date": release_date,
            "release": Release.from_dt(release_date),
        },
        "outputs": {
            "jobs": {
                "condition-job": {
                    "matrix": {},
                    "stages": {
                        "4083404693": {"outputs": {}},
                        "call-out": {"outputs": {}},
                    },
                },
            },
        },
    }


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_run_release_with_queue():
    workflow: Workflow = Workflow.from_loader(name="wf-scheduling-common")
    current_date: datetime = datetime.now().replace(second=0, microsecond=0)
    release_date: datetime = workflow.on[0].next(current_date).date
    queue = WorkflowQueue(running=[Release.from_dt(release_date)])

    # NOTE: Start call workflow release method.
    rs: Result = workflow.release(
        release=release_date,
        params={"asat-dt": datetime(2024, 10, 1)},
        queue=queue,
    )
    assert rs.status == 0
    assert rs.context == {
        "params": {"asat-dt": datetime(2024, 10, 1, 0, 0)},
        "release": {
            "status": "success",
            "type": "datetime",
            "logical_date": release_date,
            "release": Release.from_dt(release_date),
        },
        "outputs": {
            "jobs": {
                "condition-job": {
                    "matrix": {},
                    "stages": {
                        "4083404693": {"outputs": {}},
                        "call-out": {"outputs": {}},
                    },
                },
            },
        },
    }
    assert queue.running == []
    assert queue.complete == [Release.from_dt(release_date)]


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_run_release_with_start_date():
    workflow: Workflow = Workflow.from_loader(name="wf-scheduling-common")
    start_date: datetime = datetime(2024, 1, 1, 1, 1)

    rs: Result = workflow.release(
        release=start_date,
        params={"asat-dt": datetime(2024, 10, 1)},
    )
    assert rs.status == 0
    assert rs.context == {
        "params": {"asat-dt": datetime(2024, 10, 1, 0, 0)},
        "release": {
            "status": "success",
            "type": "datetime",
            "logical_date": start_date,
            "release": Release.from_dt(start_date),
        },
        "outputs": {
            "jobs": {
                "condition-job": {
                    "matrix": {},
                    "stages": {
                        "4083404693": {"outputs": {}},
                        "call-out": {"outputs": {}},
                    },
                },
            },
        },
    }
