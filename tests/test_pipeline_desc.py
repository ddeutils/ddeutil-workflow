import ddeutil.workflow.pipeline as pipe


def test_pipe_desc():
    pipeline = pipe.Pipeline.from_loader(
        name="run_python",
        externals={},
    )
    assert pipeline.desc == (
        "## Run Python Workflow\n\nThis is a running python workflow\n"
    )
