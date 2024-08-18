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
    assert rs != rs2


def test_result_context():
    data = {
        "params": {
            "source": "src",
            "target": "tgt",
        }
    }
    rs = Result(context=data)
    rs.context.update({"additional-key": "new-value-to-add"})
    assert {
        "params": {"source": "src", "target": "tgt"},
        "additional-key": "new-value-to-add",
    } == rs.context
