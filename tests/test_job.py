import pytest
from ddeutil.workflow.errors import JobError
from ddeutil.workflow.job import (
    Job,
    OnDocker,
    OnLocal,
    OnSelfHosted,
    Rule,
    RunsOnModel,
)
from ddeutil.workflow.result import CANCEL, FAILED, SKIP, SUCCESS, WAIT
from pydantic import TypeAdapter, ValidationError


def test_run_ons():
    model = TypeAdapter(RunsOnModel).validate_python(
        {
            "type": "self_hosted",
            "with": {"host": "localhost:88", "token": "dummy"},
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
    assert job.id is None
    assert job.trigger_rule == "all_success"
    assert job.trigger_rule == Rule.ALL_SUCCESS

    job = Job(desc="\n\t# Desc\n\tThis is a demo job.")
    assert job.desc == "# Desc\nThis is a demo job."

    job = Job.model_validate({"runs-on": {"type": "docker"}})
    assert isinstance(job.runs_on, OnDocker)


def test_job_check_needs():
    job = Job(id="final-job", needs=["job-before"])
    assert job.id == "final-job"

    # NOTE: Validate the `check_needs` method
    assert job.check_needs({"job-before": {"stages": "foo"}}) == SUCCESS
    assert job.check_needs({"job-before": {}}) == SUCCESS
    assert job.check_needs({"job-after": {"stages": "foo"}}) == WAIT
    assert (
        job.check_needs({"job-before": {"status": FAILED, "errors": {}}})
        == FAILED
    )
    assert job.check_needs({"job-before": {"status": SKIP}}) == SKIP
    assert job.check_needs({"job-before": {"status": SUCCESS}}) == SUCCESS

    job = Job(id="final-job", needs=["job-before1", "job-before2"])
    assert job.check_needs({"job-before1": {}, "job-before2": {}}) == SUCCESS
    assert job.check_needs({"job-before1": {"stages": "foo"}}) == WAIT
    # assert job.check_needs({"job-before1": {"errors": {}}}) == FAILED
    assert (
        job.check_needs({"job-before1": {"status": CANCEL}, "job-before2": {}})
        == CANCEL
    )

    job = Job.model_validate(
        {
            "id": "final-job",
            "needs": ["job-before1", "job-before2"],
            "trigger-rule": Rule.ALL_DONE,
        }
    )
    assert (
        job.check_needs(
            {"job-before1": {}, "job-before2": {"status": FAILED, "errors": {}}}
        )
        == SUCCESS
    )

    job = Job.model_validate(
        {
            "id": "final-job",
            "needs": ["job-before1", "job-before2"],
            "trigger-rule": Rule.ALL_FAILED,
        }
    )
    assert (
        job.check_needs(
            {"job-before1": {}, "job-before2": {"status": FAILED, "errors": {}}}
        )
        == FAILED
    )
    assert (
        job.check_needs(
            {
                "job-before1": {"status": FAILED},
                "job-before2": {"status": FAILED, "errors": {}},
            }
        )
        == SUCCESS
    )

    job = Job.model_validate(
        {
            "id": "final-job",
            "needs": ["job-before1", "job-before2", "job-before3"],
            "trigger-rule": Rule.ONE_SUCCESS,
        }
    )
    assert (
        job.check_needs(
            {
                "job-before1": {},
                "job-before2": {"status": FAILED},
                "job-before3": {"status": SKIP},
            }
        )
        == SUCCESS
    )
    assert (
        job.check_needs(
            {
                "job-before1": {},
                "job-before2": {},
                "job-before3": {"status": FAILED},
            }
        )
        == FAILED
    )
    assert (
        job.check_needs(
            {
                "job-before1": {"status": FAILED},
                "job-before2": {"status": SKIP},
                "job-before3": {"status": FAILED},
            }
        )
        == FAILED
    )

    job = Job.model_validate(
        {
            "id": "final-job",
            "needs": ["job-before1", "job-before2", "job-before3"],
            "trigger-rule": Rule.ONE_FAILED,
        }
    )
    assert (
        job.check_needs(
            {
                "job-before1": {},
                "job-before2": {"status": FAILED},
                "job-before3": {"status": FAILED},
            }
        )
        == FAILED
    )
    assert (
        job.check_needs(
            {
                "job-before1": {},
                "job-before2": {"status": SKIP},
                "job-before3": {"status": FAILED},
            }
        )
        == SUCCESS
    )
    assert (
        job.check_needs(
            {
                "job-before1": {"status": FAILED},
                "job-before2": {"status": FAILED},
                "job-before3": {"status": FAILED},
            }
        )
        == FAILED
    )

    job = Job.model_validate(
        {
            "id": "final-job",
            "needs": ["job-before1", "job-before2", "job-before3"],
            "trigger-rule": Rule.NONE_SKIPPED,
        }
    )
    assert (
        job.check_needs(
            {
                "job-before1": {},
                "job-before2": {"status": FAILED},
                "job-before3": {"status": FAILED},
            }
        )
        == SUCCESS
    )
    assert (
        job.check_needs(
            {
                "job-before1": {},
                "job-before2": {"status": SKIP},
                "job-before3": {"status": FAILED},
            }
        )
        == FAILED
    )
    assert (
        job.check_needs(
            {
                "job-before1": {"status": FAILED},
                "job-before2": {"status": FAILED},
                "job-before3": {"status": FAILED},
            }
        )
        == SUCCESS
    )

    job = Job.model_validate(
        {
            "id": "final-job",
            "needs": ["job-before1", "job-before2", "job-before3"],
            "trigger-rule": Rule.NONE_FAILED,
        }
    )
    assert (
        job.check_needs(
            {
                "job-before1": {},
                "job-before2": {"status": SKIP},
                "job-before3": {"status": SKIP},
            }
        )
        == SUCCESS
    )
    assert (
        job.check_needs(
            {
                "job-before1": {},
                "job-before2": {"status": SKIP},
                "job-before3": {"status": FAILED},
            }
        )
        == FAILED
    )
    assert (
        job.check_needs(
            {"job-before1": {}, "job-before2": {}, "job-before3": {}}
        )
        == SUCCESS
    )


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
    job = Job(id="final-job")
    assert job.set_outputs({}, {}) == {"jobs": {"final-job": {}}}
    assert job.set_outputs({}, {"jobs": {}}) == {"jobs": {"final-job": {}}}
    assert job.set_outputs({"status": SKIP}, {"jobs": {}}) == {
        "jobs": {"final-job": {"status": SKIP}}
    }
    assert job.set_outputs({"errors": {}}, {"jobs": {}}) == {
        "jobs": {"final-job": {"errors": {}}}
    }

    # NOTE: Raise because job ID does not set.
    with pytest.raises(JobError):
        Job().set_outputs({}, {})

    assert Job().set_outputs({}, {"jobs": {}}, job_id="1") == {
        "jobs": {"1": {}}
    }

    assert (
        Job(strategy={"matrix": {"table": ["customer"]}}).set_outputs(
            {"status": FAILED}, {"jobs": {}}, job_id="foo"
        )
    ) == {"jobs": {"foo": {"status": FAILED, "strategies": {}}}}


def test_job_get_outputs():
    out = Job(strategy={"matrix": {"table": ["customer"]}}).get_outputs(
        {"jobs": {"foo": {"strategies": {"status": FAILED}}}}, job_id="foo"
    )
    assert out == {"status": FAILED}

    job = Job(id="final-job")
    out = job.get_outputs({"jobs": {"final-job": {"foo": "bar"}}})
    assert out == {"foo": "bar"}

    out = job.get_outputs({"jobs": {"first-job": {"foo": "bar"}}})
    assert out == {}


def test_job_if_condition():
    job = Job.model_validate({"if": '"${{ params.name }}" == "foo"'})
    assert not job.is_skipped(params={"params": {"name": "foo"}})
    assert job.is_skipped(params={"params": {"name": "bar"}})

    job = Job.model_validate({"if": '"${{ params.name }}"'})

    # NOTE: Raise because return type of condition does not match with boolean.
    with pytest.raises(JobError):
        job.is_skipped({"params": {"name": "foo"}})
