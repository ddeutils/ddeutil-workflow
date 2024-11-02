from unittest import mock

import pytest
from ddeutil.workflow import Job, Workflow
from ddeutil.workflow.conf import Config
from ddeutil.workflow.exceptions import JobException
from ddeutil.workflow.utils import Result


def test_job_py():
    workflow: Workflow = Workflow.from_loader(name="wf-run-common")
    job: Job = workflow.job("demo-run")

    # NOTE: Job params will change schema structure with {"params": { ... }}
    rs: Result = job.execute(params={"params": {"name": "Foo"}})
    assert {
        "1354680202": {
            "matrix": {},
            "stages": {
                "hello-world": {"outputs": {"x": "New Name"}},
                "run-var": {"outputs": {"x": 1}},
            },
        },
    } == rs.context


def test_job_py_raise():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-python-raise", externals={}
    )
    first_job: Job = workflow.job("first-job")

    with pytest.raises(JobException):
        first_job.execute(params={})


def test_job_py_not_set_output():
    with mock.patch.object(Config, "stage_default_id", False):
        # NOTE: Get stage from the specific workflow.
        workflow: Workflow = Workflow.from_loader(
            name="wf-run-python-raise", externals={}
        )
        job: Job = workflow.job("second-job")
        rs = job.execute(params={})
        assert {"1354680202": {"matrix": {}, "stages": {}}} == rs.context


@mock.patch.object(Config, "job_raise_error", True)
@mock.patch.object(Config, "stage_raise_error", True)
def test_job_py_fail_fast():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-python-raise-for-job"
    )
    job: Job = workflow.job("job-fail-fast")
    rs: Result = job.execute({})
    assert rs.context == {
        "2150810470": {
            "matrix": {"sleep": "1"},
            "stages": {"success": {"outputs": {"result": "fast-success"}}},
        },
        "4855178605": {
            "matrix": {"sleep": "5"},
            "stages": {"success": {"outputs": {"result": "fast-success"}}},
        },
        "9873503202": {
            "matrix": {"sleep": "0.1"},
            "stages": {"success": {"outputs": {"result": "success"}}},
        },
    }


@mock.patch.object(Config, "job_raise_error", True)
@mock.patch.object(Config, "stage_raise_error", True)
def test_job_py_fail_fast_raise():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-python-raise-for-job"
    )
    job: Job = workflow.job("job-fail-fast-raise")
    rs: Result = job.execute({})
    assert rs.context == {
        "error": rs.context["error"],
        "error_message": (
            "JobException: Get stage execution error: StageException: "
            "PyStage: \n\tValueError: Testing raise error inside PyStage!!!"
        ),
        "9873503202": {
            "matrix": {"sleep": "0.1"},
            "stages": {
                "7972360640": {"outputs": {}},
                "raise-error": {"outputs": {"result": "success"}},
            },
        },
    }


@mock.patch.object(Config, "job_raise_error", True)
@mock.patch.object(Config, "stage_raise_error", True)
def test_job_py_complete():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-python-raise-for-job"
    )
    job: Job = workflow.job("job-complete")
    rs: Result = job.execute({})
    assert rs.context == {
        "2150810470": {
            "matrix": {"sleep": "1"},
            "stages": {"success": {"outputs": {"result": "fast-success"}}},
        },
        "4855178605": {
            "matrix": {"sleep": "5"},
            "stages": {"success": {"outputs": {"result": "fast-success"}}},
        },
        "9873503202": {
            "matrix": {"sleep": "0.1"},
            "stages": {"success": {"outputs": {"result": "success"}}},
        },
    }


@mock.patch.object(Config, "job_raise_error", True)
@mock.patch.object(Config, "stage_raise_error", True)
def test_job_py_complete_raise():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-python-raise-for-job"
    )
    job: Job = workflow.job("job-complete-raise")
    rs: Result = job.execute({})
    assert rs.context == {
        "9873503202": {
            "matrix": {"sleep": "0.1"},
            "stages": {
                "7972360640": {"outputs": {}},
                "raise-error": {"outputs": {"result": "success"}},
            },
        },
        "error": rs.context["error"],
        "error_message": (
            "JobException: Get stage execution error: StageException: "
            "PyStage: \n\tValueError: Testing raise error inside PyStage!!!"
        ),
    }
