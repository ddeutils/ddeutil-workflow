from datetime import datetime
from unittest import mock

from ddeutil.workflow.__cron import CronRunner
from ddeutil.workflow.conf import Config
from ddeutil.workflow.on import On
from ddeutil.workflow.result import Result
from ddeutil.workflow.workflow import Workflow, WorkflowTaskData

from .utils import dump_yaml_context


def test_workflow_task_data():
    workflow: Workflow = Workflow.from_loader(name="wf-scheduling-common")
    runner = workflow.on[0].generate(datetime(2024, 1, 1, 1))

    task: WorkflowTaskData = WorkflowTaskData(
        alias=workflow.name,
        workflow=workflow,
        runner=runner,
        params={"asat-dt": datetime(2024, 1, 1, 1)},
    )

    assert task != datetime(2024, 1, 1, 1)
    assert task == WorkflowTaskData(
        alias=workflow.name,
        workflow=workflow,
        runner=runner,
        params={},
    )


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_task_data_release(test_path):
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
            "demo": [
                datetime(2024, 1, 1, 1, 0, tzinfo=runner.tz),
                datetime(2024, 1, 1, 1, 1, tzinfo=runner.tz),
                datetime(2024, 1, 1, 1, 2, tzinfo=runner.tz),
                datetime(2024, 1, 1, 1, 4, tzinfo=runner.tz),
            ]
        }

        task: WorkflowTaskData = WorkflowTaskData(
            alias="demo",
            workflow=workflow,
            runner=runner,
            params={"name": "foo"},
        )

        rs: Result = task.release(queue=queue)
        assert rs.status == 0
        assert rs.context == {
            "params": {"name": "foo"},
            "release": {
                "status": "success",
                "logical_date": datetime(2024, 1, 1, 1, 3, tzinfo=runner.tz),
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

        # NOTE: Validate len of queue should added next running date from the
        #   release method.
        assert len(queue["demo"]) == 5
        assert datetime(2024, 1, 1, 1, 5, tzinfo=runner.tz) in queue["demo"]
        print(queue)
