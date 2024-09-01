import pytest
from ddeutil.workflow import Pipeline
from ddeutil.workflow.exceptions import StageException
from ddeutil.workflow.stage import Stage
from ddeutil.workflow.utils import Result


def test_stage_hook():
    pipeline: Pipeline = Pipeline.from_loader(
        name="pipe-hook-return-type", externals={}
    )
    stage: Stage = pipeline.job("second-job").stage("extract-load")
    rs: Result = stage.execute({})

    assert 0 == rs.status
    assert {"records": 1} == rs.context


def test_stage_hook_raise_return_type():
    pipeline: Pipeline = Pipeline.from_loader(
        name="pipe-hook-return-type", externals={}
    )
    stage: Stage = pipeline.job("first-job").stage("valid-type")

    with pytest.raises(StageException):
        stage.execute({})


def test_stage_hook_raise_args():
    pipeline: Pipeline = Pipeline.from_loader(
        name="pipe-hook-return-type", externals={}
    )
    stage: Stage = pipeline.job("first-job").stage("args-necessary")

    with pytest.raises(StageException):
        stage.execute({})


def test_stage_hook_not_valid():
    pipeline: Pipeline = Pipeline.from_loader(
        name="pipe-hook-return-type", externals={}
    )
    stage: Stage = pipeline.job("first-job").stage("hook-not-valid")

    with pytest.raises(StageException):
        stage.execute({})


def test_stage_hook_not_register():
    pipeline: Pipeline = Pipeline.from_loader(
        name="pipe-hook-return-type", externals={}
    )
    stage: Stage = pipeline.job("first-job").stage("hook-not-register")

    with pytest.raises(StageException):
        stage.execute({})
