from unittest import mock

from ddeutil.workflow import Workflow
from ddeutil.workflow.conf import Config
from ddeutil.workflow.utils import Result


def test_workflow_exec_needs():
    workflow = Workflow.from_loader(name="wf-run-depends", externals={})
    rs: Result = workflow.execute(params={"name": "bar"})
    assert {
        "params": {"name": "bar"},
        "jobs": {
            "final-job": {
                "matrix": {},
                "stages": {
                    "8797330324": {
                        "outputs": {},
                    },
                },
            },
            "first-job": {
                "matrix": {},
                "stages": {
                    "7824513474": {
                        "outputs": {},
                    },
                },
            },
            "second-job": {
                "matrix": {},
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
                    "matrix": {},
                    "stages": {
                        "8797330324": {
                            "outputs": {},
                        },
                    },
                },
                "first-job": {
                    "matrix": {},
                    "stages": {
                        "7824513474": {
                            "outputs": {},
                        },
                    },
                },
                "second-job": {
                    "matrix": {},
                    "stages": {
                        "1772094681": {
                            "outputs": {},
                        },
                    },
                },
            },
        } == rs.context
