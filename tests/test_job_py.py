import os

import pytest
from ddeutil.workflow import Job, Workflow
from ddeutil.workflow.exceptions import JobException
from ddeutil.workflow.utils import Result


def test_job_py():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-common", externals={}
    )
    demo_job: Job = workflow.job("demo-run")

    # NOTE: Job params will change schema structure with {"params": { ... }}
    rs: Result = demo_job.execute(params={"params": {"name": "Foo"}})
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
    # NOTE: Get stage from the specific workflow.
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-python-raise", externals={}
    )
    job: Job = workflow.job("second-job")

    os.environ["WORKFLOW_CORE_STAGE_DEFAULT_ID"] = "false"

    rs = job.execute(params={})
    assert {"1354680202": {"matrix": {}, "stages": {}}} == rs.context

    os.environ["WORKFLOW_CORE_STAGE_DEFAULT_ID"] = "true"
