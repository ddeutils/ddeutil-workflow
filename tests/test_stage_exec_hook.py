import pytest
from ddeutil.workflow import Workflow
from ddeutil.workflow.exceptions import StageException
from ddeutil.workflow.stage import Stage
from ddeutil.workflow.utils import Result


def test_stage_exec_hook():
    workflow: Workflow = Workflow.from_loader(name="wf-hook-return-type")
    stage: Stage = workflow.job("second-job").stage("extract-load")
    rs: Result = stage.execute({})

    assert 0 == rs.status
    assert {"records": 1} == rs.context


def test_stage_exec_hook_raise_return_type():
    workflow: Workflow = Workflow.from_loader(name="wf-hook-return-type")
    stage: Stage = workflow.job("first-job").stage("valid-type")

    with pytest.raises(StageException):
        stage.execute({})


def test_stage_exec_hook_raise_args():
    workflow: Workflow = Workflow.from_loader(name="wf-hook-return-type")
    stage: Stage = workflow.job("first-job").stage("args-necessary")

    with pytest.raises(StageException):
        stage.execute({})


def test_stage_exec_hook_not_valid():
    workflow: Workflow = Workflow.from_loader(name="wf-hook-return-type")
    stage: Stage = workflow.job("first-job").stage("hook-not-valid")

    with pytest.raises(StageException):
        stage.execute({})


def test_stage_exec_hook_not_register():
    workflow: Workflow = Workflow.from_loader(name="wf-hook-return-type")
    stage: Stage = workflow.job("first-job").stage("hook-not-register")

    with pytest.raises(StageException):
        stage.execute({})
