import ddeutil.workflow.pipeline as pipe
import pytest


def test_pipe_stage_run_py(params_simple):
    pipeline = pipe.Pipeline.from_loader(
        name="run_python", params=params_simple, externals={}
    )
    stage = pipeline.job("raise-run").stage(stage_id="raise-error")
    assert stage.id == "raise-error"
    with pytest.raises(pipe.PyException):
        stage.execute({"x": "Foo"})


def test_pipe_job_run_py(params_simple):
    pipeline = pipe.Pipeline.from_loader(
        name="run_python", params=params_simple, externals={}
    )
    demo_job: pipe.Job = pipeline.job("demo-run")
    rs = demo_job.execute({"x": "Foo"})
    assert {"x": 1} == rs
