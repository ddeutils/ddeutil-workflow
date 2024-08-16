import pytest
from ddeutil.workflow.exceptions import StageException
from ddeutil.workflow.pipeline import Pipeline
from ddeutil.workflow.stage import Stage
from ddeutil.workflow.utils import Result


def test_stage_py_raise():
    pipeline: Pipeline = Pipeline.from_loader(
        name="pipe-run-common", externals={}
    )
    stage: Stage = pipeline.job("raise-run").stage(stage_id="raise-error")

    assert stage.id == "raise-error"

    with pytest.raises(StageException):
        stage.execute(params={"x": "Foo"})


def test_pipe_stage_py():
    # NOTE: Get stage from the specific pipeline.
    pipeline: Pipeline = Pipeline.from_loader(
        name="pipe-run-common", externals={}
    )
    stage: Stage = pipeline.job("demo-run").stage(stage_id="run-var")
    assert stage.id == "run-var"

    # NOTE: Start execute with manual stage parameters.
    p = {
        "params": {"name": "Author"},
        "stages": {"hello-world": {"outputs": {"x": "Foo"}}},
    }
    rs = stage.execute(params=p)
    _prepare_rs = stage.set_outputs(rs.context, p)
    assert {
        "params": {"name": "Author"},
        "stages": {
            "hello-world": {"outputs": {"x": "Foo"}},
            "run-var": {"outputs": {"x": 1}},
        },
    } == _prepare_rs


def test_pipe_stage_py_func():
    pipeline: Pipeline = Pipeline.from_loader(
        name="run_python_with_params", externals={}
    )
    stage: Stage = pipeline.job("second-job").stage(stage_id="create-func")
    assert stage.id == "create-func"

    # NOTE: Start execute with manual stage parameters.
    rs: Result = stage.execute(params={})
    _prepare_rs = stage.set_outputs(rs.context, {})
    assert ("var_inside", "echo") == tuple(
        _prepare_rs["stages"]["create-func"]["outputs"].keys()
    )
