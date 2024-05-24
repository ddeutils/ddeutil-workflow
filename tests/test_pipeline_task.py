import ddeutil.workflow.pipeline as pipe


def test_pipe_stage_task(params_simple):
    pipeline = pipe.Pipeline.from_loader(
        name="ingest_local_to_local",
        params=params_simple,
        externals={},
    )

    stage = pipeline.job("extract-load").stage("extract-load")
    print(stage)
    stage.execute(params={})
