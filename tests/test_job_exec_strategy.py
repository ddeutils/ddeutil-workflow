from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event
from unittest import mock

import pytest
from ddeutil.core import getdot
from ddeutil.workflow.conf import Config
from ddeutil.workflow.exceptions import JobException, StageException
from ddeutil.workflow.job import Job, local_execute_strategy
from ddeutil.workflow.result import Result
from ddeutil.workflow.workflow import Workflow


def test_job_exec_strategy():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-python-raise-for-job"
    )
    job: Job = workflow.job("job-complete")
    rs = local_execute_strategy(job, {"sleep": "0.1"}, {})

    assert rs.context == {
        "9873503202": {
            "matrix": {"sleep": "0.1"},
            "stages": {"success": {"outputs": {"result": "success"}}},
        },
    }


@mock.patch.object(Config, "job_raise_error", True)
@mock.patch.object(Config, "stage_raise_error", False)
def test_job_exec_strategy_catch_stage_error():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-python-raise-for-job"
    )
    job: Job = workflow.job("final-job")
    rs = local_execute_strategy(job, {"name": "foo"}, {})

    assert rs.context == {
        "5027535057": {
            "matrix": {"name": "foo"},
            "stages": {
                "1772094681": {"outputs": {}},
                "raise-error": {
                    "outputs": {},
                    "errors": {
                        "class": getdot(
                            "5027535057.stages.raise-error.errors.class",
                            rs.context,
                        ),
                        "name": "ValueError",
                        "message": "Testing raise error inside PyStage!!!",
                    },
                },
                "7761132585": {"outputs": {}},
            },
        },
    }


@mock.patch.object(Config, "job_raise_error", False)
@mock.patch.object(Config, "stage_raise_error", True)
def test_job_exec_strategy_catch_job_error():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-python-raise-for-job"
    )
    job: Job = workflow.job("final-job")
    rs = local_execute_strategy(job, {"name": "foo"}, {})
    assert rs.context == {
        "5027535057": {
            "matrix": {"name": "foo"},
            "stages": {"1772094681": {"outputs": {}}},
            "errors": {
                "class": rs.context["5027535057"]["errors"]["class"],
                "name": "StageException",
                "message": (
                    "PyStage: \n\tValueError: Testing raise error "
                    "inside PyStage!!!"
                ),
            },
        },
    }


def test_job_exec_strategy_event_set():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-python-raise-for-job"
    )
    job: Job = workflow.job("second-job")
    event = Event()
    with ThreadPoolExecutor(max_workers=1) as executor:
        future: Future = executor.submit(
            local_execute_strategy, job, {}, {}, event=event
        )
        event.set()

    return_value: Result = future.result()
    assert return_value.context["1354680202"]["errors"]["message"] == (
        "Job strategy was canceled from event that had set before strategy "
        "execution."
    )


def test_job_exec_strategy_raise():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-python-raise-for-job"
    )
    job: Job = workflow.job("first-job")

    with mock.patch.object(Config, "job_raise_error", False):
        rs: Result = local_execute_strategy(job, {}, {})
        assert isinstance(
            rs.context["1354680202"]["errors"]["class"], StageException
        )
        assert rs.status == 1

    with pytest.raises(JobException):
        local_execute_strategy(job, {}, {})
