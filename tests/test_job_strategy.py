import pytest
from ddeutil.workflow import Job, Strategy, Workflow
from ddeutil.workflow.job import make


def test_make():
    assert make(
        matrix={
            "table": ["customer", "sales"],
            "system": ["csv"],
            "partition": [1, 2, 3],
        },
        exclude=[],
        include=[],
    ) == [
        {"table": "customer", "system": "csv", "partition": 1},
        {"table": "customer", "system": "csv", "partition": 2},
        {"table": "customer", "system": "csv", "partition": 3},
        {"table": "sales", "system": "csv", "partition": 1},
        {"table": "sales", "system": "csv", "partition": 2},
        {"table": "sales", "system": "csv", "partition": 3},
    ]

    assert make(
        matrix={"table": ["customer"], "system": ["csv"], "partition": [1]},
        exclude=[{"table": "customer", "system": "csv", "partition": 1}],
        include=[],
    ) == [{}]

    with pytest.raises(ValueError):
        make(
            matrix={"table": ["customer"], "system": ["csv"], "partition": [1]},
            exclude=[],
            include=[{"table": "sales", "foo": "bar", "index": 1, "name": "a"}],
        )

    assert make(
        matrix={"table": ["customer"], "system": ["csv"], "partition": [1]},
        exclude=[],
        include=[{"table": "customer", "system": "csv", "partition": 1}],
    ) == [{"table": "customer", "system": "csv", "partition": 1}]


def test_strategy():
    strategy = Strategy.model_validate(
        {
            "matrix": {
                "table": ["customer", "sales"],
                "system": ["csv"],
                "partition": [1, 2, 3],
            },
        }
    )
    assert strategy.is_set()
    assert [
        {"table": "customer", "system": "csv", "partition": 1},
        {"table": "customer", "system": "csv", "partition": 2},
        {"table": "customer", "system": "csv", "partition": 3},
        {"table": "sales", "system": "csv", "partition": 1},
        {"table": "sales", "system": "csv", "partition": 2},
        {"table": "sales", "system": "csv", "partition": 3},
    ] == strategy.make()

    strategy = Strategy.model_validate(
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


def test_strategy_from_job():
    workflow: Workflow = Workflow.from_loader(
        name="wf-run-matrix", externals={}
    )
    job: Job = workflow.job("multiple-system")
    strategy = job.strategy
    assert [
        {"table": "customer", "system": "csv", "partition": 2},
        {"table": "customer", "system": "csv", "partition": 3},
        {"table": "sales", "system": "csv", "partition": 1},
        {"table": "sales", "system": "csv", "partition": 2},
        {"table": "customer", "system": "csv", "partition": 4},
    ] == strategy.make()
