from datetime import datetime
from unittest import mock

import pytest
from ddeutil.workflow import Workflow
from ddeutil.workflow.conf import Config, config
from ddeutil.workflow.exceptions import WorkflowException
from ddeutil.workflow.result import Result

from .utils import dump_yaml_context


@pytest.mark.poke
@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_poke(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_poke.yml",
        data="""
        tmp-wf-scheduling-minute:
          type: Workflow
          on:
            - cronjob: '* * * * *'
              timezone: "Asia/Bangkok"
          params: {"asat-dt": "datetime"}
          jobs:
            condition-job:
              stages:
                - name: "Empty stage"
                - name: "Call-out"
                  echo: "Hello ${{ params.asat-dt | fmt('%Y-%m-%d') }}"
        """,
    ):
        workflow = Workflow.from_loader(name="tmp-wf-scheduling-minute")

        # NOTE: Poking with the current datetime.
        results: list[Result] = workflow.poke(
            params={"asat-dt": datetime(2024, 1, 1)}
        )

        # FIXME: The result that return from this test is random between 1 and 2
        # NOTE: Respec the result from poking should have only 1 result.
        assert len(results) == 1

        # NOTE: Check datatype of results should be list of Result.
        assert isinstance(results[0], Result)
        assert results[0].status == 0
        assert results[0].context == {
            "params": {"asat-dt": datetime(2024, 1, 1)},
            "release": {
                "status": "success",
                "type": "release",
                # NOTE: This value return with the current datetime.
                "logical_date": results[0].context["release"]["logical_date"],
                "release": results[0].context["release"]["release"],
            },
            "outputs": {
                "jobs": {
                    "condition-job": {
                        "matrix": {},
                        "stages": {
                            "6708019737": {"outputs": {}},
                            "0663452000": {"outputs": {}},
                        },
                    },
                },
            },
        }

        # NOTE: Respec the run_id does not equal to the parent_run_id.
        assert results[0].run_id != results[0].parent_run_id


@pytest.mark.poke
@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_poke_no_queue(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_poke_no_schedule.yml",
        data="""
        tmp-wf-scheduling-daily:
          type: Workflow
          on:
            - cronjob: "30 3 * * *"
              timezone: "Asia/Bangkok"
          jobs:
            do-nothing:
              stages:
                - name: "Empty stage"
        """,
    ):
        workflow = Workflow.from_loader(name="tmp-wf-scheduling-daily")

        # NOTE: Poking with the current datetime.
        results: list[Result] = workflow.poke(
            params={"asat-dt": datetime(2024, 1, 1)}
        )
        assert results == []


@pytest.mark.poke
def test_workflow_poke_raise():
    workflow = Workflow.from_loader(name="wf-scheduling-common")

    # Raise: If a period value is lower than 0.
    with pytest.raises(WorkflowException):
        workflow.poke(periods=-1)

    # Raise: If a period value is lower than 0.
    with pytest.raises(WorkflowException):
        workflow.poke(periods=-5)


@pytest.mark.poke
@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_poke_with_start_date_and_period(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_poke_with_start_date.yml",
        data="""
        tmp-wf-scheduling-with-name:
          type: Workflow
          on:
            - 'every_minute_bkk'
          params: {name: str}
          jobs:
            first-job:
              stages:
                - name: "Hello stage"
                  echo: "Hello ${{ params.name | title }}"
        """,
    ):
        workflow = Workflow.from_loader(name="tmp-wf-scheduling-with-name")

        # NOTE: Poking with specific start datetime.
        results: list[Result] = workflow.poke(
            start_date=datetime(2024, 1, 1, 0, 0, 15, tzinfo=config.tz),
            periods=2,
            params={"name": "FOO"},
        )
        assert len(results) == 2
        assert results[0].parent_run_id == results[1].parent_run_id
        assert results[0].context["release"]["logical_date"] == datetime(
            2024, 1, 1, 0, 1, tzinfo=config.tz
        )
        assert results[1].context["release"]["logical_date"] == datetime(
            2024, 1, 1, 0, 2, tzinfo=config.tz
        )


@pytest.mark.poke
@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_poke_no_on(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_poke_no_on.yml",
        data="""
        tmp-wf-poke-no-on:
          type: Workflow
          params: {"name": str}
          jobs:
            first-job:
              stages:
                - name: Echo
                  echo: "Hello ${{ params.name }}"
        """,
    ):
        workflow = Workflow.from_loader(name="tmp-wf-poke-no-on")
        assert [] == workflow.poke(params={"name": "FOO"})
