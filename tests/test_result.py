import time

import pytest
from ddeutil.workflow.errors import ResultError
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
    assert Status.SUCCESS.emoji == "✅"


def test_result_default():
    rs = Result()
    time.sleep(0.025)
    rs2 = Result()
    assert rs.status == Status.WAIT
    assert rs.context == {"status": Status.WAIT}
    assert rs2.status == Status.WAIT
    assert rs2.context == {"status": Status.WAIT}

    # NOTE: Result objects should not equal because they do not have the same
    #   running ID value.
    assert rs != rs2
    assert rs.run_id != rs2.run_id

    assert rs.alive_time() > 0


def test_result_construct_with_rs_or_id():
    rs = Result.construct_with_rs_or_id(run_id="foo", extras={"test": "value"})
    assert rs.run_id == "foo"
    assert rs.parent_run_id is None
    assert rs.extras == {"test": "value"}

    rs = Result.construct_with_rs_or_id(
        run_id="foo",
        parent_run_id="baz",
        result=Result(run_id="bar"),
    )

    assert rs.run_id != "foo"
    assert rs.run_id == "bar"
    assert rs.parent_run_id == "baz"


def test_result_context():
    rs: Result = Result(context={"params": {"source": "src", "target": "tgt"}})
    rs.context.update({"additional-key": "new-value-to-add"})
    assert rs.status == Status.WAIT
    assert rs.context == {
        "params": {"source": "src", "target": "tgt"},
        "additional-key": "new-value-to-add",
    }


def test_result_catch():
    rs: Result = Result()
    data = {"params": {"source": "src", "target": "tgt"}}
    rs.catch(status=0, context=data)
    assert rs.status == SUCCESS
    assert rs.context == data | {"status": SUCCESS}

    rs.catch(status=FAILED, context={"params": {"new_value": "foo"}})
    assert rs.status == FAILED
    assert rs.context == {
        "params": {"new_value": "foo"},
        "status": Status.FAILED,
    }

    rs.catch(status=WAIT, params={"new_value": "bar"})
    assert rs.status == WAIT
    assert rs.context == {"params": {"new_value": "bar"}, "status": Status.WAIT}

    # NOTE: Raise because kwargs get the key that does not exist on the context.
    with pytest.raises(ResultError):
        rs.catch(status=SUCCESS, not_exists={"foo": "bar"})


def test_result_catch_context_does_not_new():

    def change_context(result: Result) -> Result:  # pragma: no cov
        return result.catch(status=SUCCESS, context={"foo": "baz!!"})

    rs: Result = Result(context={"foo": "bar"})
    assert rs.status == WAIT

    change_context(rs)

    assert rs.status == SUCCESS
    assert rs.context == {"foo": "baz!!", "status": Status.SUCCESS}
