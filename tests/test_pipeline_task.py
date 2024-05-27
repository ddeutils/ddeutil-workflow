import ddeutil.workflow.pipeline as pipe


def test_pipe_stage_task(params_simple):
    pipeline = pipe.Pipeline.from_loader(
        name="ingest_csv_to_parquet",
        externals={},
    )
    stage = pipeline.job("extract-load").stage("extract-load")
    rs = stage.execute(
        params={
            "params": {
                "run-date": "",
                "source": "ds_csv_local_file",
                "sink": "ds_parquet_local_file_dir",
            },
        }
    )
    assert {"output": {"records": 2}} == rs
