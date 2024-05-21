import ddeutil.workflow.pipeline as pipe
import pytest


def test_pipe_py_stage_raise(params_simple):
    pipeline = pipe.Pipeline.from_loader(
        name="run_python", params=params_simple, externals={}
    )
    stage = pipeline.job("raise-run").stage(stage_id="raise-error")
    assert stage.id == "raise-error"
    with pytest.raises(pipe.PyException):
        stage.execute(params={"x": "Foo"})


def test_pipe_py_job(params_simple):
    pipeline = pipe.Pipeline.from_loader(
        name="run_python", params=params_simple, externals={}
    )
    demo_job: pipe.Job = pipeline.job("demo-run")
    rs = demo_job.execute(params={"x": "Foo"})
    assert {"x": 1} == rs


def test_pipe_shell_job(params_simple):
    pipeline = pipe.Pipeline.from_loader(
        name="run_python", params=params_simple, externals={}
    )
    shell_run: pipe.Job = pipeline.job("shell-run")
    rs = shell_run.execute({})
    print(rs)
