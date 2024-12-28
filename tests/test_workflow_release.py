from datetime import datetime
from unittest import mock

import pytest
from ddeutil.workflow.conf import Config
from ddeutil.workflow.utils import Result
from ddeutil.workflow.workflow import Workflow, WorkflowRelease


def test_workflow_release_dataclass():
    workflow_release = WorkflowRelease.from_dt(dt=datetime(2024, 1, 1, 1))
    assert repr(workflow_release) == repr("2024-01-01 01:00:00")
    assert str(workflow_release) == "2024-01-01 01:00:00"

    assert workflow_release == datetime(2024, 1, 1, 1)
    assert not workflow_release < datetime(2024, 1, 1, 1)
    assert not workflow_release == 2024010101

    with pytest.raises(TypeError):
        _ = workflow_release < 1


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_release():
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
def test_workflow_release_with_queue():
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
def test_workflow_release_with_start_date():
    workflow: Workflow = Workflow.from_loader(name="wf-scheduling-common")
    start_date: datetime = datetime(2024, 1, 1, 1, 1)
    queue: list[WorkflowRelease] = []

    rs: Result = workflow.release(
        workflow.on[0].next(start_date).date,
        params={"asat-dt": datetime(2024, 10, 1)},
        queue=queue,
    )
    print(rs)
