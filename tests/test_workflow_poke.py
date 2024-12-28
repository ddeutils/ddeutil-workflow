from datetime import datetime
from unittest import mock

import pytest
from ddeutil.workflow import Workflow
from ddeutil.workflow.conf import Config, config
from ddeutil.workflow.exceptions import WorkflowException
from ddeutil.workflow.utils import Result


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_poke():
    workflow = Workflow.from_loader(name="wf-scheduling-minute")

    # NOTE: Poking with the current datetime.
    results: list[Result] = workflow.poke(
        params={"asat-dt": datetime(2024, 1, 1)}
    )

    print(results)

    # NOTE: Check datatype of results should be list of Result.
    assert isinstance(results[0], Result)


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_poke_no_schedule():
    workflow = Workflow.from_loader(name="wf-scheduling-daily")

    # NOTE: Poking with the current datetime.
    results: list[Result] = workflow.poke(
        params={"asat-dt": datetime(2024, 1, 1)}
    )
    assert results == []


def test_workflow_poke_raise():
    workflow = Workflow.from_loader(name="wf-scheduling-common")

    # Raise: If a period value is lower than 0.
    with pytest.raises(WorkflowException):
        workflow.poke(periods=-1)


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_poke_with_start_date():
    workflow = Workflow.from_loader(name="wf-scheduling-with-name")

    # NOTE: Poking with specific start datetime.
    results: list[Result] = workflow.poke(
        start_date=datetime(2024, 1, 1, 0, 0, 15, tzinfo=config.tz),
        periods=2,
        params={"name": "FOO"},
    )
    print(results)


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_poke_no_on():
    workflow = Workflow.from_loader(name="wf-params-required")
    assert [] == workflow.poke(params={"name": "FOO"})


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_poke_with_release_params():
    wf = Workflow.from_loader(name="wf-scheduling", externals={})
    wf.poke(params={"asat-dt": "${{ release.logical_date }}"})
