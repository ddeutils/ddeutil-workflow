import shutil
from datetime import datetime
from textwrap import dedent
from unittest.mock import patch

from ddeutil.core import getdot
from ddeutil.workflow import (
    CANCEL,
    FAILED,
    SKIP,
    SUCCESS,
    UTC,
    Job,
    Result,
    Workflow,
    extract_call,
)

from .utils import MockEvent, dump_yaml_context


def test_workflow_exec():
    job: Job = Job(
        stages=[{"name": "Sleep", "run": "import time\ntime.sleep(2)"}],
    )
    workflow: Workflow = Workflow(
        name="demo-workflow",
        jobs={"sleep-run": job, "sleep-again-run": job},
    )
    assert all(j in workflow.jobs for j in ("sleep-run", "sleep-again-run"))

    rs: Result = workflow.execute(params={}, max_job_parallel=1)
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


def test_workflow_exec_timeout():
    job: Job = Job(
        stages=[
            {"name": "Sleep", "run": "import time\ntime.sleep(2)"},
            {"name": "Echo Last Stage", "echo": "the last stage"},
        ],
    )
    workflow: Workflow = Workflow(
        name="demo-workflow",
        jobs={
            "sleep-run": job,
            "sleep-again-run": job,
        },
    )
    rs: Result = workflow.execute(params={}, timeout=1.25, max_job_parallel=1)
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "params": {},
        "jobs": {
            "sleep-run": {
                "status": CANCEL,
                "stages": {"7972360640": {"outputs": {}, "status": SUCCESS}},
                "errors": {
                    "name": "JobCancelError",
                    "message": (
                        "Strategy execution was canceled from the event before "
                        "start stage execution."
                    ),
                },
            }
        },
        "errors": {
            "name": "WorkflowTimeoutError",
            "message": "'demo-workflow' was timeout because it use exec time more than 1.25 seconds.",
        },
    }


def test_workflow_exec_raise_event_set():
    job: Job = Job(
        stages=[{"name": "Echo Last Stage", "echo": "the last stage"}],
    )
    workflow: Workflow = Workflow(
        name="demo-workflow",
        jobs={"sleep-run": job, "sleep-again-run": job},
    )
    event = MockEvent(n=0)
    rs: Result = workflow.execute(
        params={}, timeout=1, event=event, max_job_parallel=1
    )
    assert rs.status == CANCEL
    assert rs.context == {
        "status": CANCEL,
        "jobs": {},
        "params": {},
        "errors": {
            "name": "WorkflowCancelError",
            "message": (
                "Execution was canceled from the event was set before workflow "
                "execution."
            ),
        },
    }


def test_workflow_exec_py():
    workflow = Workflow.from_conf(name="wf-run-python")
    rs: Result = workflow.execute(
        params={
            "author-run": "Local Workflow",
            "run-date": "2024-01-01",
        },
    )
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "params": {
            "author-run": "Local Workflow",
            "run-date": datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
        },
        "jobs": {
            "first-job": {
                "status": SUCCESS,
                "stages": {
                    "printing": {
                        "outputs": {"x": "Local Workflow"},
                        "status": SUCCESS,
                    },
                    "setting-x": {
                        "outputs": {"x": 1},
                        "status": SUCCESS,
                    },
                },
            },
            "second-job": {
                "status": SUCCESS,
                "stages": {
                    "create-func": {
                        "status": SUCCESS,
                        "outputs": {
                            "var_inside": "Create Function Inside",
                            "echo": "echo",
                        },
                    },
                    "call-func": {
                        "outputs": {},
                        "status": SUCCESS,
                    },
                    "9150930869": {
                        "outputs": {},
                        "status": SUCCESS,
                    },
                },
            },
            "final-job": {
                "status": SUCCESS,
                "stages": {
                    "1772094681": {
                        "status": SUCCESS,
                        "outputs": {
                            "return_code": 0,
                            "stdout": "Hello World",
                            "stderr": None,
                        },
                    }
                },
            },
        },
    }


def test_workflow_exec_parallel():
    job: Job = Job(
        stages=[{"name": "Sleep", "run": "import time\ntime.sleep(2)"}],
    )
    workflow: Workflow = Workflow(
        name="demo-workflow", jobs={"sleep-run": job, "sleep-again-run": job}
    )
    rs: Result = workflow.execute(params={}, max_job_parallel=2)
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


