import pytest
from ddeutil.workflow import FAILED, SUCCESS, Result
from ddeutil.workflow.stages import BashStage


def test_bash_stage_exec():
    stage: BashStage = BashStage(
        name="Bash Stage",
        bash='echo "Hello World";\n' "VAR='Foo';\n" 'echo "Variable $VAR";',
    )
    rs: Result = stage.execute({})
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
    rs: Result = stage.execute({})
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
    rs: Result = stage.execute({})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "StageError",
            "message": (
                "Subprocess: Test Raise Error case with failed\n\t"
                '```bash\n\techo "Test Raise Error case with failed" >&2;\n\t'
                "exit 1;\n\t"
                "```"
            ),
        },
    }


def test_bash_stage_exec_retry():
    stage: BashStage = BashStage(
        name="Retry Bash Stage",
        bash=(
            "VAR=${{ retry }};\n"
            'if [ "$VAR" -eq 1 ]; then\n'
            'echo "This value do not break retry step.";\n'
            "else\n"
            'echo "Raise Error for test retry strategy." >&2;\n'
            "exit 1;\n"
            "fi;"
        ),
        retry=1,
    )
    rs: Result = stage.execute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "retry": 1,
        "return_code": 0,
        "stdout": "This value do not break retry step.",
        "stderr": None,
    }


def test_bash_stage_exec_retry_exceed():
    stage: BashStage = BashStage(
        name="Retry Bash Stage",
        bash=(
            "VAR=${{ retry }};\n"
            'if [ "$VAR" -eq 3 ]; then\n'
            'echo "This value do not break retry step.";\n'
            "else\n"
            'echo "Raise Error for test retry strategy." >&2;\n'
            "exit 1;\n"
            "fi;"
        ),
        retry=1,
    )
    rs: Result = stage.execute(params={})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "retry": 1,
        "errors": {
            "name": "StageError",
            "message": (
                "Subprocess: Raise Error for test retry strategy.\n\t"
                "```bash\n\t"
                'VAR=1;\n\tif [ "$VAR" -eq 3 ]; then\n\t'
                'echo "This value do not break retry step.";\n\t'
                'else\n\techo "Raise Error for test retry strategy." >&2;\n\t'
                "exit 1;\n\tfi;\n\t```"
            ),
        },
    }


@pytest.mark.asyncio
async def test_bash_stage_axec():
    stage: BashStage = BashStage(
        name="Bash Stage",
        desc="Echo runtime variable that create inside subprocess.",
        bash='echo "Hello World";\n' "VAR='Foo';\n" 'echo "Variable $VAR";',
    )
    rs: Result = await stage.axecute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "return_code": 0,
        "stdout": "Hello World\nVariable Foo",
        "stderr": None,
    }


@pytest.mark.asyncio
async def test_bash_stage_axec_retry():
    stage: BashStage = BashStage(
        name="Retry Bash Stage",
        bash=(
            "VAR=${{ retry }};\n"
            'if [ "$VAR" -eq 1 ]; then\n'
            'echo "This value do not break retry step.";\n'
            "else\n"
            'echo "Raise Error for test retry strategy." >&2;\n'
            "exit 1;\n"
            "fi;"
        ),
        retry=1,
    )
    rs: Result = await stage.axecute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "retry": 1,
        "return_code": 0,
        "stdout": "This value do not break retry step.",
        "stderr": None,
    }


@pytest.mark.asyncio
async def test_bash_stage_axec_raise():
    stage: BashStage = BashStage(
        name="Bash Stage",
        bash='echo "Test Raise Error case with failed" >&2;\n' "exit 1;",
    )

    # NOTE: Raise error from bash that force exit 1.
    rs: Result = await stage.axecute({})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "StageError",
            "message": (
                "Subprocess: Test Raise Error case with failed\n\t"
                '```bash\n\techo "Test Raise Error case with failed" >&2;\n\t'
                "exit 1;\n\t"
                "```"
            ),
        },
    }
