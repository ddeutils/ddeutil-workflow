import pytest
import yaml
from ddeutil.workflow import Workflow
from ddeutil.workflow.exceptions import WorkflowException
from ddeutil.workflow.job import Job
from ddeutil.workflow.utils import Result
from pydantic import ValidationError


def test_workflow():
    job: Job = Job(
        stages=[
            {"name": "Run Hello World", "run": "print(f'Hello {x}')\n"},
            {
                "name": "Run Sequence and use var from Above",
                "run": (
                    "print(f'Receive x from above with {x}')\n\n" "x: int = 1\n"
                ),
            },
        ],
    )
    workflow: Workflow = Workflow(
        name="manual-workflow",
        jobs={
            "demo-run": job,
            "next-run": {
                "stages": [
                    {
                        "name": "Set variable and function",
                        "run": (
                            "var: str = 'Foo'\n"
                            "def echo() -> None:\n\tprint(f'Echo {var}')\n"
                        ),
                    },
                    {"name": "Call that variable", "run": "echo()\n"},
                ]
            },
        },
    )

    assert workflow.name == "manual-workflow"
    assert workflow.job("demo-run") == job

    # NOTE: Raise ValueError when get a job with ID that does not exist.
    with pytest.raises(ValueError):
        workflow.job("not-found-job-id")

    # NOTE: Raise when name of workflow include any template parameter syntax.
    with pytest.raises(ValidationError):
        Workflow(name="manual-workflow-${{ params.test }}")

    with pytest.raises(ValidationError):
        Workflow(name="manual-workflow-${{ matrix.name }}")


def test_workflow_on():

    # NOTE: Raise when the on field receive duplicate values.
    with pytest.raises(ValidationError):
        Workflow.from_loader(name="wf-scheduling-raise")


def test_workflow_desc():
    workflow = Workflow.from_loader(name="wf-run-common")
    assert workflow.desc == (
        "## Run Python Workflow\n\nThis is a running python workflow\n"
    )


def test_workflow_from_loader_without_job():
    workflow = Workflow.from_loader(name="wf-without-jobs")
    rs = workflow.execute({})
    assert rs.context == {}


def test_workflow_from_loader_raise(test_path):
    test_file = test_path / "conf/demo/01_01_wf_run_raise.yml"

    # NOTE: Raise for type of workflow does not valid.
    with test_file.open(mode="w") as f:
        yaml.dump(
            {
                "wf-run-from-loader-raise": {
                    "type": "ddeutil.workflow.on.On",
                    "jobs": {
                        "first-job": {
                            "stages": [
                                {"name": "Echo next", "echo": "Hello World"}
                            ]
                        }
                    },
                }
            },
            f,
        )

    with pytest.raises(ValueError):
        Workflow.from_loader(name="wf-run-from-loader-raise")

    # NOTE: Raise if type of the on field does not valid with str or dict.
    with test_file.open(mode="w") as f:
        yaml.dump(
            {
                "wf-run-from-loader-raise": {
                    "type": "ddeutil.workflow.Workflow",
                    "on": [
                        ["* * * * *"],
                        ["* * 1 0 0"],
                    ],
                    "jobs": {
                        "first-job": {
                            "stages": [
                                {"name": "Echo next", "echo": "Hello World"}
                            ]
                        }
                    },
                }
            },
            f,
        )

    with pytest.raises(TypeError):
        Workflow.from_loader(name="wf-run-from-loader-raise")

    # NOTE: Raise if value of the on field does not parsing to the CronJob obj.
    with test_file.open(mode="w") as f:
        yaml.dump(
            {
                "wf-run-from-loader-raise": {
                    "type": "ddeutil.workflow.Workflow",
                    "jobs": {
                        "first-job": {
                            "needs": ["not-found"],
                            "stages": [
                                {"name": "Echo next", "echo": "Hello World"}
                            ],
                        }
                    },
                }
            },
            f,
        )
    with pytest.raises(WorkflowException):
        Workflow.from_loader(name="wf-run-from-loader-raise")

    # NOTE: Remove the testing file on the demo path.
    test_file.unlink(missing_ok=True)


def test_workflow_condition():
    workflow = Workflow.from_loader(name="wf-condition")
    rs: Result = workflow.execute(params={"name": "bar"})
    assert {
        "params": {"name": "bar"},
        "jobs": {
            "condition-job": {
                "matrix": {},
                "stages": {},
            },
        },
    } == rs.context

    rs: Result = workflow.execute(params={"name": "foo"})
    assert {
        "params": {"name": "foo"},
        "jobs": {
            "condition-job": {
                "matrix": {},
                "stages": {
                    "condition-stage": {"outputs": {"message": "Hello World"}}
                },
            },
        },
    } == rs.context


def test_workflow_parameterize():
    workflow = Workflow.from_loader(name="wf-params-required")

    assert workflow.parameterize({"name": "foo"}) == {
        "params": {"name": "foo"},
        "jobs": {},
    }

    # NOTE: Raise if passing parameter that does not set on the workflow.
    with pytest.raises(WorkflowException):
        workflow.parameterize({"foo": "bar"})
