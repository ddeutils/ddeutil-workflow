import pytest
from ddeutil.workflow.errors import JobError
from ddeutil.workflow.job import Job, local_execute_strategy
from ddeutil.workflow.result import CANCEL, FAILED, SKIP, SUCCESS
from ddeutil.workflow.workflow import Workflow

from .utils import MockEvent


def test_job_exec_strategy():
    job: Job = Workflow.from_conf(name="wf-run-python-raise-for-job").job(
        "job-complete"
    )
    st, ctx = local_execute_strategy(
        job, {"sleep": "0.1"}, {}, run_id="001", context={}
    )
    assert st == SUCCESS
    assert ctx == {
        "status": SUCCESS,
        "9873503202": {
            "status": SUCCESS,
            "matrix": {"sleep": "0.1"},
            "stages": {
                "success": {"outputs": {"result": "success"}, "status": SUCCESS}
            },
        },
    }


def test_job_exec_strategy_skipped_stage():
    job: Job = Workflow.from_conf(name="wf-run-python-raise-for-job").job(
        "job-stage-condition"
    )
    st, ctx = local_execute_strategy(
        job, {"sleep": "1"}, {}, run_id="001", context={}
    )
    assert st == SUCCESS
    assert ctx == {
        "status": SUCCESS,
        "2150810470": {
            "status": SUCCESS,
            "matrix": {"sleep": "1"},
            "stages": {
                "equal-one": {
                    "status": SUCCESS,
                    "outputs": {"result": "pass-condition"},
                },
                "not-equal-one": {"outputs": {}, "status": SKIP},
            },
        },
    }


def test_job_exec_strategy_catch_stage_error():
    job: Job = Workflow.from_conf("wf-run-python-raise-for-job").job(
        "final-job"
    )

    context = {}
    with pytest.raises(JobError):
        local_execute_strategy(
            job, {"name": "foo"}, {}, run_id="001", context=context
        )

    assert context == {
        "status": FAILED,
        "5027535057": {
            "status": FAILED,
            "matrix": {"name": "foo"},
            "stages": {
                "1772094681": {"outputs": {}, "status": SUCCESS},
                "raise-error": {
                    "status": FAILED,
                    "outputs": {},
                    "errors": {
                        "name": "ValueError",
                        "message": "Testing raise error inside PyStage!!!",
                    },
                },
            },
            "errors": {
                "name": "JobError",
                "message": (
                    "Strategy execution was break because its nested-stage, "
                    "'raise-error', failed."
                ),
            },
        },
    }


def test_job_exec_strategy_catch_job_error():
    job: Job = Workflow.from_conf("wf-run-python-raise-for-job").job(
        "final-job"
    )
    context = {}
    with pytest.raises(JobError):
        local_execute_strategy(
            job, {"name": "foo"}, {}, run_id="001", context=context
        )

    assert context == {
        "status": FAILED,
        "5027535057": {
            "status": FAILED,
            "matrix": {"name": "foo"},
            "stages": {
                "1772094681": {"outputs": {}, "status": SUCCESS},
                "raise-error": {
                    "status": FAILED,
                    "outputs": {},
                    "errors": {
                        "name": "ValueError",
                        "message": "Testing raise error inside PyStage!!!",
                    },
                },
            },
            "errors": {
                "name": "JobError",
                "message": (
                    "Strategy execution was break because its nested-stage, "
                    "'raise-error', failed."
                ),
            },
        },
    }


def test_job_exec_strategy_event_set():
    job: Job = Workflow.from_conf(name="wf-run-python-raise-for-job").job(
        "second-job"
    )
    event = MockEvent(n=0)
    context = {}
    with pytest.raises(JobError):
        local_execute_strategy(
            job, {}, {}, run_id="001", context=context, event=event
        )

    assert context == {
        "status": CANCEL,
        "EMPTY": {
            "status": CANCEL,
            "matrix": {},
            "stages": {},
            "errors": {
                "name": "JobCancelError",
                "message": (
                    "Strategy execution was canceled from the event before "
                    "start stage execution."
                ),
            },
        },
    }


def test_job_exec_strategy_raise():
    job: Job = Workflow.from_conf(name="wf-run-python-raise-for-job").job(
        "first-job"
    )
    context = {}
    with pytest.raises(JobError):
        local_execute_strategy(job, {}, {}, run_id="001", context=context)

    assert context["status"] == FAILED
    assert context == {
        "status": FAILED,
        "EMPTY": {
            "status": FAILED,
            "matrix": {},
            "stages": {
                "raise-error": {
                    "status": FAILED,
                    "outputs": {},
                    "errors": {
                        "name": "ValueError",
                        "message": "Testing raise error inside PyStage!!!",
                    },
                }
            },
            "errors": {
                "name": "JobError",
                "message": (
                    "Strategy execution was break because its nested-stage, "
                    "'raise-error', failed."
                ),
            },
        },
    }
