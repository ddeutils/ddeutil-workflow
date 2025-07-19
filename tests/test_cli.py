import pytest
from ddeutil.workflow.__main__ import app
from typer.testing import CliRunner


@pytest.fixture(scope="module")
def runner() -> CliRunner:
    return CliRunner()


def test_app(runner: CliRunner):
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "ddeutil-workflow==" in result.output
    assert "python-version==" in result.output
