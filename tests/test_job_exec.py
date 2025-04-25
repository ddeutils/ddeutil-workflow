from ddeutil.workflow import Job, Workflow
from ddeutil.workflow.result import FAILED, SUCCESS, Result


def test_job_exec_py():
    workflow: Workflow = Workflow.from_conf(name="wf-run-common")
    job: Job = workflow.job("demo-run")

    # NOTE: Job params will change schema structure with {"params": { ... }}
    rs: Result = job.execute(params={"params": {"name": "Foo"}})
    assert {
        "EMPTY": {
            "matrix": {},
            "stages": {
                "hello-world": {"outputs": {"x": "New Name"}},
                "run-var": {"outputs": {"x": 1}},
            },
        },
    } == rs.context

    output = {}
    job.set_outputs(rs.context, to=output)
    assert output == {
        "jobs": {
            "demo-run": {
                "stages": {
                    "hello-world": {"outputs": {"x": "New Name"}},
                    "run-var": {"outputs": {"x": 1}},
                },
            },
        },
    }


def test_job_exec_py_raise():
    rs: Result = (
        Workflow.from_conf(name="wf-run-python-raise")
        .job("first-job")
        .execute(params={})
    )
    assert rs.status == FAILED
    assert rs.context == {
        "EMPTY": {
            "errors": {
                "message": "PyStage: ValueError: Testing raise error inside PyStage!!!",
                "name": "StageException",
            },
            "matrix": {},
            "stages": {},
        },
        "errors": {
            "name": "JobException",
            "message": (
                "Handler Error: StageException: PyStage: "
                "ValueError: Testing raise error inside PyStage!!!"
            ),
        },
    }


def test_job_exec_py_not_set_output():
    workflow: Workflow = Workflow.from_conf(
        name="wf-run-python-raise", extras={"stage_default_id": False}
    )
    job: Job = workflow.job("second-job")
    rs = job.execute(params={})
    assert {"EMPTY": {"matrix": {}, "stages": {}}} == rs.context
    assert job.set_outputs(rs.context, to={}) == {
        "jobs": {"second-job": {"stages": {}}}
    }


def test_job_exec_py_fail_fast():
    rs: Result = (
        Workflow.from_conf(
            name="wf-run-python-raise-for-job",
            extras={"stage_raise_error": True},
        )
        .job("job-fail-fast")
        .execute({})
    )
    assert rs.status == SUCCESS
    assert rs.context == {
        "2150810470": {
            "matrix": {"sleep": "1"},
            "stages": {"success": {"outputs": {"result": "fast-success"}}},
        },
        "4855178605": {
            "matrix": {"sleep": "5"},
            "stages": {"success": {"outputs": {"result": "fast-success"}}},
        },
        "9873503202": {
            "matrix": {"sleep": "0.1"},
            "stages": {"success": {"outputs": {"result": "success"}}},
        },
    }


def test_job_exec_py_fail_fast_raise_catch():
    rs: Result = (
        Workflow.from_conf(
            name="wf-run-python-raise-for-job",
            extras={
                "stage_raise_error": True,
                "stage_default_id": False,
            },
        )
        .job("job-fail-fast-raise")
        .execute({})
    )
    print(rs.context)
    assert rs.status == FAILED
    assert rs.context == {
        "1067561285": {
            "matrix": {"sleep": "2"},
            "stages": {},
            "errors": {
                "name": "JobException",
                "message": "Job strategy was canceled because event was set.",
            },
        },
        "2150810470": {
            "errors": {
                "message": (
                    "PyStage: ValueError: Testing raise error inside "
                    "PyStage with the sleep not equal 4!!!"
                ),
                "name": "StageException",
            },
            "matrix": {"sleep": "1"},
            "stages": {},
        },
        "9112472804": {
            "matrix": {"sleep": "4"},
            "stages": {},
            "errors": {
                "name": "JobException",
                "message": "Job strategy was canceled because event was set.",
            },
        },
        "errors": {
            "1067561285": {
                "name": "JobException",
                "message": "Job strategy was canceled because event was set.",
            },
            "2150810470": {
                "name": "JobException",
                "message": "Handler Error: StageException: PyStage: ValueError: Testing raise error inside PyStage with the sleep not equal 4!!!",
            },
            "9112472804": {
                "name": "JobException",
                "message": "Job strategy was canceled because event was set.",
            },
        },
    }


