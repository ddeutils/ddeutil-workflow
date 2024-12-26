from datetime import datetime
from unittest import mock

from ddeutil.workflow import Workflow
from ddeutil.workflow.conf import Config
from ddeutil.workflow.job import Job
from ddeutil.workflow.utils import Result


@mock.patch.object(Config, "max_job_parallel", 1)
def test_workflow_exec():
    job: Job = Job(
        stages=[{"name": "Sleep", "run": "import time\ntime.sleep(2)"}],
    )
    workflow: Workflow = Workflow(
        name="demo-workflow", jobs={"sleep-run": job, "sleep-again-run": job}
    )
    workflow.execute(params={})


@mock.patch.object(Config, "max_job_parallel", 1)
def test_workflow_exec_timeout():
    job: Job = Job(
        stages=[{"name": "Sleep", "run": "import time\ntime.sleep(2)"}],
    )
    workflow: Workflow = Workflow(
        name="demo-workflow", jobs={"sleep-run": job, "sleep-again-run": job}
    )
    rs: Result = workflow.execute(params={}, timeout=1)
    assert rs.context["error_message"] == (
        "WorkflowException: Execution: 'demo-workflow' was timeout."
    )


def test_workflow_exec_py():
    workflow = Workflow.from_loader(name="wf-run-python")
    rs: Result = workflow.execute(
        params={
            "author-run": "Local Workflow",
            "run-date": "2024-01-01",
        },
    )
    assert 0 == rs.status
    assert {
        "params": {
            "author-run": "Local Workflow",
            "run-date": datetime(2024, 1, 1, 0, 0),
        },
        "jobs": {
            "first-job": {
                "matrix": {},
                "stages": {
                    "printing": {"outputs": {"x": "Local Workflow"}},
                    "setting-x": {"outputs": {"x": 1}},
                },
            },
            "second-job": {
                "matrix": {},
                "stages": {
                    "create-func": {
                        "outputs": {
                            "var_inside": "Create Function Inside",
                            "echo": "echo",
                        },
                    },
                    "call-func": {"outputs": {}},
                    "9150930869": {"outputs": {}},
                },
            },
            "final-job": {
                "matrix": {},
                "stages": {
                    "1772094681": {
                        "outputs": {
                            "return_code": 0,
                            "stdout": "Hello World",
                            "stderr": None,
                        }
                    }
                },
            },
        },
    } == rs.context


@mock.patch.object(Config, "max_job_parallel", 2)
def test_workflow_exec_parallel():
    job: Job = Job(
        stages=[{"name": "Sleep", "run": "import time\ntime.sleep(2)"}],
    )
    workflow: Workflow = Workflow(
        name="demo-workflow", jobs={"sleep-run": job, "sleep-again-run": job}
    )
    workflow.execute(params={})


@mock.patch.object(Config, "max_job_parallel", 2)
def test_workflow_exec_parallel_timeout():
    job: Job = Job(
        stages=[{"name": "Sleep", "run": "import time\ntime.sleep(2)"}],
    )
    workflow: Workflow = Workflow(
        name="demo-workflow",
        jobs={
            "sleep-run": job,
            "sleep-again-run": job.model_copy(update={"needs": ["sleep-run"]}),
        },
    )
    workflow.execute(params={}, timeout=1)


def test_workflow_exec_py_with_parallel():
    with mock.patch.object(Config, "max_job_parallel", 3):
        workflow = Workflow.from_loader(name="wf-run-python")
        rs: Result = workflow.execute(
            params={
                "author-run": "Local Workflow",
                "run-date": "2024-01-01",
            },
        )
        assert 0 == rs.status
        assert {
            "params": {
                "author-run": "Local Workflow",
                "run-date": datetime(2024, 1, 1, 0, 0),
            },
            "jobs": {
                "first-job": {
                    "matrix": {},
                    "stages": {
                        "printing": {"outputs": {"x": "Local Workflow"}},
                        "setting-x": {"outputs": {"x": 1}},
                    },
                },
                "second-job": {
                    "matrix": {},
                    "stages": {
                        "create-func": {
                            "outputs": {
                                "var_inside": "Create Function Inside",
                                "echo": "echo",
                            },
                        },
                        "call-func": {"outputs": {}},
                        "9150930869": {"outputs": {}},
                    },
                },
                "final-job": {
                    "matrix": {},
                    "stages": {
                        "1772094681": {
                            "outputs": {
                                "return_code": 0,
                                "stdout": "Hello World",
                                "stderr": None,
                            }
                        }
                    },
                },
            },
        } == rs.context


def test_workflow_exec_py_raise():
    workflow = Workflow.from_loader("wf-run-python-raise")
    rs = workflow.execute(params={})
    assert rs.status == 1
    assert rs.context == {
        "params": {},
        "jobs": {},
        "error": rs.context["error"],
        "error_message": (
            "WorkflowException: Get job execution error first-job: "
            "JobException: Get stage execution error: "
            "StageException: PyStage: \n\t"
            "ValueError: Testing raise error inside PyStage!!!"
        ),
    }


@mock.patch.object(Config, "max_job_parallel", 2)
def test_workflow_exec_py_raise_parallel():
    workflow = Workflow.from_loader("wf-run-python-raise")
    rs = workflow.execute(params={})
    assert rs.status == 1
    assert rs.context == {
        "params": {},
        "jobs": {
            "second-job": {
                "matrix": {},
                "stages": {"1772094681": {"outputs": {}}},
            }
        },
        "error": rs.context["error"],
        "error_message": (
            "WorkflowException: Get job execution error first-job: "
            "JobException: Get stage execution error: "
            "StageException: PyStage: \n\t"
            "ValueError: Testing raise error inside PyStage!!!"
        ),
    }


def test_workflow_exec_with_matrix():
    workflow: Workflow = Workflow.from_loader(name="wf-run-matrix")
    rs: Result = workflow.execute(params={"source": "src", "target": "tgt"})
    assert {
        "params": {"source": "src", "target": "tgt"},
        "jobs": {
            "multiple-system": {
                "strategies": {
                    "9696245497": {
                        "matrix": {
                            "table": "customer",
                            "system": "csv",
                            "partition": 2,
                        },
                        "stages": {
                            "customer-2": {"outputs": {"records": 1}},
                            "end-stage": {"outputs": {"passing_value": 10}},
                        },
                    },
                    "8141249744": {
                        "matrix": {
                            "table": "customer",
                            "system": "csv",
                            "partition": 3,
                        },
                        "stages": {
                            "customer-3": {"outputs": {"records": 1}},
                            "end-stage": {"outputs": {"passing_value": 10}},
                        },
                    },
                    "3590257855": {
                        "matrix": {
                            "table": "sales",
                            "system": "csv",
                            "partition": 1,
                        },
                        "stages": {
                            "sales-1": {"outputs": {"records": 1}},
                            "end-stage": {"outputs": {"passing_value": 10}},
                        },
                    },
                    "3698996074": {
                        "matrix": {
                            "table": "sales",
                            "system": "csv",
                            "partition": 2,
                        },
                        "stages": {
                            "sales-2": {"outputs": {"records": 1}},
                            "end-stage": {"outputs": {"passing_value": 10}},
                        },
                    },
                    "4390593385": {
                        "matrix": {
                            "table": "customer",
                            "system": "csv",
                            "partition": 4,
                        },
                        "stages": {
                            "customer-4": {"outputs": {"records": 1}},
                            "end-stage": {"outputs": {"passing_value": 10}},
                        },
                    },
                },
            },
        },
    } == rs.context
