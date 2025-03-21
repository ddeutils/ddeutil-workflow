import logging
import time

from ddeutil.workflow.result import (
    Result,
    StageContext,
    Status,
    StrategyContext,
)


def test_status():
    assert Status.SUCCESS == Status.__getitem__("SUCCESS")
    assert Status.FAILED == Status(1)


def test_result_default():
    rs = Result()
    time.sleep(1)

    rs2 = Result()

    logging.info(f"Run ID: {rs.run_id}, Parent Run ID: {rs.parent_run_id}")
    logging.info(f"Run ID: {rs2.run_id}, Parent Run ID: {rs2.parent_run_id}")
    assert isinstance(rs.status, Status)
    assert 2 == rs.status
    assert {} == rs.context

    assert 2 == rs2.status
    assert {} == rs2.context

    # NOTE: Result objects should not equal because they do not have the same
    #   running ID value.
    assert rs != rs2


def test_result_context():
    data: dict[str, dict[str, str]] = {
        "params": {
            "source": "src",
            "target": "tgt",
        }
    }
    rs: Result = Result(context=data)
    rs.context.update({"additional-key": "new-value-to-add"})
    assert {
        "params": {"source": "src", "target": "tgt"},
        "additional-key": "new-value-to-add",
    } == rs.context


def test_result_catch():
    rs: Result = Result()
    data = {"params": {"source": "src", "target": "tgt"}}
    rs.catch(status=0, context=data)
    assert rs.status == 0
    assert data == rs.context

    rs.catch(status=1, context={"params": {"new_value": "foo"}})
    assert rs.status == 1
    assert rs.context == {"params": {"new_value": "foo"}}


def test_context_stage():
    stage_context = StageContext()
    assert stage_context.errors is None
    assert not stage_context.is_exception()


def test_context_stage_errors():
    stage_context = StageContext(
        errors={
            "class": TypeError("str type"),
            "name": "TypeError",
            "message": "str type",
        }
    )
    assert stage_context.is_exception()
    assert stage_context.errors.message == "str type"


def test_context_strategy():
    strategy_context = StrategyContext(stages={"stage-id": {}})
    assert strategy_context.errors is None
    assert not strategy_context.is_exception()
