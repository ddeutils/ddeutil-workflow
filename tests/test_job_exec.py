from ddeutil.workflow import Job, Workflow
from ddeutil.workflow.result import CANCEL, FAILED, SKIP, SUCCESS, Result

from .utils import MockEvent


def test_job_exec_py():
    job: Job = Workflow.from_conf(name="wf-run-common").job("demo-run")
    rs: Result = job.execute(params={"params": {"name": "Foo"}})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "EMPTY": {
            "status": SUCCESS,
            "matrix": {},
            "stages": {
                "hello-world": {
                    "outputs": {"x": "New Name"},
                    "status": SUCCESS,
                },
                "run-var": {"outputs": {"x": 1}, "status": SUCCESS},
            },
        },
    }

    output = job.set_outputs(rs.context, to={})
    assert output == {
        "jobs": {
            "demo-run": {
                "status": SUCCESS,
                "stages": {
                    "hello-world": {
                        "outputs": {"x": "New Name"},
                        "status": SUCCESS,
                    },
                    "run-var": {"outputs": {"x": 1}, "status": SUCCESS},
                },
            },
        },
    }

    # NOTE: Cancel job execution by set the event.
    event = MockEvent(n=0)
    rs: Result = job.execute(params={"params": {"name": "Foo"}}, event=event)
    assert rs.status == CANCEL
    assert rs.context == {
        "status": CANCEL,
        "errors": {
            "name": "JobCancelError",
            "message": "Execution was canceled from the event before start local job execution.",
        },
    }

    event = MockEvent(n=1)
    rs: Result = job.execute(params={"params": {"name": "Foo"}}, event=event)
    assert rs.status == CANCEL
    assert rs.context == {
        "status": CANCEL,
        "EMPTY": {
            "errors": {
                "message": "Strategy execution was canceled from the event before start stage execution.",
                "name": "JobCancelError",
            },
            "matrix": {},
            "stages": {},
            "status": CANCEL,
        },
        "errors": {
            "name": "JobCancelError",
            "message": "Strategy execution was canceled from the event before start stage execution.",
        },
    }

    event = MockEvent(n=2)
    rs: Result = job.execute(params={"params": {"name": "Foo"}}, event=event)
    assert rs.status == CANCEL
    assert rs.context == {
        "status": CANCEL,
        "EMPTY": {
            "errors": {
                "message": "Strategy execution was canceled from the event before start stage execution.",
                "name": "JobCancelError",
            },
            "matrix": {},
            "stages": {
                "hello-world": {"outputs": {"x": "New Name"}, "status": SUCCESS}
            },
            "status": CANCEL,
        },
        "errors": {
            "name": "JobCancelError",
            "message": "Strategy execution was canceled from the event before start stage execution.",
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
        "status": FAILED,
        "EMPTY": {
            "status": FAILED,
            "matrix": {},
            "stages": {
                "raise-error": {
                    "status": FAILED,
                    "outputs": {},
                    "errors": {
                        "name": "ValueError",
                        "message": "Testing raise error inside PyStage!!!",
                    },
                }
            },
            "errors": {
                "name": "JobError",
                "message": (
                    "Strategy execution was break because its nested-stage, "
                    "'raise-error', failed."
                ),
            },
        },
        "errors": {
            "name": "JobError",
            "message": (
                "Strategy execution was break because its nested-stage, "
                "'raise-error', failed."
            ),
        },
    }


def test_job_exec_py_not_set_output():
    workflow: Workflow = Workflow.from_conf(
        name="wf-run-python-raise", extras={"stage_default_id": False}
    )
    job: Job = workflow.job("second-job")
    rs: Result = job.execute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "EMPTY": {"status": SUCCESS, "matrix": {}, "stages": {}},
    }
    assert job.set_outputs(rs.context, to={}) == {
        "jobs": {"second-job": {"status": SUCCESS, "stages": {}}}
    }


def test_job_exec_py_fail_fast():
    rs: Result = (
        Workflow.from_conf(name="wf-run-python-raise-for-job")
        .job("job-fail-fast")
        .execute(params={})
    )
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "2150810470": {
            "status": SUCCESS,
            "matrix": {"sleep": "1"},
            "stages": {
                "success": {
                    "outputs": {"result": "fast-success"},
                    "status": SUCCESS,
                }
            },
        },
        "4855178605": {
            "status": SUCCESS,
            "matrix": {"sleep": "5"},
            "stages": {
                "success": {
                    "outputs": {"result": "fast-success"},
                    "status": SUCCESS,
                }
            },
        },
        "9873503202": {
            "status": SUCCESS,
            "matrix": {"sleep": "0.1"},
            "stages": {
                "success": {
                    "outputs": {"result": "success"},
                    "status": SUCCESS,
                }
            },
        },
    }


