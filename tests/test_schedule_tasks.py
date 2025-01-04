from datetime import datetime
from unittest import mock

from ddeutil.workflow.conf import Config
from ddeutil.workflow.scheduler import Schedule
from ddeutil.workflow.workflow import Workflow, WorkflowQueue, WorkflowTask

from .utils import dump_yaml_context


def test_schedule_tasks(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/03_99_schedule_tasks.yml",
        data="""
        tmp-schedule-wf-tasks:
          type: scheduler.Schedule
          workflows:
            - name: 'wf-scheduling'
              on: ['every_3_minute_bkk', 'every_minute_bkk']
              params:
                asat-dt: "${{ release.logical_date }}"
        """,
    ):
        schedule: Schedule = Schedule.from_loader("tmp-schedule-wf-tasks")
        queue: dict[str, WorkflowQueue] = {}

        tasks = schedule.tasks(datetime(2024, 1, 1, 1), queue=queue)

        assert len(tasks) == 2

        for task in tasks:
            assert task.workflow.name == "wf-scheduling"

        task: WorkflowTask = tasks[0]

        assert task != datetime(2024, 1, 1, 1)
        assert task == WorkflowTask(
            alias="wf-scheduling",
            workflow=Workflow.from_loader(name="wf-scheduling"),
            runner=task.runner,
            values={},
        )


@mock.patch.object(Config, "enable_write_log", False)
def test_schedule_tasks_release(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/03_99_schedule_tasks_release.yml",
        data="""
        tmp-schedule-common-wf:
          type: scheduler.Schedule
          workflows:
            - name: 'wf-scheduling'
              on: 'every_3_minute_bkk'
              params:
                asat-dt: "${{ release.logical_date }}"
        """,
    ):
        schedule: Schedule = Schedule.from_loader("tmp-schedule-common-wf")
        queue: dict[str, WorkflowQueue] = {}

        for task in schedule.tasks(
            start_date=datetime(2024, 1, 1, 1, 2, 30),
            queue=queue,
        ):
            task.release(queue=queue["wf-scheduling"])

            assert len(queue["wf-scheduling"].complete) == 1

            task.release(queue=queue["wf-scheduling"])

            assert len(queue["wf-scheduling"].complete) == 2
