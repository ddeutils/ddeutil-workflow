import ddeutil.workflow.pipeline as pipe
from ddeutil.workflow.utils import Result


def test_job_py():
    pipeline = pipe.Pipeline.from_loader(name="pipe-run-common", externals={})
    demo_job: pipe.Job = pipeline.job("demo-run")

    # NOTE: Job params will change schema structure with {"params": { ... }}
    rs = demo_job.execute(params={"params": {"name": "Foo"}})
    assert {
        "1354680202": {
            "matrix": {},
            "stages": {
                "hello-world": {"outputs": {"x": "New Name"}},
                "run-var": {"outputs": {"x": 1}},
            },
        },
    } == rs.context


def test_pipe_run_py():
    pipeline = pipe.Pipeline.from_loader(
        name="run_python_with_params",
        externals={},
    )
    rs: Result = pipeline.execute(
        params={
            "author-run": "Local Workflow",
            "run-date": "2024-01-01",
        }
    )
    assert 0 == rs.status
    assert {"final-job", "first-job", "second-job"} == set(
        rs.context["jobs"].keys()
    )
    assert {"printing", "setting-x"} == set(
        rs.context["jobs"]["first-job"]["stages"].keys()
    )
