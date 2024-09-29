from datetime import datetime

import ddeutil.workflow as wf
from ddeutil.workflow.utils import Result


def test_pipe_run_py():
    workflow = wf.Workflow.from_loader(
        name="wf-run-python",
        externals={},
    )
    rs: Result = workflow.execute(
        params={
            "author-run": "Local Workflow",
            "run-date": "2024-01-01",
        },
    )
    assert 0 == rs.status
    assert {"final-job", "first-job", "second-job"} == set(
        rs.context["jobs"].keys()
    )
    assert {"printing", "setting-x"} == set(
        rs.context["jobs"]["first-job"]["stages"].keys()
    )
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
                            "stderr": "",
                        }
                    }
                },
            },
        },
    } == rs.context
