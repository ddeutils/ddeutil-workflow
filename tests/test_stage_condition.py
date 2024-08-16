import pytest
from ddeutil.workflow.exceptions import StageException
from ddeutil.workflow.pipeline import Pipeline
from ddeutil.workflow.stage import Stage


def test_stage_condition_raise():
    pipeline: Pipeline = Pipeline.from_loader(
        name="pipe-condition-raise", externals={}
    )
    stage: Stage = pipeline.job("condition-job").stage("condition-stage")

    with pytest.raises(StageException):
        stage.is_skipped({"params": {"name": "foo"}})
