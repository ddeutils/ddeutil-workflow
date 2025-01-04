from datetime import datetime
from unittest import mock

from ddeutil.workflow.__cron import CronRunner
from ddeutil.workflow.conf import Config, FileLog
from ddeutil.workflow.cron import On
from ddeutil.workflow.result import Result
from ddeutil.workflow.workflow import Workflow, WorkflowQueue, WorkflowTask

from .utils import dump_yaml_context


def test_workflow_task():
    workflow: Workflow = Workflow.from_loader(name="wf-scheduling-common")
    runner = workflow.on[0].generate(datetime(2024, 1, 1, 1))

    task: WorkflowTask = WorkflowTask(
        alias=workflow.name,
        workflow=workflow,
        runner=runner,
        values={"asat-dt": datetime(2024, 1, 1, 1)},
    )

    assert task != datetime(2024, 1, 1, 1)
    assert task == WorkflowTask(
        alias=workflow.name,
        workflow=workflow,
        runner=runner,
        values={},
    )


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_task_queue(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_task_data_release.yml",
        data="""
        tmp-wf-task-data-release:
          type: ddeutil.workflow.Workflow
          params: {name: str}
          jobs:
            first-job:
              stages:
                - name: "Hello stage"
                  echo: "Hello ${{ params.name | title }}"
        """,
    ):
        workflow = Workflow.from_loader(name="tmp-wf-task-data-release")
        runner: CronRunner = On.from_loader("every_minute_bkk").generate(
            datetime(2024, 1, 1, 1)
        )
        queue = {
            "demo": WorkflowQueue.from_list(
                [
                    datetime(2024, 1, 1, 1, 0, tzinfo=runner.tz),
                    datetime(2024, 1, 1, 1, 1, tzinfo=runner.tz),
                    datetime(2024, 1, 1, 1, 2, tzinfo=runner.tz),
                    datetime(2024, 1, 1, 1, 4, tzinfo=runner.tz),
                ]
            ),
        }

        task: WorkflowTask = WorkflowTask(
            alias="demo",
            workflow=workflow,
            runner=runner,
            values={"name": "foo"},
        )

        task.queue(
            end_date=datetime(2024, 2, 1, 1, 0, tzinfo=runner.tz),
            queue=queue["demo"],
            log=FileLog,
        )

        assert len(queue["demo"].queue) == 5


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_task_release(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_task_data_release.yml",
        data="""
        tmp-wf-task-data-release:
          type: ddeutil.workflow.Workflow
          params: {name: str}
          jobs:
            first-job:
              stages:
                - name: "Hello stage"
                  echo: "Hello ${{ params.name | title }}"
        """,
    ):
        workflow = Workflow.from_loader(name="tmp-wf-task-data-release")
        runner: CronRunner = On.from_loader("every_minute_bkk").generate(
            datetime(2024, 1, 1, 1)
        )
        queue = {"demo": WorkflowQueue()}

        task: WorkflowTask = WorkflowTask(
            alias="demo",
            workflow=workflow,
            runner=runner,
            values={"name": "foo"},
        )

        rs: Result = task.release(queue=queue["demo"])
        assert rs.status == 0
        assert rs.context == {
            "params": {"name": "foo"},
            "release": {
                "status": "success",
                "logical_date": datetime(2024, 1, 1, 1, tzinfo=runner.tz),
            },
            "outputs": {
                "jobs": {
                    "first-job": {
                        "matrix": {},
                        "stages": {"9818133124": {"outputs": {}}},
                    },
                },
            },
        }


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_task_release_long_running(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_task_data_release_long_run.yml",
        data="""
        tmp-wf-task-data-release-long-run:
          type: ddeutil.workflow.Workflow
          params: {name: str}
          jobs:
            first-job:
              stages:
                - name: "Hello stage"
                  echo: "Hello ${{ params.name | title }}"
                  sleep: 60
        """,
    ):
        workflow = Workflow.from_loader(
            name="tmp-wf-task-data-release-long-run"
        )
        runner: CronRunner = On.from_loader("every_minute_bkk").generate(
            datetime(2024, 1, 1, 1)
        )
        queue = {
            "demo": WorkflowQueue.from_list(
                [
                    datetime(2024, 1, 1, 1, 0, tzinfo=runner.tz),
                    datetime(2024, 1, 1, 1, 2, tzinfo=runner.tz),
                ]
            ),
        }

        task: WorkflowTask = WorkflowTask(
            alias="demo",
            workflow=workflow,
            runner=runner,
            values={"name": "foo"},
        )

        rs: Result = task.release(queue=queue["demo"])
        assert rs.status == 0
        print(queue)
