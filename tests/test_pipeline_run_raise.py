import ddeutil.workflow as wf


def test_pipeline_run_raise():
    workflow = wf.Workflow.from_loader("wf-run-python-raise", externals={})
    rs = workflow.execute(params={})
    print(rs)
    assert 1 == rs.status

    import json

    print(json.dumps(rs.context, indent=2, default=str))
