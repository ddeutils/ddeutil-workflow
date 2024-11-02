from datetime import datetime

import ddeutil.workflow as wf
import ddeutil.workflow.stage as st


def test_workflow_exec_hook_from_stage():
    workflow = wf.Workflow.from_loader(
        name="ingest_csv_to_parquet",
        externals={},
    )
    stage: st.HookStage = workflow.job("extract-load").stage("extract-load")
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


def test_workflow_exec_hook_from_job():
    workflow = wf.Workflow.from_loader(
        name="ingest_csv_to_parquet",
        externals={},
    )
    el_job: wf.Job = workflow.job("extract-load")
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
        "1354680202": {
            "matrix": {},
            "stages": {"extract-load": {"outputs": {"records": 1}}},
        },
    } == rs.context


def test_workflow_exec_hook():
    workflow = wf.Workflow.from_loader(
        name="ingest_csv_to_parquet",
        externals={},
    )
    rs = workflow.execute(
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


def test_workflow_exec_hook_with_prefix():
    workflow = wf.Workflow.from_loader(name="pipe_hook_mssql_proc")
    rs = workflow.execute(
        params={
            "run_date": datetime(2024, 1, 1),
            "sp_name": "proc-name",
            "source_name": "src",
            "target_name": "tgt",
        },
    )
    print(rs)
