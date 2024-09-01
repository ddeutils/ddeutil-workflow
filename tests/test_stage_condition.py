import pytest
from ddeutil.workflow import Workflow
from ddeutil.workflow.exceptions import StageException
from ddeutil.workflow.stage import Stage


def test_stage_condition_raise():
    workflow: Workflow = Workflow.from_loader(
        name="wf-condition-raise", externals={}
    )
    stage: Stage = workflow.job("condition-job").stage("condition-stage")

    with pytest.raises(StageException):
        stage.is_skipped({"params": {"name": "foo"}})