def test_workflow_exec_parallel_timeout():
    job: Job = Job(
        stages=[
            {"name": "Sleep", "run": "import time\ntime.sleep(2)"},
            {"name": "Echo Last Stage", "echo": "the last stage"},
        ],
    )
    workflow: Workflow = Workflow(
        name="demo-workflow",
        jobs={
            "sleep-run": job,
            "sleep-again-run": job.model_copy(update={"needs": ["sleep-run"]}),
        },
        extras={"stage_default_id": False},
    )
    rs: Result = workflow.execute(params={}, timeout=1.25, max_job_parallel=2)
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "params": {},
        "jobs": {
            "sleep-run": {
                "status": CANCEL,
                "stages": {},
                "errors": {
                    "name": "JobCancelError",
                    "message": (
                        "Strategy execution was canceled from the event before "
                        "start stage execution."
                    ),
                },
            },
        },
        "errors": {
            "name": "WorkflowTimeoutError",
            "message": (
                "'demo-workflow' was timeout because it use exec time more "
                "than 1.25 seconds."
            ),
        },
    }


def test_workflow_exec_py_with_parallel():
    workflow = Workflow.from_conf(name="wf-run-python")
    rs: Result = workflow.execute(
        params={
            "author-run": "Local Workflow",
            "run-date": "2024-01-01",
        },
        max_job_parallel=3,
    )
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "params": {
            "author-run": "Local Workflow",
            "run-date": datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
        },
        "jobs": {
            "first-job": {
                "status": SUCCESS,
                "stages": {
                    "printing": {
                        "outputs": {"x": "Local Workflow"},
                        "status": SUCCESS,
                    },
                    "setting-x": {"outputs": {"x": 1}, "status": SUCCESS},
                },
            },
            "second-job": {
                "status": SUCCESS,
                "stages": {
                    "create-func": {
                        "outputs": {
                            "var_inside": "Create Function Inside",
                            "echo": "echo",
                        },
                        "status": SUCCESS,
                    },
                    "call-func": {"outputs": {}, "status": SUCCESS},
                    "9150930869": {"outputs": {}, "status": SUCCESS},
                },
            },
            "final-job": {
                "status": SUCCESS,
                "stages": {
                    "1772094681": {
                        "outputs": {
                            "return_code": 0,
                            "stdout": "Hello World",
                            "stderr": None,
                        },
                        "status": SUCCESS,
                    }
                },
            },
        },
    }


def test_workflow_exec_py_raise():
    rs: Result = Workflow.from_conf("wf-run-python-raise").execute(
        params={}, max_job_parallel=1
    )
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "WorkflowError",
            "message": "Job execution, 'first-job', was failed.",
        },
        "params": {},
        "jobs": {
            "first-job": {
                "status": FAILED,
                "stages": {
                    "raise-error": {
                        "outputs": {},
                        "errors": {
                            "name": "ValueError",
                            "message": "Testing raise error inside PyStage!!!",
                        },
                        "status": FAILED,
                    }
                },
                "errors": {
                    "name": "JobError",
                    "message": "Strategy execution was break because its nested-stage, 'raise-error', failed.",
                },
            },
            "second-job": {
                "status": SUCCESS,
                "stages": {"1772094681": {"outputs": {}, "status": SUCCESS}},
            },
        },
    }


def test_workflow_exec_py_raise_parallel():
    event = MockEvent(n=10)
    rs: Result = Workflow.from_conf("wf-run-python-raise").execute(
        params={}, max_job_parallel=2, event=event
    )
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "WorkflowError",
            "message": "Job execution, 'first-job', was failed.",
        },
        "params": {},
        "jobs": {
            "first-job": {
                "status": FAILED,
                "stages": {
                    "raise-error": {
                        "outputs": {},
                        "errors": {
                            "name": "ValueError",
                            "message": "Testing raise error inside PyStage!!!",
                        },
                        "status": FAILED,
                    }
                },
                "errors": {
                    "name": "JobError",
                    "message": "Strategy execution was break because its nested-stage, 'raise-error', failed.",
                },
            },
            "second-job": {
                "status": SUCCESS,
                "stages": {"1772094681": {"outputs": {}, "status": SUCCESS}},
            },
        },
    }


