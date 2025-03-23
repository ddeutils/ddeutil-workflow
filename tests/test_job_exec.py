from unittest import mock

import pytest
from ddeutil.workflow import Job, Workflow
from ddeutil.workflow.conf import Config
from ddeutil.workflow.exceptions import JobException
from ddeutil.workflow.result import Result


def test_job_exec_py():
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

    output = {}
    job.set_outputs(rs.context, to=output)
    assert output == {
        "jobs": {
            "demo-run": {
                "stages": {
                    "hello-world": {"outputs": {"x": "New Name"}},
                    "run-var": {"outputs": {"x": 1}},
                },
            },
        },
    }


def test_job_exec_py_raise():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-python-raise", externals={}
    )
    first_job: Job = workflow.job("first-job")

    with pytest.raises(JobException):
        first_job.execute(params={})


@mock.patch.object(Config, "stage_default_id", False)
def test_job_exec_py_not_set_output():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-python-raise", externals={}
    )
    job: Job = workflow.job("second-job")
    rs = job.execute(params={})
    assert {"1354680202": {"matrix": {}, "stages": {}}} == rs.context

    output = {}
    job.set_outputs(rs.context, to=output)
    assert output == {"jobs": {"second-job": {"stages": {}}}}


@mock.patch.object(Config, "job_raise_error", True)
@mock.patch.object(Config, "stage_raise_error", True)
def test_job_exec_py_fail_fast():
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
def test_job_exec_py_fail_fast_raise_catch():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-python-raise-for-job"
    )
    job: Job = workflow.job("job-fail-fast-raise")
    rs: Result = job.execute({})
    assert rs.context == {
        "9112472804": {
            "matrix": {"sleep": "4"},
            "stages": {"1181478804": {"outputs": {}}},
            "errors": {
                "class": rs.context["9112472804"]["errors"]["class"],
                "name": "JobException",
                "message": (
                    "Job strategy was canceled from event that had set before "
                    "strategy execution."
                ),
            },
        },
        "errors": {
            "class": rs.context["errors"]["class"],
            "name": "JobException",
            "message": (
                "Stage execution error: StageException: PyStage: \n\t"
                "ValueError: Testing raise error inside PyStage with the "
                "sleep not equal 4!!!"
            ),
        },
    }


@mock.patch.object(Config, "job_raise_error", True)
@mock.patch.object(Config, "stage_raise_error", True)
def test_job_exec_py_complete():
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
def test_job_exec_py_complete_not_parallel():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-python-raise-for-job"
    )
    job: Job = workflow.job("job-complete-not-parallel")
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

    output = {}
    job.set_outputs(rs.context, to=output)
    assert output == {
        "jobs": {
            "job-complete-not-parallel": {
                "strategies": {
                    "9873503202": {
                        "matrix": {"sleep": "0.1"},
                        "stages": {
                            "success": {"outputs": {"result": "success"}},
                        },
                    },
                    "4855178605": {
                        "matrix": {"sleep": "5"},
                        "stages": {
                            "success": {"outputs": {"result": "fast-success"}},
                        },
                    },
                    "2150810470": {
                        "matrix": {"sleep": "1"},
                        "stages": {
                            "success": {"outputs": {"result": "fast-success"}},
                        },
                    },
                },
            },
        },
    }


@mock.patch.object(Config, "job_raise_error", True)
@mock.patch.object(Config, "stage_raise_error", True)
def test_job_exec_py_complete_raise():
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
        "errors": {
            "class": rs.context["errors"]["class"],
            "name": "JobException",
            "message": (
                "Stage execution error: StageException: PyStage: \n\t"
                "ValueError: Testing raise error inside PyStage!!!"
            ),
        },
    }


@mock.patch.object(Config, "job_raise_error", True)
@mock.patch.object(Config, "stage_raise_error", True)
def test_job_exec_runs_on_not_implement():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-python-raise-for-job"
    )
    job: Job = workflow.job("job-fail-runs-on")

    with pytest.raises(NotImplementedError):
        job.execute({})
