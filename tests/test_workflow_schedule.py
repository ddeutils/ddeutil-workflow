from ddeutil.workflow.scheduler import WorkflowSchedule


def test_workflow_schedule():
    wf_schedule = WorkflowSchedule(name="demo workflow")

    assert wf_schedule.name == "demo_workflow"
    assert wf_schedule.alias == "demo_workflow"

    wf_schedule = WorkflowSchedule(name="demo", alias="example")

    assert wf_schedule.name == "demo"
    assert wf_schedule.alias == "example"
