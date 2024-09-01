import ddeutil.workflow as pipe


def test_pipe_desc():
    pipeline = pipe.Pipeline.from_loader(
        name="pipe-run-common",
        externals={},
    )
    assert pipeline.desc == (
        "## Run Python Workflow\n\nThis is a running python workflow\n"
    )
