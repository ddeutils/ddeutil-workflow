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
    assert 2 == multi_sys.strategy.max_parallel
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
    assert {
        "params": {"source": "src", "target": "tgt"},
        "jobs": {
            "multiple-system": {
                "strategies": {
                    "ee5917b59c2a4f9fd6e6921f9966b400": {
                        "matrix": {
                            "table": "customer",
                            "system": "csv",
                            "partition": 2,
                        },
                        "stages": {
                            "customer-2": {"outputs": {"records": 1}},
                            "end-stage": {"outputs": {"passing_value": 10}},
                        },
                    },
                    "cf30d610117956231786c6ed34df2e96": {
                        "matrix": {
                            "table": "customer",
                            "system": "csv",
                            "partition": 3,
                        },
                        "stages": {
                            "customer-3": {"outputs": {"records": 1}},
                            "end-stage": {"outputs": {"passing_value": 10}},
                        },
                    },
                    "ec753d2915cdc4f82a2329d1ca51bfe8": {
                        "matrix": {
                            "table": "sales",
                            "system": "csv",
                            "partition": 1,
                        },
                        "stages": {
                            "sales-1": {"outputs": {"records": 1}},
                            "end-stage": {"outputs": {"passing_value": 10}},
                        },
                    },
                    "d3a8459afe955fc81fa7a543bd993c58": {
                        "matrix": {
                            "table": "sales",
                            "system": "csv",
                            "partition": 2,
                        },
                        "stages": {
                            "sales-2": {"outputs": {"records": 1}},
                            "end-stage": {"outputs": {"passing_value": 10}},
                        },
                    },
                    "2f3fe68ee7a285a18723f000e65c4f05": {
                        "matrix": {
                            "table": "customer",
                            "system": "csv",
                            "partition": 4,
                        },
                        "stages": {
                            "customer-4": {"outputs": {"records": 1}},
                            "end-stage": {"outputs": {"passing_value": 10}},
                        },
                    },
                },
            },
        },
    } == rs.context


def test_pipe_matrix_fail_fast():
    pipeline = pipe.Pipeline.from_loader(
        name="pipeline_matrix_fail_fast",
        externals={},
    )
    rs = pipeline.execute(params={"source": "src", "target": "tgt"})
    print(rs)
