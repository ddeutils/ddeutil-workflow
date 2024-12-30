from datetime import datetime
from unittest import mock

import pytest
from ddeutil.workflow.conf import Config
from ddeutil.workflow.result import Result
from ddeutil.workflow.workflow import Workflow, WorkflowQueue, WorkflowRelease


def test_workflow_queue():
    wf_queue = WorkflowQueue()

    assert not wf_queue.is_queued


def test_workflow_queue_from_list():
    wf_queue = WorkflowQueue.from_list()

    assert not wf_queue.is_queued

    wf_queue = WorkflowQueue.from_list([])

    assert not wf_queue.is_queued

    wf_queue = WorkflowQueue.from_list(
        [datetime(2024, 1, 1, 1), datetime(2024, 1, 2, 1)]
    )

    assert wf_queue.is_queued

    wf_queue = WorkflowQueue.from_list(
        [WorkflowRelease.from_dt(datetime(2024, 1, 1, 1))]
    )

    assert wf_queue.is_queued

    with pytest.raises(TypeError):
        WorkflowQueue.from_list(["20240101"])

    with pytest.raises(TypeError):
        WorkflowQueue.from_list("20240101")

    wf_queue = WorkflowQueue.from_list(
        [datetime(2024, 1, 1, 1), datetime(2024, 1, 2, 1)]
    )

    assert not wf_queue.check_queue(WorkflowRelease.from_dt("2024-01-02"))
    assert wf_queue.check_queue(WorkflowRelease.from_dt("2024-01-02 01:00:00"))


def test_workflow_release():
    workflow_release = WorkflowRelease.from_dt(dt=datetime(2024, 1, 1, 1))

    assert repr(workflow_release) == repr("2024-01-01 01:00:00")
    assert str(workflow_release) == "2024-01-01 01:00:00"

    assert workflow_release == datetime(2024, 1, 1, 1)
    assert not workflow_release < datetime(2024, 1, 1, 1)
    assert not workflow_release == 2024010101

    workflow_release = WorkflowRelease.from_dt(dt="2024-01-01")

    assert repr(workflow_release) == repr("2024-01-01 00:00:00")
    assert str(workflow_release) == "2024-01-01 00:00:00"

    with pytest.raises(TypeError):
        assert workflow_release < 1


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
    print(rs)


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_run_release_with_queue():
    workflow: Workflow = Workflow.from_loader(name="wf-scheduling-common")
    current_date: datetime = datetime.now().replace(second=0, microsecond=0)
    release_date: datetime = workflow.on[0].next(current_date).date

    # NOTE: Start call workflow release method.
    rs: Result = workflow.release(
        release=release_date,
        params={"asat-dt": datetime(2024, 10, 1)},
    )
    assert rs.status == 0
    print(rs)


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_run_release_with_start_date():
    workflow: Workflow = Workflow.from_loader(name="wf-scheduling-common")
    start_date: datetime = datetime(2024, 1, 1, 1, 1)
    queue: list[WorkflowRelease] = []

    rs: Result = workflow.release(
        workflow.on[0].next(start_date).date,
        params={"asat-dt": datetime(2024, 10, 1)},
        queue=queue,
    )
    print(rs)