def test_workflow_exec_with_matrix():
    workflow: Workflow = Workflow.from_conf(name="wf-run-matrix")
    rs: Result = workflow.execute(params={"source": "src", "target": "tgt"})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "params": {"source": "src", "target": "tgt"},
        "jobs": {
            "multiple-system": {
                "strategies": {
                    "9696245497": {
                        "status": SUCCESS,
                        "matrix": {
                            "table": "customer",
                            "system": "csv",
                            "partition": 2,
                        },
                        "stages": {
                            "customer-2": {
                                "outputs": {"records": 1},
                                "status": SUCCESS,
                            },
                            "end-stage": {
                                "outputs": {"passing_value": 10},
                                "status": SUCCESS,
                            },
                        },
                    },
                    "8141249744": {
                        "status": SUCCESS,
                        "matrix": {
                            "table": "customer",
                            "system": "csv",
                            "partition": 3,
                        },
                        "stages": {
                            "customer-3": {
                                "outputs": {"records": 1},
                                "status": SUCCESS,
                            },
                            "end-stage": {
                                "outputs": {"passing_value": 10},
                                "status": SUCCESS,
                            },
                        },
                    },
                    "3590257855": {
                        "status": SUCCESS,
                        "matrix": {
                            "table": "sales",
                            "system": "csv",
                            "partition": 1,
                        },
                        "stages": {
                            "sales-1": {
                                "outputs": {"records": 1},
                                "status": SUCCESS,
                            },
                            "end-stage": {
                                "outputs": {"passing_value": 10},
                                "status": SUCCESS,
                            },
                        },
                    },
                    "3698996074": {
                        "status": SUCCESS,
                        "matrix": {
                            "table": "sales",
                            "system": "csv",
                            "partition": 2,
                        },
                        "stages": {
                            "sales-2": {
                                "outputs": {"records": 1},
                                "status": SUCCESS,
                            },
                            "end-stage": {
                                "outputs": {"passing_value": 10},
                                "status": SUCCESS,
                            },
                        },
                    },
                    "4390593385": {
                        "status": SUCCESS,
                        "matrix": {
                            "table": "customer",
                            "system": "csv",
                            "partition": 4,
                        },
                        "stages": {
                            "customer-4": {
                                "outputs": {"records": 1},
                                "status": SUCCESS,
                            },
                            "end-stage": {
                                "outputs": {"passing_value": 10},
                                "status": SUCCESS,
                            },
                        },
                    },
                },
                "status": SUCCESS,
            }
        },
    }


def test_workflow_exec_needs():
    workflow = Workflow.from_conf(name="wf-run-depends")
    rs: Result = workflow.execute(params={"name": "bar"})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "params": {"name": "bar"},
        "jobs": {
            "final-job": {
                "status": SUCCESS,
                "stages": {"8797330324": {"outputs": {}, "status": SUCCESS}},
            },
            "second-job": {
                "status": SUCCESS,
                "stages": {"1772094681": {"outputs": {}, "status": SUCCESS}},
            },
            "first-job": {
                "status": SUCCESS,
                "stages": {"7824513474": {"outputs": {}, "status": SUCCESS}},
            },
        },
    }


def test_workflow_exec_needs_condition():
    workflow = Workflow.from_conf(name="wf-run-depends-condition")
    rs: Result = workflow.execute(params={"name": "bar"})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "params": {"name": "bar"},
        "jobs": {
            "second-job": {"status": SKIP},
            "first-job": {"status": SKIP},
            "final-job": {
                "status": SUCCESS,
                "stages": {"8797330324": {"outputs": {}, "status": SUCCESS}},
            },
        },
    }


def test_workflow_exec_needs_parallel():
    workflow = Workflow.from_conf(name="wf-run-depends", extras={})
    rs: Result = workflow.execute(params={"name": "bar"}, max_job_parallel=3)
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "params": {"name": "bar"},
        "jobs": {
            "final-job": {
                "status": SUCCESS,
                "stages": {"8797330324": {"outputs": {}, "status": SUCCESS}},
            },
            "second-job": {
                "status": SUCCESS,
                "stages": {"1772094681": {"outputs": {}, "status": SUCCESS}},
            },
            "first-job": {
                "status": SUCCESS,
                "stages": {"7824513474": {"outputs": {}, "status": SUCCESS}},
            },
        },
    }


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
                  uses: tasks/simple-task@demo
                  with:
                    source: ${{ params.source }}
                    sink: ${{ params.sink }}
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-call-csv-to-parquet")
        rs: Result = workflow.execute(
            params={
                "run-date": datetime(2024, 1, 1),
                "source": "ds_csv_local_file",
                "sink": "ds_parquet_local_file_dir",
            },
        )
        assert rs.status == SUCCESS
        assert rs.context == {
            "status": SUCCESS,
            "params": {
                "run-date": datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
                "source": "ds_csv_local_file",
                "sink": "ds_parquet_local_file_dir",
            },
            "jobs": {
                "extract-load": {
                    "status": SUCCESS,
                    "stages": {
                        "extract-load": {
                            "outputs": {"records": 1},
                            "status": SUCCESS,
                        }
                    },
                }
            },
        }


