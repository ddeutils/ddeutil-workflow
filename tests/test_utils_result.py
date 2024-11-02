import logging
import time

from ddeutil.workflow.utils import Result


def test_result_default():
    rs = Result()
    time.sleep(1)

    rs2 = Result()

    logging.info(f"Run ID: {rs.run_id}, Parent Run ID: {rs.parent_run_id}")
    logging.info(f"Run ID: {rs2.run_id}, Parent Run ID: {rs2.parent_run_id}")
    assert 2 == rs.status
    assert {} == rs.context
    assert rs == rs2


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


def test_result_receive():
    data = {
        "params": {
            "source": "src",
            "target": "tgt",
        }
    }
    rs: Result = Result(status=1, context=data)
    rs_empty: Result = Result()
    rs_empty.receive(rs)
    assert rs_empty.status == 1
    assert rs_empty.run_id == rs.run_id
    assert id(rs_empty) != id(rs)
    assert {
        "params": {"source": "src", "target": "tgt"},
    } == rs_empty.context


def test_result_receive_jobs():
    data = {"params": {"source": "src", "target": "tgt"}}
    rs: Result = Result(status=1, context=data)

    rs_empty: Result = Result()
    rs_empty.receive_jobs(rs)
    assert rs_empty.status == 1
    assert rs_empty.run_id == rs.run_id
    assert id(rs_empty) != id(rs)
    assert {"jobs": data} == rs_empty.context

    rs_empty: Result = Result(context={"jobs": {}})
    rs_empty.receive_jobs(rs)
    assert rs_empty.status == 1
    assert rs_empty.run_id == rs.run_id
    assert id(rs_empty) != id(rs)
    assert {"jobs": data} == rs_empty.context
