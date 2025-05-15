from inspect import isfunction
from unittest import mock

import pytest
from ddeutil.workflow.conf import Config
from ddeutil.workflow.errors import UtilError
from ddeutil.workflow.reusables import (
    custom_filter,
    get_args_const,
    make_filter_registry,
    map_post_filter,
)


@custom_filter("foo")
def foo(_: str) -> str:  # pragma: no cov
    return "bar"


@custom_filter("raise_err")
def raise_err(_: str) -> None:  # pragma: no cov
    raise ValueError("Demo raise error from filter function")


@custom_filter("raise_util_exception")
def raise_util(_: str) -> None:  # pragma: no cov
    raise UtilError("Demo raise error from filter function")


@mock.patch.object(
    Config,
    "registry_filter",
    [
        "ddeutil.workflow.utils",
        "tests.test_reusables_template_filter",
        "foo.bar",
    ],
)
def test_make_registry_raise():
    assert isfunction(make_filter_registry()["foo"])
    assert "bar" == make_filter_registry()["foo"]("")

    filter_func = make_filter_registry()["foo"]
    assert filter_func.filter == "foo"
    assert filter_func.mark == "filter"


def test_get_args_const():
    name, args, kwargs = get_args_const('fmt(fmt="str")')
    assert name == "fmt"
    assert args == []
    assert kwargs["fmt"].value == "str"

    name, args, kwargs = get_args_const("datetime")
    assert name == "datetime"
    assert args == []
    assert kwargs == {}

    with pytest.raises(UtilError):
        get_args_const("lambda x: x + 1\nfoo()")

    with pytest.raises(UtilError):
        get_args_const('fmt(fmt="str") + fmt()')

    with pytest.raises(UtilError):
        get_args_const("foo(datetime.timedelta)")

    with pytest.raises(UtilError):
        get_args_const("foo(fmt=datetime.timedelta)")


@mock.patch.object(
    Config,
    "registry_filter",
    [
        "ddeutil.workflow.utils",
        "tests.test_reusables_template_filter",
        "foo.bar",
    ],
)
def test_map_post_filter():
    registry = make_filter_registry()
    assert "bar" == map_post_filter("demo", ["foo"], registry)
    assert "'bar'" == map_post_filter("bar", ["rstr"], registry)
    assert 1 == map_post_filter("1", ["int"], registry)
    assert ["foo", "bar"] == map_post_filter(
        {"foo": 1, "bar": 2}, ["keys", "list"], registry
    )
    assert [1, 2] == map_post_filter(
        {"foo": 1, "bar": 2}, ["values", "list"], registry
    )

    with pytest.raises(UtilError):
        map_post_filter("demo", ['rstr(fmt="foo")'], registry)

    with pytest.raises(UtilError):
        map_post_filter("demo", ["raise_err"], registry)

    with pytest.raises(UtilError):
        map_post_filter("2024", ["fmt"], registry)

    # NOTE: Raise util exception inside filter function
    with pytest.raises(UtilError):
        map_post_filter("foo", ["raise_util_exception"], registry)
