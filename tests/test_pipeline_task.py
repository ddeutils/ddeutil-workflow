from datetime import datetime

import ddeutil.workflow.pipeline as pipe


def test_pipe_stage_task():
    pipeline = pipe.Pipeline.from_loader(
        name="ingest_csv_to_parquet",
        externals={},
    )
    stage = pipeline.job("extract-load").stage("extract-load")
    rs = stage.execute(
        params={
            "params": {
                "run-date": datetime(2024, 1, 1),
                "source": "ds_csv_local_file",
                "sink": "ds_parquet_local_file_dir",
            },
        }
    )
    assert {"extract-load": {"outputs": {"records": 2}}} == rs["stages"]
