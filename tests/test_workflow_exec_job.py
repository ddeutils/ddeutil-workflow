from ddeutil.workflow import Workflow
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
    rs: Result = workflow.execute_job(job=workflow.job("demo-run"), params={})
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

    rs: Result = workflow.execute_job(job=workflow.job("demo-run"), params={})
    assert rs.status == FAILED
    assert rs.context == {
        "errors": {
            "name": "WorkflowException",
            "message": "Job, 'demo-run', return `FAILED` status.",
        },
        "jobs": {
            "demo-run": {
                "stages": {},
                "errors": {
                    "name": "JobException",
                    "message": (
                        "Handler Error: StageException: PyStage: "
                        "NotImplementedError: "
                    ),
                },
            },
        },
    }