def test_workflow_exec_call_override_registry(test_path):
    task_path = test_path.parent / "mock_tests"
    task_path.mkdir(exist_ok=True)
    (task_path / "__init__.py").open(mode="w")
    (task_path / "mock_tasks").mkdir(exist_ok=True)

    with (task_path / "mock_tasks/__init__.py").open(mode="w") as f:
        f.write(
            dedent(
                """
            from ddeutil.workflow import tag, Result

            @tag("v1", alias="get-info")
            def get_info(result: Result):
                result.trace.info("... [CALLER]: Info from mock tasks")
                return {"get-info": "success"}
            """.strip(
                    "\n"
                )
            )
        )

    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_exec_call_override.yml",
        data="""
        tmp-wf-exec-call-override:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Call from mock tasks"
                  uses: mock_tasks/get-info@v1
        """,
    ):
        func = extract_call("mock_tasks/get-info@v1", registries=["mock_tests"])
        assert func().name == "get-info"

        workflow = Workflow.from_conf(
            name="tmp-wf-exec-call-override",
            extras={"registry_caller": ["mock_tests"]},
        )
        rs: Result = workflow.execute(params={})
        assert rs.status == SUCCESS
        assert rs.context == {
            "status": SUCCESS,
            "params": {},
            "jobs": {
                "first-job": {
                    "status": SUCCESS,
                    "stages": {
                        "4030788970": {
                            "outputs": {"get-info": "success"},
                            "status": SUCCESS,
                        }
                    },
                }
            },
        }

    shutil.rmtree(task_path)