def test_job_exec_py_complete():
    rs: Result = (
        Workflow.from_conf(
            name="wf-run-python-raise-for-job",
            extras={"stage_raise_error": True},
        )
        .job("job-complete")
        .execute({})
    )
    assert rs.context == {
        "2150810470": {
            "matrix": {"sleep": "1"},
            "stages": {"success": {"outputs": {"result": "fast-success"}}},
        },
        "4855178605": {
            "matrix": {"sleep": "5"},
            "stages": {"success": {"outputs": {"result": "fast-success"}}},
        },
        "9873503202": {
            "matrix": {"sleep": "0.1"},
            "stages": {"success": {"outputs": {"result": "success"}}},
        },
    }


def test_job_exec_py_complete_not_parallel():
    workflow: Workflow = Workflow.from_conf(
        name="wf-run-python-raise-for-job",
        extras={"stage_raise_error": True},
    )
    job: Job = workflow.job("job-complete-not-parallel")
    rs: Result = job.execute({})
    assert rs.context == {
        "2150810470": {
            "matrix": {"sleep": "1"},
            "stages": {"success": {"outputs": {"result": "fast-success"}}},
        },
        "4855178605": {
            "matrix": {"sleep": "5"},
            "stages": {"success": {"outputs": {"result": "fast-success"}}},
        },
        "9873503202": {
            "matrix": {"sleep": "0.1"},
            "stages": {"success": {"outputs": {"result": "success"}}},
        },
    }

    output = {}
    job.set_outputs(rs.context, to=output)
    assert output == {
        "jobs": {
            "job-complete-not-parallel": {
                "strategies": {
                    "9873503202": {
                        "matrix": {"sleep": "0.1"},
                        "stages": {
                            "success": {"outputs": {"result": "success"}},
                        },
                    },
                    "4855178605": {
                        "matrix": {"sleep": "5"},
                        "stages": {
                            "success": {"outputs": {"result": "fast-success"}},
                        },
                    },
                    "2150810470": {
                        "matrix": {"sleep": "1"},
                        "stages": {
                            "success": {"outputs": {"result": "fast-success"}},
                        },
                    },
                },
            },
        },
    }


def test_job_exec_py_complete_raise():
    rs: Result = (
        Workflow.from_conf(
            "wf-run-python-raise-for-job",
            extras={"stage_raise_error": True},
        )
        .job("job-complete-raise")
        .execute(params={})
    )
    assert rs.context == {
        "2150810470": {
            "errors": {
                "message": (
                    "PyStage: ValueError: Testing raise error inside "
                    "PyStage!!!"
                ),
                "name": "StageException",
            },
            "matrix": {"sleep": "1"},
            "stages": {"7972360640": {"outputs": {}}},
        },
        "9112472804": {
            "errors": {
                "message": (
                    "PyStage: ValueError: Testing raise error inside "
                    "PyStage!!!"
                ),
                "name": "StageException",
            },
            "matrix": {"sleep": "4"},
            "stages": {"7972360640": {"outputs": {}}},
        },
        "9873503202": {
            "matrix": {"sleep": "0.1"},
            "stages": {
                "7972360640": {"outputs": {}},
                "raise-error": {"outputs": {"result": "success"}},
            },
        },
        "errors": {
            "2150810470": {
                "name": "JobException",
                "message": (
                    "Handler Error: StageException: PyStage: "
                    "ValueError: Testing raise error inside PyStage!!!"
                ),
            },
            "9112472804": {
                "name": "JobException",
                "message": (
                    "Handler Error: StageException: PyStage: "
                    "ValueError: Testing raise error inside PyStage!!!"
                ),
            },
        },
    }


def test_job_exec_runs_on_not_implement():
    job: Job = Workflow.from_conf(
        "wf-run-python-raise-for-job",
        extras={"stage_raise_error": True},
    ).job("job-fail-runs-on")
    rs: Result = job.execute({})
    assert rs.status == FAILED
    assert rs.context == {
        "errors": {
            "message": "Execute runs-on type: 'self_hosted' does not support yet.",
            "name": "JobException",
        }
    }
