import pytest
from ddeutil.workflow.scheduler import WorkflowSchedule
from pydantic import ValidationError


def test_workflow_schedule():
    wf_schedule = WorkflowSchedule(name="demo workflow")

    assert wf_schedule.name == "demo_workflow"
    assert wf_schedule.alias == "demo_workflow"

    wf_schedule = WorkflowSchedule(name="demo", alias="example", on=[])

    assert wf_schedule.name == "demo"
    assert wf_schedule.alias == "example"

    wf_schedule = WorkflowSchedule(name="demo", on=[{"cronjob": "2 * * * *"}])
    assert len(wf_schedule.on) == 1

    # NOTE: Raise if do not pass any data to WorkflowSchedule
    with pytest.raises(ValidationError):
        WorkflowSchedule.model_validate({})


def test_workflow_schedule_raise_on(test_path):
    # NOTE: Raise if values on the on field reach the maximum value.
    with pytest.raises(ValidationError):
        WorkflowSchedule(
            name="tmp-wf-on-reach-max-value",
            on=[
                {"cronjob": "2 * * * *"},
                {"cronjob": "3 * * * *"},
                {"cronjob": "4 * * * *"},
                {"cronjob": "5 * * * *"},
                {"cronjob": "6 * * * *"},
                {"cronjob": "7 * * * *"},
            ],
        )

    # NOTE: Raise if values on has duplicate values.
    with pytest.raises(ValidationError):
        WorkflowSchedule(
            name="tmp-wf-on-duplicate",
            on=[
                {"cronjob": "2 * * * *"},
                {"cronjob": "2 * * * *"},
            ],
        )

    # NOTE: Raise if values on has not valid type.
    with pytest.raises(TypeError):
        WorkflowSchedule(
            name="tmp-wf-on-type-not-valid",
            on=[
                [{"cronjob": "2 * * * *"}],
                20240101,
            ],
        )
