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

    for s in make(
        matrix={
            "table": ["customer", "sales"],
            "system": ["csv"],
            "partition": [1, 2, 3],
        },
        exclude=[],
        include=[],
    ):
        print("".join(map(str, s.values())))


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
