from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event
from unittest import mock

import pytest
from ddeutil.core import getdot
from ddeutil.workflow.conf import Config
from ddeutil.workflow.exceptions import JobException, StageException
from ddeutil.workflow.job import Job
from ddeutil.workflow.utils import Result
from ddeutil.workflow.workflow import Workflow


def test_job_exec_strategy_raise():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-python-raise-for-job"
    )
    job: Job = workflow.job("first-job")

    with mock.patch.object(Config, "job_raise_error", False):
        rs: Result = job.execute_strategy({}, {})
        assert isinstance(rs.context["1354680202"]["error"], StageException)
        assert rs.status == 1

    with pytest.raises(JobException):
        job.execute_strategy({}, {})


@mock.patch.object(Config, "job_raise_error", True)
@mock.patch.object(Config, "stage_raise_error", False)
def test_job_exec_strategy():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-python-raise-for-job"
    )
    job: Job = workflow.job("final-job")
    rs = job.execute_strategy({"name": "foo"}, {})
    assert rs.context == {
        "5027535057": {
            "matrix": {"name": "foo"},
            "stages": {
                "1772094681": {"outputs": {}},
                "raise-error": {
                    "outputs": {
                        "error": getdot(
                            "5027535057.stages.raise-error.outputs.error",
                            rs.context,
                        ),
                        "error_message": (
                            "ValueError: Testing raise error inside PyStage!!!"
                        ),
                    },
                },
                "7761132585": {"outputs": {}},
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
            job.execute_strategy, {}, {}, event=event
        )
        event.set()

    return_value: Result = future.result()
    assert return_value.context["1354680202"]["error_message"] == (
        "Job strategy was canceled from trigger event that had stopped before "
        "execution."
    )