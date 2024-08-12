from datetime import datetime

import ddeutil.workflow.pipeline as pipe
import ddeutil.workflow.stage as st


def test_pipe_stage_task():
    pipeline = pipe.Pipeline.from_loader(
        name="ingest_csv_to_parquet",
        externals={},
    )
    stage: st.HookStage = pipeline.job("extract-load").stage("extract-load")
    rs = stage.execute(
        params={
            "params": {
                "run-date": datetime(2024, 1, 1),
                "source": "ds_csv_local_file",
                "sink": "ds_parquet_local_file_dir",
            },
        }
    )
    assert 0 == rs.status
    assert {"records": 1} == rs.context


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
        "99914b932bd37a50b983c5e7c90ae93b": {
            "matrix": {},
            "stages": {"extract-load": {"outputs": {"records": 1}}},
        },
    } == rs.context


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
    assert 0 == rs.status
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
                        "outputs": {"records": 1},
                    },
                },
                "matrix": {},
            },
        },
    } == rs.context
