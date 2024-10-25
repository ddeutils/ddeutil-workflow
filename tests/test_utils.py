from unittest.mock import patch

import ddeutil.workflow.utils as utils
import pytest


def test_gen_id():
    assert "1354680202" == utils.gen_id("{}")
    assert "1354680202" == utils.gen_id("{}", sensitive=False)

    with patch("ddeutil.workflow.utils.config.workflow_id_simple_mode", False):
        assert "99914b932bd37a50b983c5e7c90ae93b" == utils.gen_id("{}")


def test_filter_func():
    _locals = locals()
    exec("def echo():\n\tprint('Hello World')", globals(), _locals)
    _extract_func = _locals["echo"]
    raw_rs = {
        "echo": _extract_func,
        "list": ["1", 2, _extract_func],
        "dict": {
            "foo": open,
            "echo": _extract_func,
        },
    }
    rs = utils.filter_func(raw_rs)
    assert {
        "echo": "echo",
        "list": ["1", 2, "echo"],
        "dict": {"foo": open, "echo": "echo"},
    } == rs


def test_batch():
    with pytest.raises(ValueError):
        next(utils.batch(range(10), n=-1))

    assert [[0, 1], [2, 3], [4, 5], [6, 7], [8, 9]] == [
        list(i) for i in utils.batch(range(10), n=2)
    ]
