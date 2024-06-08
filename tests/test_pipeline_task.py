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


def test_pipe_job_task():
    pipeline = pipe.Pipeline.from_loader(
        name="ingest_csv_to_parquet",
        externals={},
    )
    el_job: pipe.Job = pipeline.job("extract-load")
    rs = el_job.execute(
        params={
            "params": {
                "run-date": datetime(2024, 1, 1),
                "source": "ds_csv_local_file",
                "sink": "ds_parquet_local_file_dir",
            },
        },
    )
    assert {
        "matrix": {},
        "params": {
            "run-date": datetime(2024, 1, 1, 0, 0),
            "source": "ds_csv_local_file",
            "sink": "ds_parquet_local_file_dir",
        },
        "stages": {
            "extract-load": {"outputs": {"records": 2}},
        },
    } == rs


def test_pipe_task():
    pipeline = pipe.Pipeline.from_loader(
        name="ingest_csv_to_parquet",
        externals={},
    )
    rs = pipeline.execute(
        params={
            "run-date": datetime(2024, 1, 1),
            "source": "ds_csv_local_file",
            "sink": "ds_parquet_local_file_dir",
        },
    )
    assert {
        "params": {
            "run-date": datetime(2024, 1, 1),
            "source": "ds_csv_local_file",
            "sink": "ds_parquet_local_file_dir",
        },
        "jobs": {
            "extract-load": {
                "stages": {
                    "extract-load": {
                        "outputs": {"records": 2},
                    },
                },
                "matrix": {},
            },
        },
    } == rs
