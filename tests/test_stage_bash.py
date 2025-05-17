import pytest
from ddeutil.workflow import FAILED, SUCCESS, Result
from ddeutil.workflow.stages import BashStage


def test_bash_stage_exec():
    stage: BashStage = BashStage(
        name="Bash Stage",
        bash='echo "Hello World";\n' "VAR='Foo';\n" 'echo "Variable $VAR";',
    )
    rs: Result = stage.handler_execute({})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "return_code": 0,
        "stdout": "Hello World\nVariable Foo",
        "stderr": None,
    }


def test_bash_stage_exec_with_env():
    stage: BashStage = BashStage(
        name="Bash Stage",
        bash='echo "ENV $$FOO";',
        env={"FOO": "Bar"},
    )
    rs: Result = stage.handler_execute({})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "return_code": 0,
        "stdout": "ENV Bar",
        "stderr": None,
    }


def test_bash_stage_exec_raise():
    stage: BashStage = BashStage(
        name="Bash Stage",
        bash='echo "Test Raise Error case with failed" >&2;\nexit 1;',
    )
    rs: Result = stage.handler_execute({})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "StageError",
            "message": (
                "Subprocess: Test Raise Error case with failed\n"
                "---( statement )---\n"
                '```bash\necho "Test Raise Error case with failed" >&2;\n'
                "exit 1;\n"
                "```"
            ),
        },
    }


@pytest.mark.asyncio
async def test_bash_stage_axec():
    stage: BashStage = BashStage(name="Bash Stage", bash='echo "Hello World"')
    rs: Result = await stage.handler_axecute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "return_code": 0,
        "stdout": "Hello World",
        "stderr": None,
    }


@pytest.mark.asyncio
async def test_bash_stage_axec_raise():
    stage: BashStage = BashStage(
        name="Bash Stage",
        bash='echo "Test Raise Error case with failed" >&2;\n' "exit 1;",
    )

    # NOTE: Raise error from bash that force exit 1.
    rs: Result = await stage.handler_axecute({})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "StageError",
            "message": (
                "Subprocess: Test Raise Error case with failed\n"
                "---( statement )---\n"
                '```bash\necho "Test Raise Error case with failed" >&2;\n'
                "exit 1;\n"
                "```"
            ),
        },
    }
