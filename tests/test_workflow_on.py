import ddeutil.workflow as wf
import ddeutil.workflow.on as on


def test_workflow_on():
    workflow = wf.Workflow.from_loader(
        name="wf-run-common",
        externals={},
    )
    assert workflow.on == [
        on.On.from_loader(name="every_5_minute_bkk", externals={})
    ]
