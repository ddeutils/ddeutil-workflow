from datetime import datetime

import pytest
import yaml
from ddeutil.workflow import Crontab, Schedule, Workflow, WorkflowTask
from pydantic import ValidationError

from .utils import dump_yaml_context


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


def test_schedule_from_conf_raise(test_path):
    test_file = test_path / "conf/demo/03_schedule_raise.yml"

    with test_file.open(mode="w") as f:
        yaml.dump(
            {
                "schedule-raise-wf": {
                    "type": "Crontab",
                    "workflows": [
                        {"name": "wf-scheduling"},
                    ],
                }
            },
            f,
        )

    with pytest.raises(ValueError):
        Schedule.from_conf("schedule-raise-wf")

    with pytest.raises(ValueError):
        Schedule.from_conf("schedule-raise-wf", path=test_path / "conf")

    with test_file.open(mode="w") as f:
        yaml.dump(
            {
                "schedule-raise-wf": {
                    "type": "Schedule",
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
        Schedule.from_conf("schedule-raise-wf")

    with pytest.raises(TypeError):
        Schedule.from_conf("schedule-raise-wf", path=test_path / "conf")

    with test_file.open(mode="w") as f:
        yaml.dump(
            {
                "schedule-raise-wf": {
                    "type": "Schedule",
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
        Schedule.from_conf("schedule-raise-wf")

    with pytest.raises(ValidationError):
        Schedule.from_conf("schedule-raise-wf", path=test_path / "conf")

    test_file.unlink(missing_ok=True)


def test_schedule_default_on(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/03_99_schedule_default_on.yml",
        data="""
        tmp-schedule-default-wf:
          type: Schedule
          workflows:
            - name: 'wf-scheduling'
              params:
                asat-dt: "${{ release.logical_date }}"
        """,
    ):
        schedule = Schedule.from_conf("tmp-schedule-default-wf")
        for sch_wf in schedule.workflows:
            assert sch_wf.on == []

        schedule = Schedule.from_conf(
            "tmp-schedule-default-wf", path=test_path / "conf"
        )
        for sch_wf in schedule.workflows:
            assert sch_wf.on == []


def test_schedule_remove_workflow_task():
    pipeline_tasks: list[WorkflowTask] = []
    start_date: datetime = datetime(2024, 1, 1, 1)

    wf: Workflow = Workflow.from_conf("wf-scheduling")
    for on in wf.on:
        pipeline_tasks.append(
            WorkflowTask(
                alias=wf.name,
                workflow=wf,
                runner=on.generate(start_date),
                values={"asat-dt": "${{ release.logical_date }}"},
            )
        )
    assert 2 == len(pipeline_tasks)

    wf: Workflow = Workflow.from_conf("wf-scheduling")
    for on in wf.on:
        pipeline_tasks.remove(
            WorkflowTask(
                alias=wf.name,
                workflow=wf,
                runner=on.generate(start_date),
                values={"asat-dt": "${{ release.logical_date }}"},
            )
        )

    assert 0 == len(pipeline_tasks)

    wf: Workflow = Workflow.from_conf("wf-scheduling")
    for on in wf.on:
        pipeline_tasks.append(
            WorkflowTask(
                alias=wf.name,
                workflow=wf,
                runner=on.generate(start_date),
                values={"asat-dt": "${{ release.logical_date }}"},
            )
        )

    remover = WorkflowTask(
        alias=wf.name,
        workflow=wf,
        runner=Crontab.from_conf(name="every_minute_bkk").generate(start_date),
        values={"asat-dt": "${{ release.logical_date }}"},
    )
    pipeline_tasks.remove(remover)
    assert 1 == len(pipeline_tasks)
