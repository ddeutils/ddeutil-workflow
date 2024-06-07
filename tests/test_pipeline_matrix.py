import ddeutil.workflow.pipeline as pipe


def test_pipe_job_matrix():
    pipeline = pipe.Pipeline.from_loader(
        name="ingest_multiple_system",
        externals={},
    )
    multi_sys = pipeline.job(name="multiple-system")
    assert {
        "system": ["csv"],
        "table": ["customer", "sales"],
        "partition": [1, 2, 3],
    } == multi_sys.strategy.matrix
    assert -1 == multi_sys.strategy.max_parallel
    assert [
        {"partition": 4, "system": "csv", "table": "customer"},
    ] == multi_sys.strategy.include
    assert [
        {"table": "customer", "system": "csv", "partition": 1},
        {"table": "sales", "partition": 3},
    ] == multi_sys.strategy.exclude
    assert [
        {"partition": 1, "system": "csv", "table": "sales"},
        {"partition": 2, "system": "csv", "table": "customer"},
        {"partition": 2, "system": "csv", "table": "sales"},
        {"partition": 3, "system": "csv", "table": "customer"},
        {"partition": 4, "system": "csv", "table": "customer"},
    ] == list(multi_sys.make_strategy())
