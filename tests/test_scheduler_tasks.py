from datetime import datetime
from unittest import mock

from ddeutil.workflow.conf import Config
from ddeutil.workflow.scheduler import Schedule
from ddeutil.workflow.workflow import Workflow, WorkflowTaskData


def test_workflow_task_data():
    workflow: Workflow = Workflow.from_loader(name="wf-scheduling-common")
    runner = workflow.on[0].generate(datetime(2024, 1, 1, 1))
    task: WorkflowTaskData = WorkflowTaskData(
        alias=workflow.name,
        workflow=workflow,
        runner=runner,
        params={"asat-dt": datetime(2024, 1, 1, 1)},
    )

    assert task != datetime(2024, 1, 1, 1)
    assert task == WorkflowTaskData(
        alias=workflow.name,
        workflow=workflow,
        runner=runner,
        params={},
    )


def test_schedule_tasks():
    schedule = Schedule.from_loader("schedule-wf")
    queue: dict[str, list[datetime]] = {"wf-scheduling": []}

    for wf_task in schedule.tasks(
        datetime(2024, 1, 1, 1),
        queue=queue,
    ):
        assert wf_task.workflow.name == "wf-scheduling"

    task: WorkflowTaskData = schedule.tasks(
        datetime(2024, 1, 1, 1),
        queue=queue,
    )[0]

    assert task != datetime(2024, 1, 1, 1)
    assert task == WorkflowTaskData(
        alias="wf-scheduling",
        workflow=Workflow.from_loader(name="wf-scheduling"),
        runner=task.runner,
        params={},
    )


@mock.patch.object(Config, "enable_write_log", False)
def test_schedule_tasks_release():
    schedule = Schedule.from_loader("schedule-common-wf")
    queue: dict[str, list[datetime]] = {}

    for task in schedule.tasks(
        start_date=datetime(2024, 1, 1, 1, 2, 30),
        queue=queue,
    ):
        task.release(queue=queue, waiting_sec=60)
        print(task.runner.date)

    print(queue)


@mock.patch.object(Config, "enable_write_log", False)
def test_schedule_tasks_release_skip():
    schedule = Schedule.from_loader("schedule-common-wf")
    queue: dict[str, list[datetime]] = {}

    for wf_task in schedule.tasks(
        datetime(2024, 1, 1, 1),
        queue=queue,
    ):
        assert wf_task.workflow.name == "wf-scheduling"
        wf_task.release(queue=queue, waiting_sec=0)

    assert queue == {"wf-scheduling": []}
