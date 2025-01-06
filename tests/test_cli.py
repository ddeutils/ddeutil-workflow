from datetime import datetime, timedelta

from ddeutil.workflow.cli import cli
from typer.testing import CliRunner, Result


def test_cli_workflow():
    runner = CliRunner(mix_stderr=False)
    result: Result = runner.invoke(
        cli,
        [
            "run",
            "wf-scheduling-agent",
            '{"name": "Foo", "asat-dt": "2024-01-01"}',
        ],
    )
    print(result.stderr)
    print(result.stdout)
    assert result.exit_code == 0
    assert (
        "Running workflow name: (<class 'str'>) " "'wf-scheduling-agent'"
    ) in result.stdout


def test_cli_schedule():
    runner = CliRunner(mix_stderr=False)
    stop_date: datetime = datetime.now().replace(
        second=0, microsecond=0
    ) + timedelta(minutes=2)
    result: Result = runner.invoke(
        cli,
        [
            "schedule",
            "--stop",
            stop_date.strftime("%Y-%m-%d %H:%M:%S"),
            "--excluded",
            (
                '["schedule-common-wf", '
                '"schedule-multi-on-wf", '
                '"schedule-every-minute-wf", '
                '"schedule-every-minute-wf-parallel"]'
            ),
        ],
    )
    print(result.stderr)
    print(result.stdout)
    assert result.exit_code == 0
