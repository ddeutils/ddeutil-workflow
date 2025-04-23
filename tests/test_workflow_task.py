from datetime import datetime
from unittest import mock

import pytest
from ddeutil.workflow import SUCCESS, Config, CronRunner, FileAudit, On, Result
from ddeutil.workflow.workflow import (
    ReleaseQueue,
    ReleaseType,
    Workflow,
    WorkflowTask,
)

from .utils import dump_yaml_context


def test_workflow_task():
    workflow: Workflow = Workflow.model_validate(
        obj={
            "name": "wf-scheduling-common",
            "params": {"asat-dt": "datetime"},
            "on": [
                {"cronjob": "*/3 * * * *", "timezone": "Asia/Bangkok"},
            ],
            "jobs": {
                "condition-job": {
                    "stages": [
                        {"name": "Empty Stage"},
                        {
                            "name": "Call Out",
                            "id": "call-out",
                            "echo": "Hello ${{ params.asat-dt | fmt('%Y-%m-%d') }}",
                        },
                    ]
                }
            },
        }
    )
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

    assert repr(task) == (
        "WorkflowTask(alias='wf-scheduling-common', "
        "workflow='wf-scheduling-common', "
        "runner=CronRunner(CronJob('*/3 * * * *'), 2024-01-01 01:00:00, "
        "tz='Asia/Bangkok'), values={'asat-dt': "
        "datetime.datetime(2024, 1, 1, 1, 0)})"
    )

    # NOTE: Raise because the WorkflowTask does not implement the order property
    with pytest.raises(TypeError):
        assert task < WorkflowTask(
            alias=workflow.name,
            workflow=workflow,
            runner=runner,
            values={},
        )


@mock.patch.object(Config, "enable_write_audit", False)
def test_workflow_task_queue(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_task_data_release.yml",
        data="""
        tmp-wf-task-data-release:
          type: Workflow
          params: {name: str}
          jobs:
            first-job:
              stages:
                - name: "Hello stage"
                  echo: "Hello ${{ params.name | title }}"
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-task-data-release")
        runner: CronRunner = On.from_conf("every_minute_bkk").generate(
            datetime(2024, 1, 1, 1)
        )
        queue = {
            "demo": ReleaseQueue.from_list(
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
            audit=FileAudit,
        )

        assert len(queue["demo"].queue) == 5


@mock.patch.object(Config, "enable_write_audit", False)
def test_workflow_task_release(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_task_data_release.yml",
        data="""
        tmp-wf-task-data-release:
          type: Workflow
          params: {name: str}
          jobs:
            first-job:
              stages:
                - name: "Hello stage"
                  echo: "Hello ${{ params.name | title }}"
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-task-data-release")
        runner: CronRunner = On.from_conf("every_minute_bkk").generate(
            datetime(2024, 1, 1, 1)
        )
        queue = {"demo": ReleaseQueue()}

        task: WorkflowTask = WorkflowTask(
            alias="demo",
            workflow=workflow,
            runner=runner,
            values={"name": "foo"},
        )

        rs: Result = task.release(queue=queue["demo"])
        assert rs.status == SUCCESS
        assert rs.context == {
            "params": {"name": "foo"},
            "release": {
                "type": ReleaseType.DEFAULT,
                "logical_date": datetime(2024, 1, 1, 1),
            },
            "jobs": {
                "first-job": {
                    "stages": {"9818133124": {"outputs": {}}},
                },
            },
        }
        assert len(queue["demo"].complete) == 1

        with pytest.raises(ValueError):
            task.release()

        with pytest.raises(TypeError):
            task.release(
                queue=list[datetime(2024, 1, 1, 1, 0, tzinfo=runner.tz)],
            )

        rs: Result = task.release(
            release=datetime(2024, 1, 1, 1, 1), queue=queue["demo"]
        )
        assert rs.status == SUCCESS
        assert len(queue["demo"].complete) == 2


@mock.patch.object(Config, "enable_write_audit", False)
def test_workflow_task_release_long_running(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_task_data_release_long_run.yml",
        data="""
        tmp-wf-task-data-release-long-run:
          type: Workflow
          params: {name: str}
          jobs:
            first-job:
              stages:
                - name: "Hello stage"
                  echo: "Hello ${{ params.name | title }}"
                  sleep: 60
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-task-data-release-long-run")
        runner: CronRunner = On.from_conf("every_minute_bkk").generate(
            datetime(2024, 1, 1, 1)
        )
        queue = {
            "demo": ReleaseQueue.from_list(
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
