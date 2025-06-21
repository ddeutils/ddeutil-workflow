from threading import Event

from ddeutil.workflow import CANCEL, FAILED, SUCCESS, Workflow
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
    st, ctx = workflow.execute_job(
        job=workflow.job("demo-run"), run_id="1234", context={}
    )
    assert st == SUCCESS
    assert ctx == {
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

    event = Event()
    event.set()
    st, ctx = workflow.execute_job(
        job=workflow.job("demo-run"), run_id="1234", context={}, event=event
    )
    assert st == CANCEL
    assert ctx == {
        "status": CANCEL,
        "errors": {
            "name": "WorkflowCancelError",
            "message": "Job execution was canceled because the event was set before start job execution.",
        },
    }


def test_workflow_execute_job_raise_inside():
    job: Job = Job(
        stages=[
            {"name": "raise error", "run": "raise NotImplementedError()\n"},
        ],
    )
    workflow: Workflow = Workflow(name="workflow", jobs={"demo-run": job})
    st, ctx = workflow.execute_job(
        job=workflow.job("demo-run"), run_id="1234", context={}
    )
    assert st == FAILED
    assert ctx == {
        "status": FAILED,
        "errors": {
            "name": "WorkflowError",
            "message": "Job execution, 'demo-run', was failed.",
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
