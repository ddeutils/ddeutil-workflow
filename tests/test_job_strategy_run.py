from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event
from unittest import mock

import pytest
from ddeutil.workflow.conf import Config
from ddeutil.workflow.exceptions import JobException, StageException
from ddeutil.workflow.job import Job
from ddeutil.workflow.scheduler import Workflow
from ddeutil.workflow.utils import Result


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
def test_job_exec_strategy_fail_fast():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-python-raise-for-job"
    )
    job: Job = workflow.job("final-job")

    rs = job.execute({})
    print(rs.context)


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
