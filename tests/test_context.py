from ddeutil.workflow.context import (
    JobContext,
    MatrixStageContext,
    OutputContext,
    StageContext,
    StrategyMatrixContext,
)
from pydantic import TypeAdapter


def test_context_output():
    context = OutputContext()
    assert context.errors is None
    assert not context.is_exception()


def test_context_output_errors():
    context = OutputContext(
        errors={
            "class": TypeError("str type"),
            "name": "TypeError",
            "message": "str type",
        }
    )
    assert context.is_exception()
    assert context.errors.message == "str type"


def test_context_stage():
    context = StageContext(stages={"stage-id": {}})
    assert context.errors is None
    assert not context.is_exception()


def test_strategies_context():
    context = TypeAdapter(MatrixStageContext).validate_python(
        {
            "2150810470": {
                "matrix": {"sleep": "1"},
                "stages": {"success": {"outputs": {"result": "fast-success"}}},
            },
            "4855178605": {
                "matrix": {"sleep": "5"},
                "stages": {"success": {"outputs": {"result": "fast-success"}}},
            },
            "9873503202": {
                "matrix": {"sleep": "0.1"},
                "stages": {"success": {"outputs": {"result": "success"}}},
            },
        }
    )
    assert len(context) == 3
    assert context["2150810470"].matrix == {"sleep": "1"}


def test_job_context():
    TypeAdapter(StrategyMatrixContext).validate_python(
        {
            "2150810470": {
                "matrix": {"sleep": "1"},
                "stages": {"success": {"outputs": {"result": "fast-success"}}},
            },
            "4855178605": {
                "matrix": {"sleep": "5"},
                "stages": {"success": {"outputs": {"result": "fast-success"}}},
            },
            "9873503202": {
                "matrix": {"sleep": "0.1"},
                "stages": {"success": {"outputs": {"result": "success"}}},
            },
        }
    )

    context = TypeAdapter(StrategyMatrixContext).validate_python(
        {
            "strategies": {
                "9873503202": {
                    "matrix": {"sleep": "0.1"},
                    "stages": {
                        "success": {"outputs": {"result": "success"}},
                    },
                },
                "4855178605": {
                    "matrix": {"sleep": "5"},
                    "stages": {
                        "success": {"outputs": {"result": "fast-success"}},
                    },
                },
                "2150810470": {
                    "matrix": {"sleep": "1"},
                    "stages": {
                        "success": {"outputs": {"result": "fast-success"}},
                    },
                },
            },
        }
    )
    print(context.strategies)
    assert not context.is_exception()


def test_context_workflow():
    context = JobContext.model_validate(
        {
            "params": {},
            "jobs": {
                "job-complete-not-parallel": {
                    "strategies": {
                        "9873503202": {
                            "matrix": {"sleep": "0.1"},
                            "stages": {
                                "success": {"outputs": {"result": "success"}},
                            },
                        },
                        "4855178605": {
                            "matrix": {"sleep": "5"},
                            "stages": {
                                "success": {
                                    "outputs": {"result": "fast-success"}
                                },
                            },
                        },
                        "2150810470": {
                            "matrix": {"sleep": "1"},
                            "stages": {
                                "success": {
                                    "outputs": {"result": "fast-success"}
                                },
                            },
                        },
                    },
                },
            },
        }
    )
    print(context)
