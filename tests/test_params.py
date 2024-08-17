from ddeutil.workflow.utils import StrParam


def test_params_str():
    str_params = StrParam.model_validate({"type": "str"})
    rs = str_params.receive("foo")
    assert rs == "foo"

    rs = str_params.receive(None)
    assert rs is None

    rs = str_params.receive(10)
    assert rs == "10"
