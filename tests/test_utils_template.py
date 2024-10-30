from datetime import datetime
from typing import Any

import pytest
from ddeutil.workflow.exceptions import UtilException
from ddeutil.workflow.utils import (
    has_template,
    not_in_template,
    param2template,
)


def test_param2template():
    value: dict[str, Any] = param2template(
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
        value="${{ params.value | abs }}",
        params={"params": {"value": -5}},
    )
    assert 5 == value

    with pytest.raises(UtilException):
        param2template(
            value="${{ params.value | abs12 }}",
            params={"params": {"value": -5}},
        )

    value: str = param2template(
        value="${{ params.asat-dt | fmt(fmt='%Y%m%d') }}",
        params={"params": {"asat-dt": datetime(2024, 8, 1)}},
    )
    assert "20240801" == value

    with pytest.raises(UtilException):
        param2template(
            value="${{ params.asat-dt | fmt(fmt='%Y%m%d) }}",
            params={
                "params": {"asat-dt": datetime(2024, 8, 1)},
            },
        )


def test_not_in_template():
    assert not not_in_template(
        {
            "params": {"test": "${{ matrix.value.test }}"},
            "test": [1, False, "${{ matrix.foo }}"],
        }
    )

    assert not_in_template(
        {
            "params": {"test": "${{ params.value.test }}"},
            "test": [1, False, "${{ matrix.foo }}"],
        }
    )

    assert not not_in_template(
        {
            "params": {"test": "${{ foo.value.test }}"},
            "test": [1, False, "${{ foo.foo.matrix }}"],
        },
        not_in="foo.",
    )
    assert not_in_template(
        {
            "params": {"test": "${{ foo.value.test }}"},
            "test": [1, False, "${{ stages.foo.matrix }}"],
        },
        not_in="foo.",
    )


def test_has_template():
    assert has_template(
        {
            "params": {"test": "${{ matrix.value.test }}"},
            "test": [1, False, "${{ matrix.foo }}"],
        }
    )

    assert has_template(
        {
            "params": {"test": "${{ params.value.test }}"},
            "test": [1, False, "${{ matrix.foo }}"],
        }
    )

    assert not has_template(
        {
            "params": {"test": "data", "foo": "bar"},
            "test": [1, False, "{{ stages.foo.matrix }}"],
        }
    )
