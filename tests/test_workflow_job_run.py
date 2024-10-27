import pytest
from ddeutil.workflow import Workflow
from ddeutil.workflow.exceptions import WorkflowException
from ddeutil.workflow.utils import Result


def test_workflow_execute_job():
    workflow = Workflow.from_loader(name="wf-run-python")
    rs: Result = workflow.execute_job(
        job_id="final-job",
        params={
            "author-run": "Local Workflow",
            "run-date": "2024-01-01",
        },
    )
    print(rs.context)


def test_workflow_execute_job_raise():
    workflow = Workflow.from_loader(name="wf-run-python")
    with pytest.raises(WorkflowException):
        workflow.execute_job(
            job_id="not-found-job",
            params={
                "author-run": "Local Workflow",
                "run-date": "2024-01-01",
            },
        )
