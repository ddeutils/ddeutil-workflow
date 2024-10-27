from datetime import datetime

import pytest
from ddeutil.workflow import Workflow
from ddeutil.workflow.exceptions import WorkflowException


def test_workflow_params_py():
    workflow = Workflow.from_loader(name="wf-run-hook")
    rs = workflow.params["run-date"].receive("2024-01-01")
    assert rs == datetime(2024, 1, 1)


def test_workflow_params_required():
    workflow = Workflow.from_loader(name="wf-params-required")

    assert workflow.parameterize({"name": "foo"}) == {
        "params": {"name": "foo"},
        "jobs": {},
    }

    with pytest.raises(WorkflowException):
        workflow.parameterize({"foo": "bar"})
