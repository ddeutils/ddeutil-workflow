import pytest
from ddeutil.workflow import Workflow
from ddeutil.workflow.exceptions import StageException
from ddeutil.workflow.stage import Stage
from ddeutil.workflow.utils import Result


def test_stage_bash():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-common", externals={}
    )
    echo: Stage = workflow.job("bash-run").stage("echo")
    rs: Result = echo.execute({})
    assert {
        "return_code": 0,
        "stdout": "Hello World\nVariable Foo",
        "stderr": "",
    } == rs.context


def test_stage_bash_env():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-common", externals={}
    )
    echo_env: Stage = workflow.job("bash-run-env").stage("echo-env")
    rs: Result = echo_env.execute({})
    assert {
        "return_code": 0,
        "stdout": "Hello World\nVariable Foo\nENV Bar",
        "stderr": "",
    } == rs.context


def test_stage_bash_raise():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-common", externals={}
    )
    raise_bash: Stage = workflow.job("bash-run-env").stage("raise-error")
    with pytest.raises(StageException):
        raise_bash.execute({})
