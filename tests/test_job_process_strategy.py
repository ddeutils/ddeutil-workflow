import pytest
from ddeutil.workflow import CANCEL, FAILED, SKIP, SUCCESS, Workflow, get_trace
from ddeutil.workflow.errors import JobError
from ddeutil.workflow.job import Job, local_process_strategy

from .utils import MockEvent


@pytest.fixture(scope="module")
def trace():
    return get_trace(run_id="001")


def test_job_process_strategy(trace):
    job: Job = Workflow.from_conf(name="wf-run-python-raise-for-job").job(
        "job-complete"
    )
    st, ctx = local_process_strategy(
        job, {"sleep": "0.1"}, {}, trace=trace, context={}
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


def test_job_process_strategy_skipped_stage(trace):
    job: Job = Workflow.from_conf(name="wf-run-python-raise-for-job").job(
        "job-stage-condition"
    )
    st, ctx = local_process_strategy(
        job, {"sleep": "1"}, {}, trace=trace, context={}
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


def test_job_process_strategy_catch_stage_error(trace):
    job: Job = Workflow.from_conf("wf-run-python-raise-for-job").job(
        "final-job"
    )

    context = {}
    with pytest.raises(JobError):
        local_process_strategy(
            job, {"name": "foo"}, {}, trace=trace, context=context
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


def test_job_process_strategy_catch_job_error(trace):
    job: Job = Workflow.from_conf("wf-run-python-raise-for-job").job(
        "final-job"
    )
    context = {}
    with pytest.raises(JobError):
        local_process_strategy(
            job, {"name": "foo"}, {}, trace=trace, context=context
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


def test_job_process_strategy_event_set(trace):
    job: Job = Workflow.from_conf(name="wf-run-python-raise-for-job").job(
        "second-job"
    )
    event = MockEvent(n=0)
    context = {}
    with pytest.raises(JobError):
        local_process_strategy(
            job, {}, {}, trace=trace, context=context, event=event
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


def test_job_process_strategy_raise(trace):
    job: Job = Workflow.from_conf(name="wf-run-python-raise-for-job").job(
        "first-job"
    )
    context = {}
    with pytest.raises(JobError):
        local_process_strategy(job, {}, {}, trace=trace, context=context)

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
