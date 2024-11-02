from unittest import mock

import pytest
from ddeutil.workflow import Config, Job
from ddeutil.workflow.exceptions import JobException
from ddeutil.workflow.workflow import Workflow
from pydantic import ValidationError


def test_job():
    job = Job()
    assert "all_success" == job.trigger_rule

    job = Job(desc="\t# Desc\n\tThis is a demo job.")
    assert job.desc == "# Desc\nThis is a demo job."

    job = Job(id="final-job")
    assert job.id == "final-job"


def test_job_stage_id_not_dup():
    with pytest.raises(ValidationError):
        Job.model_validate(
            {
                "stages": [
                    {"name": "Empty Stage", "echo": "hello world"},
                    {"name": "Empty Stage", "echo": "hello foo"},
                ]
            }
        )


def test_job_id_raise():
    with pytest.raises(ValidationError):
        Job(id="${{ some-template }}")

    with pytest.raises(ValidationError):
        Job(id="This is ${{ some-template }}")


def test_job_stage_from_workflow():
    workflow: Workflow = Workflow.from_loader(name="wf-run-common")

    with pytest.raises(ValueError):
        workflow.job("demo-run").stage("some-stage-id")


def test_job_set_outputs():
    assert Job(id="final-job").set_outputs({}, {}) == {
        "jobs": {"final-job": {}}
    }
    assert Job(id="final-job").set_outputs({}, {"jobs": {}}) == {
        "jobs": {"final-job": {}}
    }

    with pytest.raises(JobException):
        Job().set_outputs({}, {})

    with mock.patch.object(Config, "job_default_id", True):
        assert Job().set_outputs({}, {"jobs": {}}) == {"jobs": {"1": {}}}

        assert (
            Job(strategy={"matrix": {"table": ["customer"]}}).set_outputs(
                {}, {"jobs": {}}
            )
        ) == {"jobs": {"1": {"strategies": {}}}}
