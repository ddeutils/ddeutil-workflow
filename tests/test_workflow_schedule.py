from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

import pytest
from ddeutil.workflow.conf import Config
from ddeutil.workflow.scheduler import WorkflowSchedule
from ddeutil.workflow.workflow import Release, ReleaseQueue
from pydantic import ValidationError

from .utils import dump_yaml_context


def test_workflow_schedule():
    wf_schedule = WorkflowSchedule(name="demo workflow")

    assert wf_schedule.name == "demo_workflow"
    assert wf_schedule.alias == "demo_workflow"

    wf_schedule = WorkflowSchedule(name="demo", alias="example", on=[])

    assert wf_schedule.name == "demo"
    assert wf_schedule.alias == "example"

    wf_schedule = WorkflowSchedule(name="demo", on=[{"cronjob": "2 * * * *"}])
    assert len(wf_schedule.on) == 1

    # NOTE: Raise if it does not pass any data to WorkflowSchedule
    with pytest.raises(ValidationError):
        WorkflowSchedule.model_validate({})


def test_workflow_schedule_pass_on_loader():
    wf_schedule = WorkflowSchedule(
        name="wf-scheduling",
        on=["every_3_minute_bkk", "every_minute_bkk"],
    )
    assert wf_schedule.alias == "wf-scheduling"

    wf_schedule = WorkflowSchedule(
        alias="wf-scheduling-morning",
        name="wf-scheduling",
        on=["every_3_minute_bkk", "every_minute_bkk"],
    )
    assert wf_schedule.alias == "wf-scheduling-morning"


def test_workflow_schedule_raise_on(test_path):
    # NOTE: Raise if values on the on field reach the maximum value.
    with pytest.raises(ValidationError):
        WorkflowSchedule(
            name="tmp-wf-on-reach-max-value",
            on=[
                {"cronjob": "2 * * * *"},
                {"cronjob": "3 * * * *"},
                {"cronjob": "4 * * * *"},
                {"cronjob": "5 * * * *"},
                {"cronjob": "6 * * * *"},
                {"cronjob": "7 * * * *"},
            ],
        )

    # NOTE: Raise if values on has duplicate values.
    with pytest.raises(ValidationError):
        WorkflowSchedule(
            name="tmp-wf-on-duplicate",
            on=[
                {"cronjob": "2 * * * *"},
                {"cronjob": "2 * * * *"},
            ],
        )

    # NOTE: Raise if values on has not valid type.
    with pytest.raises(TypeError):
        WorkflowSchedule(
            name="tmp-wf-on-type-not-valid",
            on=[
                [{"cronjob": "2 * * * *"}],
                20240101,
            ],
        )


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_schedule_tasks(test_path):
    tz: ZoneInfo = ZoneInfo("Asia/Bangkok")
    release_date: datetime = datetime(2024, 1, 1, 1, tzinfo=tz)
    queue: dict[str, ReleaseQueue] = {
        "tmp-wf-schedule-tasks": ReleaseQueue(
            complete=[
                Release.from_dt(datetime(2024, 1, 1, 1, 0, tzinfo=tz)),
                Release.from_dt(datetime(2024, 1, 1, 1, 1, tzinfo=tz)),
                Release.from_dt(datetime(2024, 1, 1, 1, 3, tzinfo=tz)),
            ]
        )
    }

    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_schedule_tasks.yml",
        data="""
        tmp-wf-schedule-tasks:
          type: Workflow
          params: {name: str}
          jobs:
            first-job:
              stages:
                - name: Echo
                  echo: "Hello ${{ params.name }}"
        """,
    ):
        wf_schedule = WorkflowSchedule(
            name="tmp-wf-schedule-tasks",
            on=[{"cronjob": "* * * * *", "timezone": "Asia/Bangkok"}],
            params={"name": "Foo"},
        )
        tasks = wf_schedule.tasks(start_date=release_date, queue=queue)

        assert len(tasks) == 1

        task = tasks[0]
        task.release(queue=queue["tmp-wf-schedule-tasks"])
        task.release(queue=queue["tmp-wf-schedule-tasks"])

        assert task.runner.date == datetime(2024, 1, 1, 1, 4, tzinfo=tz)
