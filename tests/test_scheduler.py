from datetime import datetime

from ddeutil.workflow import Workflow
from ddeutil.workflow.on import On
from ddeutil.workflow.scheduler import Schedule, WorkflowTaskData
from ddeutil.workflow.utils import Loader


def test_scheduler_model():
    schedule = Schedule.from_loader("schedule-wf")
    print(schedule)


def test_scheduler_model_default_on():
    schedule = Schedule.from_loader("schedule-default-wf")
    print(schedule)


def test_scheduler_loader_find_schedule():
    for finding in Loader.finds(Schedule, excluded=[]):
        print(finding)


def test_scheduler_remove_wf_task():
    queue: list[datetime] = []
    running: list[datetime] = []
    pipeline_tasks: list[WorkflowTaskData] = []
    wf: Workflow = Workflow.from_loader("wf-scheduling", externals={})
    for on in wf.on:
        pipeline_tasks.append(
            WorkflowTaskData(
                workflow=wf,
                on=on,
                params={"asat-dt": "${{ release.logical_date }}"},
                queue=queue,
                running=running,
            )
        )
    assert 2 == len(pipeline_tasks)

    wf: Workflow = Workflow.from_loader("wf-scheduling", externals={})
    for on in wf.on:
        pipeline_tasks.remove(
            WorkflowTaskData(
                workflow=wf,
                on=on,
                params={"asat-dt": "${{ release.logical_date }}"},
                queue=[datetime(2024, 1, 1, 12)],
                running=[datetime(2024, 1, 1, 12)],
            )
        )

    assert 0 == len(pipeline_tasks)

    wf: Workflow = Workflow.from_loader("wf-scheduling", externals={})
    for on in wf.on:
        pipeline_tasks.append(
            WorkflowTaskData(
                workflow=wf,
                on=on,
                params={"asat-dt": "${{ release.logical_date }}"},
                queue=queue,
                running=running,
            )
        )

    remover = WorkflowTaskData(
        workflow=wf,
        on=On.from_loader(name="every_minute_bkk", externals={}),
        params={"asat-dt": "${{ release.logical_date }}"},
        queue=[datetime(2024, 1, 1, 12), datetime(2024, 1, 1, 12)],
        running=[datetime(2024, 1, 1, 6)],
    )
    pipeline_tasks.remove(remover)
    assert 1 == len(pipeline_tasks)
