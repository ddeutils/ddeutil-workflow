import pytest
from ddeutil.workflow import Workflow
from ddeutil.workflow.exceptions import StageException
from ddeutil.workflow.result import Result
from ddeutil.workflow.stage import Stage


def test_stage_exec_bash():
    workflow: Workflow = Workflow.from_loader(name="wf-run-common")
    stage: Stage = workflow.job("bash-run").stage("echo")
    rs: Result = stage.handler_execute({})
    assert {
        "return_code": 0,
        "stdout": "Hello World\nVariable Foo",
        "stderr": None,
    } == rs.context


def test_stage_exec_bash_env():
    workflow: Workflow = Workflow.from_loader(name="wf-run-common")
    stage: Stage = workflow.job("bash-run-env").stage("echo-env")
    rs: Result = stage.handler_execute({})
    assert {
        "return_code": 0,
        "stdout": "Hello World\nVariable Foo\nENV Bar",
        "stderr": None,
    } == rs.context


def test_stage_exec_bash_env_raise():
    workflow: Workflow = Workflow.from_loader(name="wf-run-common")
    stage: Stage = workflow.job("bash-run-env").stage("raise-error")
    with pytest.raises(StageException):
        stage.handler_execute({})
