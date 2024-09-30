import ddeutil.workflow as wf


def test_workflow_desc():
    workflow = wf.Workflow.from_loader(
        name="wf-run-common",
        externals={},
    )
    assert workflow.desc == (
        "## Run Python Workflow\n\nThis is a running python workflow\n"
    )
