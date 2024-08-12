import ddeutil.workflow.pipeline as pipe


def test_pipe_strategy_model():
    strategy = pipe.Strategy.model_validate(
        obj={
            "matrix": {
                "table": ["customer", "sales"],
                "system": ["csv"],
                "partition": [1, 2, 3],
            },
            "exclude": [
                {
                    "table": "customer",
                    "system": "csv",
                    "partition": 1,
                },
                {
                    "table": "sales",
                    "partition": 3,
                },
            ],
            "include": [
                {
                    "table": "customer",
                    "system": "csv",
                    "partition": 4,
                }
            ],
        }
    )
    assert sorted(
        [
            {"partition": 1, "system": "csv", "table": "sales"},
            {"partition": 2, "system": "csv", "table": "customer"},
            {"partition": 2, "system": "csv", "table": "sales"},
            {"partition": 3, "system": "csv", "table": "customer"},
            {"partition": 4, "system": "csv", "table": "customer"},
        ],
        key=lambda x: (x["partition"], x["table"]),
    ) == sorted(
        strategy.make(),
        key=lambda x: (x["partition"], x["table"]),
    )


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
    assert sorted(
        [
            {"partition": 1, "system": "csv", "table": "sales"},
            {"partition": 2, "system": "csv", "table": "customer"},
            {"partition": 2, "system": "csv", "table": "sales"},
            {"partition": 3, "system": "csv", "table": "customer"},
            {"partition": 4, "system": "csv", "table": "customer"},
        ],
        key=lambda x: (x["partition"], x["table"]),
    ) == sorted(
        multi_sys.strategy.make(),
        key=lambda x: (x["partition"], x["table"]),
    )


def test_pipe_matrix():
    pipeline = pipe.Pipeline.from_loader(
        name="ingest_multiple_system",
        externals={},
    )
    rs = pipeline.execute(params={"source": "src", "target": "tgt"})
    print(rs)
    import json

    print(json.dumps(rs, indent=4))
