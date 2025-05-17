from ddeutil.workflow import FAILED, SUCCESS, Result, Workflow
from ddeutil.workflow.job import Job


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
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "jobs": {
            "demo-run": {
                "status": SUCCESS,
                "stages": {
                    "9371661540": {
                        "outputs": {"var": "Foo", "echo": "echo"},
                        "status": SUCCESS,
                    },
                    "3008506540": {"outputs": {}, "status": SUCCESS},
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
        "status": FAILED,
        "errors": {
            "name": "WorkflowError",
            "message": "Job, 'demo-run', return `FAILED` status.",
        },
        "jobs": {
            "demo-run": {
                "status": FAILED,
                "stages": {
                    "9722867994": {
                        "status": FAILED,
                        "outputs": {},
                        "errors": {
                            "name": "NotImplementedError",
                            "message": "",
                        },
                    }
                },
                "errors": {
                    "name": "JobError",
                    "message": (
                        "Strategy execution was break because its "
                        "nested-stage, 'raise error', failed."
                    ),
                },
            }
        },
    }
