from ddeutil.workflow.scheduler import WorkflowSchedule


def test_workflow_schedule():
    wf_schedule = WorkflowSchedule(name="demo workflow")
    assert wf_schedule.name == "demo_workflow"
