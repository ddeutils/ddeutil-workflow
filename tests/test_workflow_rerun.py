from ddeutil.workflow import (
    SUCCESS,
    Job,
    Result,
    Workflow,
)


def test_workflow_rerun():
    job: Job = Job(
        stages=[{"name": "Sleep", "run": "import time\ntime.sleep(2)"}],
    )
    workflow: Workflow = Workflow(
        name="demo-workflow",
        jobs={"sleep-run": job, "sleep-again-run": job},
    )
    rs: Result = workflow.rerun(
        context={
            "status": SUCCESS,
            "params": {},
            "jobs": {
                "sleep-again-run": {
                    "status": SUCCESS,
                    "stages": {
                        "7972360640": {"outputs": {}, "status": SUCCESS}
                    },
                },
            },
        },
        max_job_parallel=1,
    )
    assert rs.status == SUCCESS
