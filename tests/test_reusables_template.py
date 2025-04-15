import os
from datetime import datetime
from typing import Any

import pytest
from ddeutil.workflow.exceptions import UtilException
from ddeutil.workflow.reusables import (
    has_template,
    not_in_template,
    param2template,
    str2template,
)


def test_str2template():
    value = str2template("None", params={})
    assert value is None

    value = str2template("${{ stages?.message }}", params={})
    assert value is None

    os.environ["ENV_VAR"] = "foo"
    value = str2template("${ ENV_VAR }", params={})
    assert value == "null"


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

    value = param2template(
        {
            "in-string": "value is ${{ stages.first-stage.errors?.class }}",
            "key-only": "${{ stages.first-stage.errors?.message }}",
            "key-only-default": "${{ stages.first-stage.errors?.message | coalesce(False) }}",
        },
        params={"stages": {"first-stage": {"outputs": {"result": 100}}}},
    )
    assert value == {
        "in-string": "value is None",
        "key-only": None,
        "key-only-default": False,
    }


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
