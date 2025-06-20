import os
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import pytest
from ddeutil.workflow.errors import UtilError
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
    assert value == "foo"


def test_param2template():
    value: dict[str, Any] = param2template(
        {
            "str": "${{ params.src }}",
            "int": "${{ params.value }}",
            "int_but_str": "value is ${{ params.value | abs}}",
            "list": ["${{ params.src }}", "${{ params.value }}"],
            "str_env": (
                "${{ params.src }}-${WORKFLOW_LOG_TIMEZONE:-}"
                "${WORKFLOW_DUMMY:-}"
            ),
            "url": urlparse("file:./conf"),
            "set": {"${{ params.src }}", "${{ params.value }}"},
        },
        params={
            "params": {
                "src": "foo",
                "value": -10,
                "url": urlparse("file:./conf"),
            },
        },
    )
    assert {
        "str": "foo",
        "int": -10,
        "int_but_str": "value is 10",
        "list": ["foo", -10],
        "str_env": "foo-Asia/Bangkok-",
        "url": urlparse("file:./conf"),
        "set": {"foo", -10},
    } == value

    with pytest.raises(UtilError):
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

    assert (
        param2template(
            value="${{ params.start-dt | fmt('%Y%m%d') }}",
            params={"params": {"start-dt": datetime(2024, 6, 12)}},
        )
        == "20240612"
    )

    assert (
        param2template(
            value="${{ params.start-dt | fmt }}",
            params={"params": {"start-dt": datetime(2024, 6, 12)}},
        )
        == "2024-06-12 00:00:00"
    )

    assert (
        param2template(
            value="${{ params.value | coalesce('foo') }}",
            params={"params": {"value": None}},
        )
        == "foo"
    )

    assert (
        param2template(
            value="${{ params.value | coalesce('foo') }}",
            params={"params": {"value": "bar"}},
        )
        == "bar"
    )

    assert (
        param2template(
            value="${{ params.data | getitem('key') }}",
            params={"params": {"data": {"key": "value"}}},
        )
        == "value"
    )

    assert (
        param2template(
            value="${{ params.data | getitem('foo', 'bar') }}",
            params={"params": {"data": {"key": "value"}}},
        )
        == "bar"
    )

    assert (
        param2template(
            value="${{ params.data | getitem(1, 'bar') }}",
            params={"params": {"data": {1: "value"}}},
        )
        == "value"
    )

    assert (
        param2template(
            value="${{ params.range | getindex(0) }}",
            params={"params": {"range": [1, 2, 3]}},
        )
        == 1
    )

    with pytest.raises(UtilError):
        param2template(
            value="${{ params.value | abs12 }}",
            params={"params": {"value": -5}},
        )

    value: str = param2template(
        value="${{ params.asat-dt | fmt(fmt='%Y%m%d') }}",
        params={"params": {"asat-dt": datetime(2024, 8, 1)}},
    )
    assert "20240801" == value

    with pytest.raises(UtilError):
        param2template(
            value="${{ params.asat-dt | fmt(fmt='%Y%m%d) }}",
            params={
                "params": {"asat-dt": datetime(2024, 8, 1)},
            },
        )

    with pytest.raises(UtilError):
        param2template(
            value="${{ params.data | getitem(1, 'bar') }}",
            params={"params": {"data": 1}},
        )

    with pytest.raises(UtilError):
        param2template(
            value="${{ params.range | getindex(4) }}",
            params={"params": {"range": [1, 2, 3]}},
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

    assert not not_in_template(None)


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

    assert not has_template(None)
