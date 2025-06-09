from ddeutil.workflow import (
    FAILED,
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
                "sleep-run": {
                    "status": SUCCESS,
                    "stages": {
                        "7972360640": {"outputs": {}, "status": SUCCESS}
                    },
                },
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
    assert rs.context == {
        "status": SUCCESS,
        "params": {},
        "jobs": {
            "sleep-run": {
                "status": SUCCESS,
                "stages": {"7972360640": {"outputs": {}, "status": SUCCESS}},
            },
            "sleep-again-run": {
                "status": SUCCESS,
                "stages": {"7972360640": {"outputs": {}, "status": SUCCESS}},
            },
        },
    }

    rs: Result = workflow.rerun(
        context={
            "status": FAILED,
            "params": {},
            "jobs": {
                "sleep-run": {
                    "status": SUCCESS,
                    "stages": {
                        "7972360640": {"outputs": {}, "status": SUCCESS}
                    },
                },
                "sleep-again-run": {
                    "status": FAILED,
                    "stages": {"7972360640": {"outputs": {}, "status": FAILED}},
                    "errors": {
                        "name": "DemoError",
                        "message": "Force error in job context.",
                    },
                },
            },
            "errors": {
                "name": "DemoError",
                "message": "Force error in context data before rerun.",
            },
        },
        max_job_parallel=1,
    )
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "params": {},
        "jobs": {
            "sleep-run": {
                "status": SUCCESS,
                "stages": {"7972360640": {"outputs": {}, "status": SUCCESS}},
            },
            "sleep-again-run": {
                "status": SUCCESS,
                "stages": {"7972360640": {"outputs": {}, "status": SUCCESS}},
            },
        },
    }
