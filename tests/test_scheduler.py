from ddeutil.workflow import Workflow
from ddeutil.workflow.on import On
from ddeutil.workflow.scheduler import Schedule, WorkflowTask
from ddeutil.workflow.utils import Loader


def test_scheduler_model():
    schedule = Schedule.from_loader("schedule-wf")
    print(schedule)


def test_scheduler_loader_find_schedule():
    for finding in Loader.finds(Schedule, excluded=[]):
        print(finding)


def test_scheduler_remove_wf_task():
    queue = []
    running = []
    pipeline_tasks: list[WorkflowTask] = []
    wf: Workflow = Workflow.from_loader("wf-scheduling", externals={})
    for on in wf.on:
        pipeline_tasks.append(
            WorkflowTask(
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
            WorkflowTask(
                workflow=wf,
                on=on,
                params={"asat-dt": "${{ release.logical_date }}"},
                queue=["test"],
                running=["foo"],
            )
        )

    assert 0 == len(pipeline_tasks)

    wf: Workflow = Workflow.from_loader("wf-scheduling", externals={})
    for on in wf.on:
        pipeline_tasks.append(
            WorkflowTask(
                workflow=wf,
                on=on,
                params={"asat-dt": "${{ release.logical_date }}"},
                queue=queue,
                running=running,
            )
        )

    remover = WorkflowTask(
        workflow=wf,
        on=On.from_loader(name="every_minute_bkk", externals={}),
        params={"asat-dt": "${{ release.logical_date }}"},
        queue=[1, 2, 3],
        running=[1],
    )
    pipeline_tasks.remove(remover)
    assert 1 == len(pipeline_tasks)
