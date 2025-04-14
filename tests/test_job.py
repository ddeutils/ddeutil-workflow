import pytest
from ddeutil.workflow.exceptions import JobException
from ddeutil.workflow.job import (
    Job,
    OnDocker,
    OnLocal,
    OnSelfHosted,
    Rule,
    RunsOnModel,
)
from ddeutil.workflow.result import FAILED, SKIP, SUCCESS, WAIT
from pydantic import TypeAdapter, ValidationError


def test_run_ons():
    model = TypeAdapter(RunsOnModel).validate_python(
        {
            "type": "self_hosted",
            "with": {"host": "localhost:88"},
        },
    )
    assert isinstance(model, OnSelfHosted)
    assert model.args.host == "localhost:88"

    model = TypeAdapter(RunsOnModel).validate_python({"type": "docker"})
    assert isinstance(model, OnDocker)

    model = TypeAdapter(RunsOnModel).validate_python({})
    assert isinstance(model, OnLocal)


def test_job():
    job = Job()
    assert "all_success" == job.trigger_rule
    assert Rule.ALL_SUCCESS == job.trigger_rule

    job = Job(desc="\t# Desc\n\tThis is a demo job.")
    assert job.desc == "# Desc\nThis is a demo job."

    job = Job(id="final-job", needs=["job-before"])
    assert job.id == "final-job"

    # NOTE: Validate the `check_needs` method
    assert job.check_needs({"job-before": "foo"}) == SUCCESS
    assert job.check_needs({"job-after": "foo"}) == WAIT

    job = Job.model_validate({"runs-on": {"type": "docker"}})
    assert isinstance(job.runs_on, OnDocker)


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

    # NOTE: Raise because job ID does not set.
    with pytest.raises(JobException):
        Job().set_outputs({}, {}, job_id=None)

    assert Job().set_outputs({}, {"jobs": {}}, job_id="1") == {
        "jobs": {"1": {}}
    }

    assert (
        Job(strategy={"matrix": {"table": ["customer"]}}).set_outputs(
            {}, {"jobs": {}}, job_id="foo"
        )
    ) == {"jobs": {"foo": {"strategies": {}}}}


def test_job_if_condition():
    job = Job.model_validate({"if": '"${{ params.name }}" == "foo"'})
    assert not job.is_skipped(params={"params": {"name": "foo"}})
    assert job.is_skipped(params={"params": {"name": "bar"}})


def test_job_if_condition_raise():
    job = Job.model_validate({"if": '"${{ params.name }}"'})
    with pytest.raises(JobException):
        job.is_skipped({"params": {"name": "foo"}})


def test_job_check_needs():
    job = Job(id="foo", needs=["deps"])
    assert job.check_needs({}) == WAIT
    assert job.check_needs({"deps": {}}) == SUCCESS
    assert job.check_needs({"deps": {"errors": {}}}) == FAILED
    assert job.check_needs({"deps": {"skipped": True}}) == SKIP
