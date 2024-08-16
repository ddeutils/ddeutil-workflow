import pytest
from ddeutil.workflow.exceptions import JobException
from ddeutil.workflow.pipeline import Job, Pipeline
from ddeutil.workflow.utils import Result


def test_job_py():
    pipeline: Pipeline = Pipeline.from_loader(
        name="pipe-run-common", externals={}
    )
    demo_job: Job = pipeline.job("demo-run")

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
    pipeline: Pipeline = Pipeline.from_loader(
        name="pipe-run-python-raise", externals={}
    )
    first_job: Job = pipeline.job("first-job")

    with pytest.raises(JobException):
        first_job.execute(params={})
