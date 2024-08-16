import pytest
from ddeutil.workflow.pipeline import Job
from pydantic import ValidationError


def test_job_model():
    job = Job()

    job.run_id = "demo"
    assert "demo" == job.run_id


def test_job_model_id_raise():
    with pytest.raises(ValidationError):
        Job(id="${{ some-template }}")

    with pytest.raises(ValidationError):
        Job(id="This is ${{ some-template }}")
