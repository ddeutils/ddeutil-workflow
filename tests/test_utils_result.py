from ddeutil.workflow.utils import Result


def test_result_default():
    rs = Result()
    assert 2 == rs.status
    assert {} == rs.context


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