def test_job_exec_py_fail_fast_raise_catch():
    rs: Result = (
        Workflow.from_conf(
            name="wf-run-python-raise-for-job",
            extras={"stage_default_id": False},
        )
        .job("job-fail-fast-raise")
        .execute(params={})
    )
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "2150810470": {
            "status": FAILED,
            "matrix": {"sleep": "1"},
            "stages": {
                "raise-error": {
                    "outputs": {},
                    "errors": {
                        "name": "ValueError",
                        "message": "Testing raise error inside PyStage with the sleep not equal 4!!!",
                    },
                    "status": FAILED,
                }
            },
            "errors": {
                "name": "JobError",
                "message": "Strategy execution was break because its nested-stage, 'raise-error', failed.",
            },
        },
        "1067561285": {
            "status": CANCEL,
            "matrix": {"sleep": "2"},
            "stages": {},
            "errors": {
                "name": "JobCancelError",
                "message": "Strategy execution was canceled from the event before start stage execution.",
            },
        },
        "9112472804": {
            "status": CANCEL,
            "matrix": {"sleep": "4"},
            "stages": {},
            "errors": {
                "name": "JobCancelError",
                "message": "Strategy execution was canceled from the event before start stage execution.",
            },
        },
        "errors": {
            "2150810470": {
                "name": "JobError",
                "message": "Strategy execution was break because its nested-stage, 'raise-error', failed.",
            },
            "1067561285": {
                "name": "JobCancelError",
                "message": "Strategy execution was canceled from the event before start stage execution.",
            },
            "9112472804": {
                "name": "JobCancelError",
                "message": "Strategy execution was canceled from the event before start stage execution.",
            },
        },
    }


def test_job_exec_py_complete():
    rs: Result = (
        Workflow.from_conf(
            name="wf-run-python-raise-for-job",
        )
        .job("job-complete")
        .execute({})
    )
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "2150810470": {
            "status": SUCCESS,
            "matrix": {"sleep": "1"},
            "stages": {
                "success": {
                    "outputs": {"result": "fast-success"},
                    "status": SUCCESS,
                }
            },
        },
        "4855178605": {
            "status": SUCCESS,
            "matrix": {"sleep": "5"},
            "stages": {
                "success": {
                    "outputs": {"result": "fast-success"},
                    "status": SUCCESS,
                }
            },
        },
        "9873503202": {
            "status": SUCCESS,
            "matrix": {"sleep": "0.1"},
            "stages": {
                "success": {
                    "outputs": {"result": "success"},
                    "status": SUCCESS,
                }
            },
        },
    }


