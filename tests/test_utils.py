import ddeutil.workflow.utils as utils


def test_gen_id():
    assert "1354680202" == utils.gen_id("{}")
    assert "1354680202" == utils.gen_id("{}", sensitive=False)


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


def test_config():
    engine = utils.Engine()
    assert ["ddeutil.workflow"] == engine.registry
    assert ["ddeutil.workflow.utils"] == engine.registry_filter

    engine = utils.Engine.model_validate(
        obj={
            "registry": "ddeutil.workflow",
            "registry_filter": "ddeutil.workflow.utils",
        }
    )
    assert ["ddeutil.workflow"] == engine.registry
    assert ["ddeutil.workflow.utils"] == engine.registry_filter
