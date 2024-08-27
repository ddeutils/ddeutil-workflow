from ddeutil.workflow.on import On
from ddeutil.workflow.pipeline import Pipeline
from ddeutil.workflow.scheduler import PipelineTask, Schedule
from ddeutil.workflow.utils import Loader


def test_scheduler_model():
    schedule = Schedule.from_loader("schedule-pipe")
    print(schedule)


def test_scheduler_loader_find_schedule():
    for finding in Loader.finds(Schedule, excluded=[]):
        print(finding)


def test_scheduler_remove_pipe_task():
    queue = []
    running = []
    pipeline_tasks: list[PipelineTask] = []
    pipe: Pipeline = Pipeline.from_loader("pipe-scheduling", externals={})
    for on in pipe.on:
        pipeline_tasks.append(
            PipelineTask(
                pipeline=pipe,
                on=on,
                params={"asat-dt": "${{ release.logical_date }}"},
                queue=queue,
                running=running,
            )
        )
    assert 2 == len(pipeline_tasks)

    pipe: Pipeline = Pipeline.from_loader("pipe-scheduling", externals={})
    for on in pipe.on:
        pipeline_tasks.remove(
            PipelineTask(
                pipeline=pipe,
                on=on,
                params={"asat-dt": "${{ release.logical_date }}"},
                queue=["test"],
                running=["foo"],
            )
        )

    assert 0 == len(pipeline_tasks)

    pipe: Pipeline = Pipeline.from_loader("pipe-scheduling", externals={})
    for on in pipe.on:
        pipeline_tasks.append(
            PipelineTask(
                pipeline=pipe,
                on=on,
                params={"asat-dt": "${{ release.logical_date }}"},
                queue=queue,
                running=running,
            )
        )

    remover = PipelineTask(
        pipeline=pipe,
        on=On.from_loader(name="every_minute_bkk", externals={}),
        params={"asat-dt": "${{ release.logical_date }}"},
        queue=[1, 2, 3],
        running=[1],
    )
    pipeline_tasks.remove(remover)
    assert 1 == len(pipeline_tasks)
