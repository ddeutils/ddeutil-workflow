import pytest
from ddeutil.workflow.exceptions import UtilException
from ddeutil.workflow.utils import param2template


def test_param2template():
    value = param2template(
        {
            "str": "${{ params.src }}",
            "int": "${{ params.value }}",
            "int_but_str": "value is ${{ params.value | abs}}",
            "list": ["${{ params.src }}", "${{ params.value }}"],
        },
        params={
            "params": {
                "src": "foo",
                "value": -10,
            },
        },
    )
    assert {
        "str": "foo",
        "int": -10,
        "int_but_str": "value is 10",
        "list": ["foo", -10],
    } == value

    with pytest.raises(UtilException):
        param2template("${{ params.foo }}", {"params": {"value": -5}})


def test_param2template_with_filter():
    value = param2template(
        "${{ params.value | abs }}", {"params": {"value": -5}}
    )
    assert 5 == value

    with pytest.raises(UtilException):
        param2template("${{ params.value | abs12 }}", {"params": {"value": -5}})
