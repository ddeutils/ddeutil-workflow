import pytest
from ddeutil.workflow.pipeline import Job, Pipeline
from pydantic import ValidationError


def test_pipe_model():
    data = {
        "demo-run": {
            "stages": [
                {"name": "Run Hello World", "run": "print(f'Hello {x}')\n"},
                {
                    "name": "Run Sequence and use var from Above",
                    "run": (
                        "print(f'Receive x from above with {x}')\n\n"
                        "x: int = 1\n"
                    ),
                },
            ]
        },
        "next-run": {
            "stages": [
                {
                    "name": "Set variable and function",
                    "run": (
                        "var_inside: str = 'Inside'\n"
                        "def echo() -> None:\n"
                        '  print(f"Echo {var_inside}"\n'
                    ),
                },
                {"name": "Call that variable", "run": "echo()\n"},
            ]
        },
    }
    p = Pipeline(name="manual-pipeline", jobs=data)
    assert "Run Hello World" == p.jobs.get("demo-run").stages[0].name
    assert (
        "Run Sequence and use var from Above"
        == p.jobs.get("demo-run").stages[1].name
    )

    demo_job: Job = p.job("demo-run")
    assert [{}] == demo_job.strategy.make()


def test_pipe_model_name_raise():

    with pytest.raises(ValidationError):
        Pipeline(name="manual-pipeline-${{ params.test }}")
