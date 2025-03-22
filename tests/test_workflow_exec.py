from datetime import datetime
from unittest import mock

from ddeutil.workflow import Workflow
from ddeutil.workflow.conf import Config
from ddeutil.workflow.job import Job
from ddeutil.workflow.result import Result
from ddeutil.workflow.stages import CallStage

from .utils import dump_yaml_context


@mock.patch.object(Config, "max_job_parallel", 1)
def test_workflow_exec():
    job: Job = Job(
        stages=[{"name": "Sleep", "run": "import time\ntime.sleep(2)"}],
    )
    workflow: Workflow = Workflow(
        name="demo-workflow", jobs={"sleep-run": job, "sleep-again-run": job}
    )
    rs: Result = workflow.execute(params={})
    assert rs.status == 0
    assert rs.context == {
        "params": {},
        "jobs": {
            "sleep-again-run": {
                "stages": {"7972360640": {"outputs": {}}},
            },
        },
    }


@mock.patch.object(Config, "max_job_parallel", 1)
def test_workflow_exec_raise_timeout():
    job: Job = Job(
        stages=[{"name": "Sleep", "run": "import time\ntime.sleep(2)"}],
    )
    workflow: Workflow = Workflow(
        name="demo-workflow", jobs={"sleep-run": job, "sleep-again-run": job}
    )
    rs: Result = workflow.execute(params={}, timeout=1)
    assert rs.status == 1
    assert rs.context["errors"]["message"] == (
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
                "stages": {
                    "printing": {"outputs": {"x": "Local Workflow"}},
                    "setting-x": {"outputs": {"x": 1}},
                },
            },
            "second-job": {
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
                    "stages": {
                        "printing": {"outputs": {"x": "Local Workflow"}},
                        "setting-x": {"outputs": {"x": 1}},
                    },
                },
                "second-job": {
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
        "errors": {
            "class": rs.context["errors"]["class"],
            "name": "WorkflowException",
            "message": (
                "WorkflowException: Get job execution error first-job: "
                "JobException: Stage execution error: "
                "StageException: PyStage: \n\t"
                "ValueError: Testing raise error inside PyStage!!!"
            ),
        },
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
                "stages": {"1772094681": {"outputs": {}}},
            }
        },
        "errors": {
            "class": rs.context["errors"]["class"],
            "name": "WorkflowException",
            "message": (
                "WorkflowException: Get job execution error first-job: "
                "JobException: Stage execution error: "
                "StageException: PyStage: \n\t"
                "ValueError: Testing raise error inside PyStage!!!"
            ),
        },
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


def test_workflow_exec_needs():
    workflow = Workflow.from_loader(name="wf-run-depends", externals={})
    rs: Result = workflow.execute(params={"name": "bar"})
    assert {
        "params": {"name": "bar"},
        "jobs": {
            "final-job": {
                "stages": {
                    "8797330324": {
                        "outputs": {},
                    },
                },
            },
            "first-job": {
                "stages": {
                    "7824513474": {
                        "outputs": {},
                    },
                },
            },
            "second-job": {
                "stages": {
                    "1772094681": {
                        "outputs": {},
                    },
                },
            },
        },
    } == rs.context


def test_workflow_exec_needs_parallel():
    with mock.patch.object(Config, "max_job_parallel", 3):
        workflow = Workflow.from_loader(name="wf-run-depends", externals={})
        rs: Result = workflow.execute(params={"name": "bar"})
        assert {
            "params": {"name": "bar"},
            "jobs": {
                "final-job": {
                    "stages": {
                        "8797330324": {
                            "outputs": {},
                        },
                    },
                },
                "first-job": {
                    "stages": {
                        "7824513474": {
                            "outputs": {},
                        },
                    },
                },
                "second-job": {
                    "stages": {
                        "1772094681": {
                            "outputs": {},
                        },
                    },
                },
            },
        } == rs.context


def test_workflow_exec_call(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_call_csv_to_parquet.yml",
        data="""
        tmp-wf-call-csv-to-parquet:
          type: Workflow
          params:
            run-date: datetime
            source: str
            sink: str
          jobs:
            extract-load:
              stages:
                - name: "Extract & Load Local System"
                  id: extract-load
                  uses: tasks/el-csv-to-parquet@polars-dir
                  with:
                    source: ${{ params.source }}
                    sink: ${{ params.sink }}
        """,
    ):
        workflow = Workflow.from_loader(
            name="tmp-wf-call-csv-to-parquet",
            externals={},
        )

        # NOTE: execute from the call stage model
        stage: CallStage = workflow.job("extract-load").stage("extract-load")
        rs = stage.handler_execute(
            params={
                "params": {
                    "run-date": datetime(2024, 1, 1),
                    "source": "ds_csv_local_file",
                    "sink": "ds_parquet_local_file_dir",
                },
            }
        )
        assert 0 == rs.status
        assert {"records": 1} == rs.context

        # NOTE: execute from the job model
        job: Job = workflow.job("extract-load")
        rs = job.execute(
            params={
                "params": {
                    "run-date": datetime(2024, 1, 1),
                    "source": "ds_csv_local_file",
                    "sink": "ds_parquet_local_file_dir",
                },
            },
        )
        assert {
            "1354680202": {
                "matrix": {},
                "stages": {"extract-load": {"outputs": {"records": 1}}},
            },
        } == rs.context

        rs = workflow.execute(
            params={
                "run-date": datetime(2024, 1, 1),
                "source": "ds_csv_local_file",
                "sink": "ds_parquet_local_file_dir",
            },
        )
        assert 0 == rs.status
        assert {
            "params": {
                "run-date": datetime(2024, 1, 1),
                "source": "ds_csv_local_file",
                "sink": "ds_parquet_local_file_dir",
            },
            "jobs": {
                "extract-load": {
                    "stages": {
                        "extract-load": {
                            "outputs": {"records": 1},
                        },
                    },
                },
            },
        } == rs.context


def test_workflow_exec_call_with_prefix(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_call_mssql_proc.yml",
        data="""
        tmp-wf-call-mssql-proc:
          type: Workflow
          params:
            run_date: datetime
            sp_name: str
            source_name: str
            target_name: str
          jobs:
            transform:
              stages:
                - name: "Transform Data in MS SQL Server"
                  id: transform
                  uses: tasks/mssql-proc@odbc
                  with:
                    _exec: ${{ params.sp_name }}
                    params:
                      run_mode: "T"
                      run_date: ${{ params.run_date }}
                      source: ${{ params.source_name }}
                      target: ${{ params.target_name }}
        """,
    ):
        workflow = Workflow.from_loader(name="tmp-wf-call-mssql-proc")
        rs = workflow.execute(
            params={
                "run_date": datetime(2024, 1, 1),
                "sp_name": "proc-name",
                "source_name": "src",
                "target_name": "tgt",
            },
        )
        print(rs)
