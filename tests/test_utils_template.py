from datetime import datetime

import pytest
from ddeutil.workflow.exceptions import UtilException
from ddeutil.workflow.utils import (
    get_args_const,
    has_template,
    make_filter_registry,
    not_in_template,
    param2template,
)


def test_param2template():
    value = param2template(
        {
            "str": "${{ params.src }}",
            "int": "${{ params.value }}",
            "int_but_str": "value is ${{ params.value | abs}}",
            "list": ["${{ params.src }}", "${{ params.value }}"],
            "str_env": (
                "${{ params.src }}-${WORKFLOW_CORE_TIMEZONE:-}"
                "${WORKFLOW_DUMMY:-}"
            ),
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
        "str_env": "foo-Asia/Bangkok-",
    } == value

    with pytest.raises(UtilException):
        param2template("${{ params.foo }}", {"params": {"value": -5}})


def test_param2template_with_filter():
    value: int = param2template(
        "${{ params.value | abs }}", {"params": {"value": -5}}
    )
    assert 5 == value

    with pytest.raises(UtilException):
        param2template("${{ params.value | abs12 }}", {"params": {"value": -5}})

    value: str = param2template(
        "${{ params.asat-dt | fmt(fmt='%Y%m%d') }}",
        {"params": {"asat-dt": datetime(2024, 8, 1)}},
    )
    assert "20240801" == value

    with pytest.raises(UtilException):
        param2template(
            "${{ params.asat-dt | fmt(fmt='%Y%m%d) }}",
            {"params": {"asat-dt": datetime(2024, 8, 1)}},
        )


def test_make_filter_registry():
    print(make_filter_registry())


def test_get_args_const():
    func, args, kwargs = get_args_const("fmt('test', fmt='%Y%m%d', _max=2)")
    print(func, args, kwargs)


def test_matrix_not_in_template():
    value = {
        "params": {
            "test": "${{ matrix.value.test }}",
        },
        "test": [1, False, "${{ matrix.foo }}"],
    }
    assert not not_in_template(value)

    value = {
        "params": {
            "test": "${{ params.value.test }}",
        },
        "test": [1, False, "${{ matrix.foo }}"],
    }
    assert not_in_template(value)

    value = {
        "params": {
            "test": "${{ matrix.value.test }}",
        },
        "test": [1, False, "${{ stages.foo.matrix }}"],
    }
    assert not_in_template(value)


def test_has_template():
    value = {
        "params": {
            "test": "${{ matrix.value.test }}",
        },
        "test": [1, False, "${{ matrix.foo }}"],
    }
    assert has_template(value)

    value = {
        "params": {
            "test": "${{ params.value.test }}",
        },
        "test": [1, False, "${{ matrix.foo }}"],
    }
    assert has_template(value)

    value = {
        "params": {
            "test": "${ matrix.value.test }",
        },
        "test": [1, False, "{{ stages.foo.matrix }}"],
    }
    assert not has_template(value)