def test_job_exec_py_complete_not_parallel():
    workflow: Workflow = Workflow.from_conf(
        name="wf-run-python-raise-for-job",
    )
    job: Job = workflow.job("job-complete-not-parallel")
    rs: Result = job.execute({})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "2150810470": {
            "status": SUCCESS,
            "matrix": {"sleep": "1"},
            "stages": {
                "success": {
                    "outputs": {"result": "fast-success"},
                    "status": SUCCESS,
                }
            },
        },
        "4855178605": {
            "status": SUCCESS,
            "matrix": {"sleep": "5"},
            "stages": {
                "success": {
                    "outputs": {"result": "fast-success"},
                    "status": SUCCESS,
                }
            },
        },
        "9873503202": {
            "status": SUCCESS,
            "matrix": {"sleep": "0.1"},
            "stages": {
                "success": {"outputs": {"result": "success"}, "status": SUCCESS}
            },
        },
    }

    output = job.set_outputs(rs.context, to={})
    assert output == {
        "jobs": {
            "job-complete-not-parallel": {
                "status": SUCCESS,
                "strategies": {
                    "9873503202": {
                        "status": SUCCESS,
                        "matrix": {"sleep": "0.1"},
                        "stages": {
                            "success": {
                                "outputs": {"result": "success"},
                                "status": SUCCESS,
                            },
                        },
                    },
                    "4855178605": {
                        "status": SUCCESS,
                        "matrix": {"sleep": "5"},
                        "stages": {
                            "success": {
                                "outputs": {"result": "fast-success"},
                                "status": SUCCESS,
                            },
                        },
                    },
                    "2150810470": {
                        "status": SUCCESS,
                        "matrix": {"sleep": "1"},
                        "stages": {
                            "success": {
                                "outputs": {"result": "fast-success"},
                                "status": SUCCESS,
                            },
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
        )
        .job("job-complete-raise")
        .execute(params={})
    )
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "9873503202": {
            "status": SUCCESS,
            "matrix": {"sleep": "0.1"},
            "stages": {
                "7972360640": {"outputs": {}, "status": SUCCESS},
                "raise-error": {
                    "outputs": {"result": "success"},
                    "status": SUCCESS,
                },
            },
        },
        "2150810470": {
            "status": FAILED,
            "matrix": {"sleep": "1"},
            "stages": {
                "7972360640": {"outputs": {}, "status": SUCCESS},
                "raise-error": {
                    "outputs": {},
                    "errors": {
                        "name": "ValueError",
                        "message": "Testing raise error inside PyStage!!!",
                    },
                    "status": FAILED,
                },
            },
            "errors": {
                "name": "JobError",
                "message": (
                    "Strategy execution was break because its nested-stage, "
                    "'raise-error', failed."
                ),
            },
        },
        "9112472804": {
            "status": FAILED,
            "matrix": {"sleep": "4"},
            "stages": {
                "7972360640": {"outputs": {}, "status": SUCCESS},
                "raise-error": {
                    "outputs": {},
                    "errors": {
                        "name": "ValueError",
                        "message": "Testing raise error inside PyStage!!!",
                    },
                    "status": FAILED,
                },
            },
            "errors": {
                "name": "JobError",
                "message": (
                    "Strategy execution was break because its nested-stage, "
                    "'raise-error', failed."
                ),
            },
        },
        "errors": {
            "2150810470": {
                "name": "JobError",
                "message": (
                    "Strategy execution was break because its nested-stage, "
                    "'raise-error', failed."
                ),
            },
            "9112472804": {
                "name": "JobError",
                "message": (
                    "Strategy execution was break because its nested-stage, "
                    "'raise-error', failed."
                ),
            },
        },
    }


def test_job_exec_skipped():
    job: Job = Job.model_validate(
        {
            "id": "first-job",
            "desc": "Job Skip execution!!!",
            "if": "False",
            "stages": [{"name": "Echo empty", "echo": "Hello World"}],
        }
    )
    rs: Result = job.execute(params={})
    assert rs.status == SKIP
    assert rs.context == {"status": SKIP}

    job: Job = Job.model_validate(
        {
            "id": "first-job",
            "if": "True",
            "stages": [
                {
                    "name": "Echo empty",
                    "if": "False",
                    "echo": "Hello World",
                }
            ],
        }
    )
    rs: Result = job.execute(params={})
    assert rs.status == SKIP
    assert rs.context == {
        "status": SKIP,
        "EMPTY": {
            "status": SKIP,
            "matrix": {},
            "stages": {"2419214589": {"outputs": {}, "status": SKIP}},
        },
    }

    job: Job = Job.model_validate(
        {
            "id": "first-job",
            "strategy": {"matrix": {"number": [1, 2]}},
            "if": "True",
            "stages": [
                {
                    "name": "Echo empty",
                    "if": "False",
                    "echo": "Hello World",
                }
            ],
        }
    )
    rs: Result = job.execute(params={})
    assert rs.status == SKIP
    assert rs.context == {
        "status": SKIP,
        "3568447778": {
            "status": SKIP,
            "matrix": {"number": 1},
            "stages": {"2419214589": {"outputs": {}, "status": SKIP}},
        },
        "9176483042": {
            "status": SKIP,
            "matrix": {"number": 2},
            "stages": {"2419214589": {"outputs": {}, "status": SKIP}},
        },
    }


def test_job_exec_runs_on_not_implement():
    job: Job = Workflow.from_conf(
        "wf-run-python-raise-for-job",
    ).job("job-fail-runs-on")
    rs: Result = job.execute({})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "message": "Execute runs-on type: 'self_hosted' does not support yet.",
            "name": "JobError",
        },
    }


def test_job_exec_cancel():
    job: Job = Job.model_validate(
        {
            "id": "first-job",
            "stages": [{"name": "Echo empty", "echo": "Hello World"}],
        }
    )
    event = MockEvent(n=2)
    rs = job.execute({}, event=event)
    assert rs.status == CANCEL
    assert rs.context == {
        "status": CANCEL,
        "EMPTY": {
            "status": CANCEL,
            "matrix": {},
            "stages": {
                "2419214589": {
                    "outputs": {},
                    "errors": {
                        "name": "StageCancelError",
                        "message": "Execution was canceled from the event before start parallel.",
                    },
                    "status": CANCEL,
                },
            },
            "errors": {
                "name": "JobCancelError",
                "message": "Strategy execution was canceled from the event after end stage execution.",
            },
        },
        "errors": {
            "name": "JobCancelError",
            "message": "Strategy execution was canceled from the event after end stage execution.",
        },
    }
