import ddeutil.workflow.on as on
import ddeutil.workflow.pipeline as pipe


def test_pipe_on():
    pipeline = pipe.Pipeline.from_loader(
        name="pipe-run-common",
        externals={},
    )
    assert pipeline.on == [
        on.On.from_loader(name="every_5_minute_bkk", externals={})
    ]
