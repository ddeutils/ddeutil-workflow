import logging
import time

import pytest
from ddeutil.workflow.exceptions import ResultException
from ddeutil.workflow.result import (
    FAILED,
    SUCCESS,
    WAIT,
    Result,
    Status,
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


def test_result_construct_with_rs_or_id():
    rs = Result.construct_with_rs_or_id(
        run_id="foo",
        extras={"test": "value"},
    )
    assert rs.run_id == "foo"
    assert rs.parent_run_id is None
    assert rs.extras == {"test": "value"}

    rs = Result.construct_with_rs_or_id(
        run_id="foo",
        parent_run_id="baz",
        result=Result(run_id="bar"),
    )

    assert rs.run_id == "bar"
    assert rs.parent_run_id == "baz"


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
    assert rs.status == SUCCESS
    assert data == rs.context

    rs.catch(status=FAILED, context={"params": {"new_value": "foo"}})
    assert rs.status == FAILED
    assert rs.context == {"params": {"new_value": "foo"}}

    rs.catch(status=WAIT, params={"new_value": "bar"})
    assert rs.status == WAIT
    assert rs.context == {"params": {"new_value": "bar"}}

    # NOTE: Raise because kwargs get the key that does not exist on the context.
    with pytest.raises(ResultException):
        rs.catch(status=SUCCESS, not_exists={"foo": "bar"})


def test_result_catch_context_does_not_new():

    def change_context(result: Result) -> Result:  # pragma: no cov
        return result.catch(status=SUCCESS, context={"foo": "baz"})

    rs: Result = Result(context={"foo": "bar"})
    assert rs.status == WAIT

    change_context(rs)

    assert rs.status == SUCCESS
    assert rs.context == {"foo": "baz"}