def test_workflow_exec_call_with_prefix(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_call_private_args.yml",
        data="""
        tmp-wf-call-private-args:
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
                  uses: tasks/private-args-task@demo
                  with:
                    exec: ${{ params.sp_name }}
                    params:
                      run_mode: "T"
                      run_date: ${{ params.run_date }}
                      source: ${{ params.source_name }}
                      target: ${{ params.target_name }}
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-call-private-args")
        rs = workflow.execute(
            params={
                "run_date": datetime(2024, 1, 1),
                "sp_name": "proc-name",
                "source_name": "src",
                "target_name": "tgt",
            },
        )
        assert rs.status == SUCCESS
        assert rs.context == {
            "status": SUCCESS,
            "params": {
                "run_date": datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
                "sp_name": "proc-name",
                "source_name": "src",
                "target_name": "tgt",
            },
            "jobs": {
                "transform": {
                    "status": SUCCESS,
                    "stages": {
                        "transform": {
                            "outputs": {
                                "exec": "proc-name",
                                "params": {
                                    "run_mode": "T",
                                    "run_date": datetime(
                                        2024, 1, 1, 0, 0, tzinfo=UTC
                                    ),
                                    "source": "src",
                                    "target": "tgt",
                                },
                            },
                            "status": SUCCESS,
                        }
                    },
                }
            },
        }


def test_workflow_exec_trigger():
    workflow = Workflow.from_conf(name="wf-trigger", extras={})
    job = workflow.job("trigger-job")
    rs = job.set_outputs(job.execute(params={}).context, to={})
    assert {
        "author-run": "Trigger Runner",
        "run-date": datetime(2024, 8, 1, tzinfo=UTC),
    } == getdot("jobs.trigger-job.stages.trigger-stage.outputs.params", rs)


def test_workflow_exec_foreach(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_foreach.yml",
        data="""
        tmp-wf-foreach:
          type: Workflow
          jobs:
            transform:
              stages:
                - name: "Get Items before run foreach"
                  id: get-items
                  uses: tasks/get-items@demo
                - name: "Create variable"
                  id: create-variable
                  run: |
                    foo: str = "bar"
                - name: "For-each item"
                  id: foreach-stage
                  foreach: ${{ stages.get-items.outputs.items }}
                  stages:
                    - name: "Echo stage"
                      echo: |
                        Start run with item ${{ item }}
                        Import variable ${{ stages.create-variable.outputs.foo }}
                    - name: "Final Echo"
                      if: ${{ item }} == 4
                      echo: |
                        Final run
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-foreach")
        rs = workflow.execute(params={})
        assert rs.status == SUCCESS
        assert rs.context == {
            "status": SUCCESS,
            "params": {},
            "jobs": {
                "transform": {
                    "status": SUCCESS,
                    "stages": {
                        "get-items": {
                            "outputs": {"items": [1, 2, 3, 4]},
                            "status": SUCCESS,
                        },
                        "create-variable": {
                            "outputs": {"foo": "bar"},
                            "status": SUCCESS,
                        },
                        "foreach-stage": {
                            "outputs": {
                                "items": [1, 2, 3, 4],
                                "foreach": {
                                    1: {
                                        "status": SUCCESS,
                                        "item": 1,
                                        "stages": {
                                            "2709471980": {
                                                "outputs": {},
                                                "status": SUCCESS,
                                            },
                                            "9263488742": {
                                                "outputs": {},
                                                "status": SKIP,
                                            },
                                        },
                                    },
                                    2: {
                                        "status": SUCCESS,
                                        "item": 2,
                                        "stages": {
                                            "2709471980": {
                                                "outputs": {},
                                                "status": SUCCESS,
                                            },
                                            "9263488742": {
                                                "outputs": {},
                                                "status": SKIP,
                                            },
                                        },
                                    },
                                    3: {
                                        "status": SUCCESS,
                                        "item": 3,
                                        "stages": {
                                            "2709471980": {
                                                "outputs": {},
                                                "status": SUCCESS,
                                            },
                                            "9263488742": {
                                                "outputs": {},
                                                "status": SKIP,
                                            },
                                        },
                                    },
                                    4: {
                                        "status": SUCCESS,
                                        "item": 4,
                                        "stages": {
                                            "2709471980": {
                                                "outputs": {},
                                                "status": SUCCESS,
                                            },
                                            "9263488742": {
                                                "outputs": {},
                                                "status": SUCCESS,
                                            },
                                        },
                                    },
                                },
                            },
                            "status": SUCCESS,
                        },
                    },
                }
            },
        }


def test_workflow_exec_foreach_get_inside(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_foreach_get_inside.yml",
        data="""
        tmp-wf-foreach-inside:
          type: Workflow
          jobs:
            transform:
              stages:
                - name: "Get Items before run foreach"
                  id: get-items
                  uses: tasks/get-items@demo
                - name: "Create variable"
                  id: create-variable
                  run: |
                    foo: str = "bar"
                - name: "For-each item"
                  id: foreach-stage
                  foreach: ${{ stages.get-items.outputs.items }}
                  stages:
                    - name: "Echo stage"
                      id: prepare-variable
                      run: |
                        foo: str = 'baz${{ item }}'
                    - name: "Final Echo"
                      if: ${{ item }} == 4
                      echo: |
                        This is the final foo, it be: ${{ stages.prepare-variable.outputs.foo }}
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-foreach-inside")
        rs = workflow.execute(params={})
        assert rs.status == SUCCESS
        assert rs.context == {
            "status": SUCCESS,
            "params": {},
            "jobs": {
                "transform": {
                    "status": SUCCESS,
                    "stages": {
                        "get-items": {
                            "outputs": {"items": [1, 2, 3, 4]},
                            "status": SUCCESS,
                        },
                        "create-variable": {
                            "outputs": {"foo": "bar"},
                            "status": SUCCESS,
                        },
                        "foreach-stage": {
                            "outputs": {
                                "items": [1, 2, 3, 4],
                                "foreach": {
                                    1: {
                                        "status": SUCCESS,
                                        "item": 1,
                                        "stages": {
                                            "prepare-variable": {
                                                "outputs": {"foo": "baz1"},
                                                "status": SUCCESS,
                                            },
                                            "9263488742": {
                                                "outputs": {},
                                                "status": SKIP,
                                            },
                                        },
                                    },
                                    2: {
                                        "status": SUCCESS,
                                        "item": 2,
                                        "stages": {
                                            "prepare-variable": {
                                                "outputs": {"foo": "baz2"},
                                                "status": SUCCESS,
                                            },
                                            "9263488742": {
                                                "outputs": {},
                                                "status": SKIP,
                                            },
                                        },
                                    },
                                    3: {
                                        "status": SUCCESS,
                                        "item": 3,
                                        "stages": {
                                            "prepare-variable": {
                                                "outputs": {"foo": "baz3"},
                                                "status": SUCCESS,
                                            },
                                            "9263488742": {
                                                "outputs": {},
                                                "status": SKIP,
                                            },
                                        },
                                    },
                                    4: {
                                        "status": SUCCESS,
                                        "item": 4,
                                        "stages": {
                                            "prepare-variable": {
                                                "outputs": {"foo": "baz4"},
                                                "status": SUCCESS,
                                            },
                                            "9263488742": {
                                                "outputs": {},
                                                "status": SUCCESS,
                                            },
                                        },
                                    },
                                },
                            },
                            "status": SUCCESS,
                        },
                    },
                }
            },
        }


def test_workflow_exec_raise_param(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_exec_raise_param.yml",
        data="""
        tmp-wf-exec-raise-param:
          type: Workflow
          params:
            name:
              desc: "A name parameter of this workflow."
              type: str
          jobs:
            start-job:
              stages:
                - name: "Get param that not set"
                  id: get-param
                  echo: "Passing name ${{ params.name }}"

                - name: "Call after above stage raise"
                  id: check
                  echo: "Hello after Raise Error"
        """,
    ):
        rs: Result = Workflow.from_conf(
            "tmp-wf-exec-raise-param",
        ).execute(params={"stream": "demo-stream"}, max_job_parallel=1)
        assert rs.status == FAILED
        assert rs.context == {
            "status": FAILED,
            "errors": {
                "name": "WorkflowError",
                "message": "Job execution, 'start-job', was failed.",
            },
            "params": {"stream": "demo-stream"},
            "jobs": {
                "start-job": {
                    "status": FAILED,
                    "stages": {
                        "get-param": {
                            "outputs": {},
                            "errors": {
                                "name": "UtilError",
                                "message": "Parameters does not get dot with caller: 'params.name'.",
                            },
                            "status": FAILED,
                        }
                    },
                    "errors": {
                        "name": "JobError",
                        "message": "Strategy execution was break because its nested-stage, 'get-param', failed.",
                    },
                }
            },
        }


def test_workflow_exec_raise_from_job_exec():
    with patch(
        "ddeutil.workflow.job.Job.execute",
        side_effect=Exception("some error on the job execution."),
    ):
        workflow = Workflow.model_validate(
            {
                "name": "tmp-wf-exec-raise",
                "jobs": {
                    "first-job": {
                        "stages": [
                            {"name": "Some Stage 1", "echo": "Start stage 1."}
                        ]
                    },
                    "second-job": {
                        "stages": [
                            {"name": "Some Stage 2", "echo": "Start stage 2."}
                        ]
                    },
                },
            }
        )
        rs = workflow.execute({})
        assert rs.status == FAILED

    with patch(
        "ddeutil.workflow.job.Job.execute",
        side_effect=Exception("some error on the job execution."),
    ):
        workflow = Workflow.model_validate(
            {
                "name": "tmp-wf-exec-raise",
                "jobs": {
                    "first-job": {
                        "stages": [
                            {"name": "Some Stage 1", "echo": "Start stage 1."}
                        ]
                    },
                    "second-job": {
                        "stages": [
                            {"name": "Some Stage 2", "echo": "Start stage 2."}
                        ]
                    },
                },
            }
        )
        rs = workflow.execute({}, max_job_parallel=1)
        assert rs.status == FAILED


def test_workflow_exec_raise_job_trigger(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_exec_raise_job_trigger.yml",
        data="""
        tmp-wf-exec-raise-job-trigger:
          type: Workflow
          params:
            name:
              desc: "A name parameter of this workflow."
              type: str
          jobs:
            final-job:
              needs: [ "start-job" ]
              stages:
                - name: "Call after above stage raise"
                  id: check
                  echo: "Hello after Raise Error"
            start-job:
              stages:
                - name: "Get param that not set"
                  id: get-param
                  echo: "Passing name ${{ params.name }}"

        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-exec-raise-job-trigger")
        rs: Result = workflow.execute(
            params={"stream": "demo-stream"}, max_job_parallel=1
        )
        assert rs.status == FAILED
        assert rs.context == {
            "status": FAILED,
            "errors": {
                "name": "WorkflowError",
                "message": "Validate job trigger rule was failed with 'all_success'.",
            },
            "params": {"stream": "demo-stream"},
            "jobs": {
                "start-job": {
                    "status": FAILED,
                    "stages": {
                        "get-param": {
                            "outputs": {},
                            "errors": {
                                "name": "UtilError",
                                "message": "Parameters does not get dot with caller: 'params.name'.",
                            },
                            "status": FAILED,
                        }
                    },
                    "errors": {
                        "name": "JobError",
                        "message": "Strategy execution was break because its nested-stage, 'get-param', failed.",
                    },
                }
            },
        }
