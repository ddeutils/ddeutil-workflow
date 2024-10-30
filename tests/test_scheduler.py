from datetime import datetime

import pytest
import yaml
from ddeutil.workflow import Workflow
from ddeutil.workflow.conf import Loader
from ddeutil.workflow.on import On
from ddeutil.workflow.scheduler import Schedule, WorkflowTaskData
from pydantic import ValidationError


def test_schedule():
    schedule = Schedule(
        desc=(
            """
            This is demo schedule description
                * test
                * foo
                * bar
            """
        ),
    )
    assert schedule.desc == (
        "\nThis is demo schedule description\n    * test\n    * foo\n"
        "    * bar\n"
    )


def test_schedule_from_loader():
    schedule = Schedule.from_loader("schedule-wf")
    print(schedule)

    schedule = Schedule.from_loader("schedule-common-wf")
    print(schedule)


def test_schedule_from_loader_raise(test_path):
    test_file = test_path / "conf/demo/03_schedule_raise.yml"

    with test_file.open(mode="w") as f:
        yaml.dump(
            {
                "schedule-raise-wf": {
                    "type": "ddeutil.workflow.on.On",
                    "workflows": [
                        {"name": "wf-scheduling"},
                    ],
                }
            },
            f,
        )

    with pytest.raises(ValueError):
        Schedule.from_loader("schedule-raise-wf")

    with test_file.open(mode="w") as f:
        yaml.dump(
            {
                "schedule-raise-wf": {
                    "type": "scheduler.Schedule",
                    "workflows": [
                        {
                            "name": "wf-scheduling",
                            "on": [
                                ["every_3_minute_bkk"],
                                ["every_minute_bkk"],
                            ],
                        },
                    ],
                }
            },
            f,
        )

    with pytest.raises(TypeError):
        Schedule.from_loader("schedule-raise-wf")

    with test_file.open(mode="w") as f:
        yaml.dump(
            {
                "schedule-raise-wf": {
                    "type": "scheduler.Schedule",
                    "workflows": [
                        {
                            "name": "wf-scheduling",
                            "on": [
                                "every_3_minute_bkk",
                                "every_3_minute_bkk",
                            ],
                        },
                    ],
                }
            },
            f,
        )

    with pytest.raises(ValidationError):
        Schedule.from_loader("schedule-raise-wf")

    test_file.unlink(missing_ok=True)


def test_schedule_model_default_on():
    schedule = Schedule.from_loader("schedule-default-wf")
    for sch_wf in schedule.workflows:
        assert sch_wf.on == []


def test_schedule_loader_find_schedule():
    for finding in Loader.finds(Schedule, excluded=[]):
        print(finding)


def test_schedule_remove_workflow_task():
    queue: list[datetime] = []
    running: list[datetime] = []
    pipeline_tasks: list[WorkflowTaskData] = []

    wf: Workflow = Workflow.from_loader("wf-scheduling")
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

    wf: Workflow = Workflow.from_loader("wf-scheduling")
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

    wf: Workflow = Workflow.from_loader("wf-scheduling")
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
        on=On.from_loader(name="every_minute_bkk"),
        params={"asat-dt": "${{ release.logical_date }}"},
        queue=[
            datetime(2024, 1, 1, 12),
            datetime(2024, 1, 1, 12),
        ],
        running=[datetime(2024, 1, 1, 6)],
    )
    pipeline_tasks.remove(remover)
    assert 1 == len(pipeline_tasks)
