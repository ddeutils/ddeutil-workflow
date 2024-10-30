from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from ddeutil.workflow.conf import Config
from ddeutil.workflow.scheduler import Schedule, Workflow, WorkflowTaskData


def test_workflow_task_data():
    workflow: Workflow = Workflow.from_loader(name="wf-scheduling-common")
    task: WorkflowTaskData = WorkflowTaskData(
        workflow=workflow,
        on=workflow.on[0],
        params={"asat-dt": datetime(2024, 1, 1, 1)},
        queue={},
        running={},
    )

    assert task != datetime(2024, 1, 1, 1)
    assert task == WorkflowTaskData(
        workflow=workflow,
        on=workflow.on[0],
        params={},
        queue={},
        running={},
    )


def test_schedule_tasks():
    schedule = Schedule.from_loader("schedule-wf")
    queue: dict[str, list[datetime]] = {"wf-scheduling": []}
    running: dict[str, list[datetime]] = {"wf-scheduling": []}

    for wf_task in schedule.tasks(
        datetime(2024, 1, 1, 1),
        queue=queue,
        running=running,
    ):
        assert wf_task.workflow.name == "wf-scheduling"

    task: WorkflowTaskData = schedule.tasks(
        datetime(2024, 1, 1, 1),
        queue=queue,
        running=running,
    )[0]

    assert task != datetime(2024, 1, 1, 1)
    assert task == WorkflowTaskData(
        workflow=Workflow.from_loader(name="wf-scheduling"),
        on=task.on,
        params={},
        queue={},
        running={},
    )


@mock.patch.object(Config, "enable_write_log", False)
def test_schedule_tasks_release():
    schedule = Schedule.from_loader("schedule-common-wf")

    queue: dict[str, list[datetime]] = {"wf-scheduling": []}
    running: dict[str, list[datetime]] = {"wf-scheduling": []}
    for wf_task in schedule.tasks(
        datetime(2024, 1, 1, 1, 2, 30),
        queue=queue,
        running=running,
    ):
        assert wf_task.workflow.name == "wf-scheduling"
        wf_task.release(waiting_sec=60)


@mock.patch.object(Config, "enable_write_log", False)
def test_schedule_tasks_release_skip():
    schedule = Schedule.from_loader("schedule-common-wf")
    queue: dict[str, list[datetime]] = {"wf-scheduling": []}
    running: dict[str, list[datetime]] = {"wf-scheduling": []}

    for wf_task in schedule.tasks(
        datetime(2024, 1, 1, 1),
        queue=queue,
        running=running,
    ):
        assert wf_task.workflow.name == "wf-scheduling"
        wf_task.release(waiting_sec=0)

    assert queue == {
        "wf-scheduling": [
            datetime(2024, 1, 1, 1, tzinfo=ZoneInfo("Asia/Bangkok")),
        ]
    }
    assert running == {"wf-scheduling": []}
