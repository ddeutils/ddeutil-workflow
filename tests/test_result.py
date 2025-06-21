import time

import pytest
from ddeutil.workflow.errors import ResultError
from ddeutil.workflow.result import (
    CANCEL,
    FAILED,
    SUCCESS,
    WAIT,
    Result,
    Status,
    catch,
    validate_statuses,
)


def test_status():
    assert Status.SUCCESS == Status("SUCCESS")
    assert Status.SUCCESS.emoji == "✅"
    assert repr(Status.SUCCESS) == "SUCCESS"
    assert str(Status.SUCCESS) == "SUCCESS"

    assert SUCCESS.is_result()
    assert not WAIT.is_result()


def test_result_default():
    rs = Result()
    time.sleep(0.025)
    rs2 = Result()
    assert rs.status == Status.WAIT
    assert rs.context is None
    assert rs2.status == Status.WAIT
    assert rs2.context is None

    # NOTE: Result objects should not equal because they do not have the same
    #   running ID value.
    assert rs != rs2
    assert rs.run_id != rs2.run_id


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
    rs.catch(status=SUCCESS, context=data)
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

    rs.catch(status=SUCCESS, info={"name": "foo"})
    assert rs.info == {"name": "foo"}

    # NOTE: Raise because kwargs get the key that does not exist on the context.
    with pytest.raises(ResultError):
        rs.catch(status=SUCCESS, not_exists={"foo": "bar"})

    rs: Result = Result(parent_run_id="demo")
    assert rs.parent_run_id == "demo"


def test_result_catch_context_does_not_new():

    def change_context(result: Result) -> Result:  # pragma: no cov
        return result.catch(status=SUCCESS, context={"foo": "baz!!"})

    rs: Result = Result(context={"foo": "bar"})
    assert rs.status == WAIT

    change_context(rs)

    assert rs.status == SUCCESS
    assert rs.context == {"foo": "baz!!", "status": Status.SUCCESS}


def test_validate_statuses():
    assert validate_statuses([SUCCESS, SUCCESS]) == SUCCESS
    assert validate_statuses([CANCEL, SUCCESS]) == CANCEL
    assert validate_statuses([CANCEL, SUCCESS, FAILED]) == CANCEL
    assert validate_statuses([FAILED, SUCCESS]) == FAILED
    assert validate_statuses([FAILED, WAIT]) == FAILED
    assert validate_statuses([SUCCESS, WAIT]) == WAIT
    assert validate_statuses([]) == SUCCESS


def test_catch():
    context = {}
    catch(context, status=SUCCESS, updated={"name": "foo"})
    assert context["status"] == SUCCESS
    assert context == {"status": SUCCESS, "name": "foo"}

    context = {}
    catch(context, status=WAIT, info={"start": 1})
    assert context == {"status": WAIT, "info": {"start": 1}}

    context = {"info": {"end": 10}}
    catch(context, status=WAIT, info={"start": 1})
    assert context == {"status": WAIT, "info": {"start": 1, "end": 10}}

    with pytest.raises(ResultError):
        catch({}, status=SUCCESS, foo={"key": "bar"})
