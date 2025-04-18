from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

import pytest
from ddeutil.workflow.conf import Config
from ddeutil.workflow.scheduler import ScheduleWorkflow
from ddeutil.workflow.workflow import Release, ReleaseQueue
from pydantic import ValidationError

from .utils import dump_yaml_context


def test_schedule_workflow():
    schedule_wf = ScheduleWorkflow(name="demo_workflow")

    assert schedule_wf.name == "demo_workflow"
    assert schedule_wf.alias == "demo_workflow"

    schedule_wf = ScheduleWorkflow(name="demo", alias="example", on=[])

    assert schedule_wf.name == "demo"
    assert schedule_wf.alias == "example"

    schedule_wf = ScheduleWorkflow(name="demo", on=[{"cronjob": "2 * * * *"}])
    assert len(schedule_wf.on) == 1

    # NOTE: Raise if it does not pass any data to ScheduleWorkflow
    with pytest.raises(ValidationError):
        ScheduleWorkflow.model_validate({})


def test_schedule_workflow_pass_on_loader():
    schedule_wf = ScheduleWorkflow(
        name="wf-scheduling",
        on=["every_3_minute_bkk", "every_minute_bkk"],
    )
    assert schedule_wf.alias == "wf-scheduling"

    schedule_wf = ScheduleWorkflow(
        alias="wf-scheduling-morning",
        name="wf-scheduling",
        on=["every_3_minute_bkk", "every_minute_bkk"],
    )
    assert schedule_wf.alias == "wf-scheduling-morning"


def test_schedule_workflow_raise_on(test_path):
    # NOTE: Raise if values on the on field reach the maximum value.
    with pytest.raises(ValidationError):
        ScheduleWorkflow(
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
        ScheduleWorkflow(
            name="tmp-wf-on-duplicate",
            on=[
                {"cronjob": "2 * * * *"},
                {"cronjob": "2 * * * *"},
            ],
        )

    # NOTE: Raise if values on has not valid type.
    with pytest.raises(TypeError):
        ScheduleWorkflow(
            name="tmp-wf-on-type-not-valid",
            on=[
                [{"cronjob": "2 * * * *"}],
                20240101,
            ],
        )


@mock.patch.object(Config, "enable_write_audit", False)
def test_schedule_workflow_tasks(test_path):
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
        test_path / "conf/demo/01_99_wf_test_schedule_wf_tasks.yml",
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
        schedule_wf = ScheduleWorkflow(
            name="tmp-wf-schedule-tasks",
            on=[{"cronjob": "* * * * *", "timezone": "Asia/Bangkok"}],
            params={"name": "Foo"},
        )
        tasks = schedule_wf.tasks(start_date=release_date, queue=queue)

        assert len(tasks) == 1

        task = tasks[0]
        task.release(queue=queue["tmp-wf-schedule-tasks"])
        task.release(queue=queue["tmp-wf-schedule-tasks"])

        assert task.runner.date == datetime(2024, 1, 1, 1, 4, tzinfo=tz)
