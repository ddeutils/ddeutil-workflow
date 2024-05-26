import ddeutil.workflow.pipeline as pipe


def test_pipe_stage_task(params_simple):
    pipeline = pipe.Pipeline.from_loader(
        name="ingest_csv_to_parquet",
        params=params_simple,
        externals={},
    )
    stage = pipeline.job("extract-load").stage("extract-load")
    rs = stage.execute(params={})
    assert {"output": {"records": 2}} == rs
