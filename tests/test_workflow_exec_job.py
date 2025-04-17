import pytest
from ddeutil.workflow import Workflow
from ddeutil.workflow.exceptions import WorkflowException
from ddeutil.workflow.job import Job
from ddeutil.workflow.result import FAILED, Result


def test_workflow_execute_job():
    job: Job = Job(
        stages=[
            {
                "name": "Set variable and function",
                "run": (
                    "var: str = 'Foo'\n"
                    "def echo(var: str) -> None:\n\tprint(f'Echo {var}')\n"
                    "echo(var=var)\n"
                ),
            },
            {"name": "Call print function", "run": "print('Start')\n"},
        ],
    )
    workflow: Workflow = Workflow(name="workflow", jobs={"demo-run": job})
    rs: Result = workflow.execute_job(job_id="demo-run", params={})
    assert rs.context == {
        "jobs": {
            "demo-run": {
                "stages": {
                    "9371661540": {"outputs": {"var": "Foo", "echo": "echo"}},
                    "3008506540": {"outputs": {}},
                },
            },
        },
    }


def test_workflow_execute_job_raise_inside():
    job: Job = Job(
        stages=[
            {"name": "raise error", "run": "raise NotImplementedError()\n"},
        ],
    )
    workflow: Workflow = Workflow(name="workflow", jobs={"demo-run": job})

    # NOTE: Raise if execute not exist job's ID.
    with pytest.raises(WorkflowException):
        workflow.execute_job(
            job_id="not-found-job",
            params={
                "author-run": "Local Workflow",
                "run-date": "2024-01-01",
            },
        )

    rs: Result = workflow.execute_job(job_id="demo-run", params={})
    assert rs.status == FAILED
    assert rs.context == {
        "errors": {
            "class": rs.context["errors"]["class"],
            "name": "WorkflowException",
            "message": "Workflow job, 'demo-run', return FAILED status.",
        },
        "jobs": {
            "demo-run": {
                "errors": [
                    {
                        "class": rs.context["jobs"]["demo-run"]["errors"][0][
                            "class"
                        ],
                        "name": "JobException",
                        "message": (
                            "Stage raise: StageException: PyStage: "
                            "\n\t| ...\tNotImplementedError: "
                        ),
                    }
                ],
                "stages": {},
            },
        },
    }
