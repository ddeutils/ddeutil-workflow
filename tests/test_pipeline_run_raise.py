import ddeutil.workflow as pipe


def test_pipeline_run_raise():
    pipeline = pipe.Pipeline.from_loader("pipe-run-python-raise", externals={})
    rs = pipeline.execute(params={})
    print(rs)
    assert 1 == rs.status

    import json

    print(json.dumps(rs.context, indent=2, default=str))
