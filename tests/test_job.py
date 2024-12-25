from unittest import mock

import pytest
from ddeutil.workflow import Config
from ddeutil.workflow.exceptions import JobException
from ddeutil.workflow.job import Job, TriggerRules
from pydantic import ValidationError


def test_job():
    job = Job()
    assert "all_success" == job.trigger_rule
    assert TriggerRules.all_success == job.trigger_rule

    job = Job(desc="\t# Desc\n\tThis is a demo job.")
    assert job.desc == "# Desc\nThis is a demo job."

    job = Job(id="final-job", needs=["job-before"])
    assert job.id == "final-job"

    # NOTE: Validate the `check_needs` method
    assert job.check_needs({"job-before": "foo"})
    assert not job.check_needs({"job-after": "foo"})


def test_job_raise():

    # NOTE: Raise if passing template to the job ID.
    with pytest.raises(ValidationError):
        Job(id="${{ some-template }}")

    with pytest.raises(ValidationError):
        Job(id="This is ${{ some-template }}")

    # NOTE: Raise if it has some stage ID was duplicated in the same job.
    with pytest.raises(ValidationError):
        Job.model_validate(
            {
                "stages": [
                    {"name": "Empty Stage", "echo": "hello world"},
                    {"name": "Empty Stage", "echo": "hello foo"},
                ]
            }
        )

    # NOTE: Raise if getting not existing stage ID from a job.
    with pytest.raises(ValueError):
        Job(
            stages=[
                {"id": "stage01", "name": "Empty Stage", "echo": "hello world"},
                {"id": "stage02", "name": "Empty Stage", "echo": "hello foo"},
            ]
        ).stage("some-stage-id")


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
