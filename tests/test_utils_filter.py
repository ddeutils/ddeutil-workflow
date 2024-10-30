from inspect import isfunction
from unittest import mock

import pytest
from ddeutil.workflow.conf import Config
from ddeutil.workflow.exceptions import UtilException
from ddeutil.workflow.utils import (
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


def test_make_registry_raise():
    with mock.patch.object(
        Config,
        "regis_filter_str",
        "ddeutil.workflow.utils,tests.test_utils_filter,foo.bar",
    ):
        assert isfunction(make_filter_registry()["foo"])
        assert "bar" == make_filter_registry()["foo"]("")


def test_get_args_const():
    name, args, kwargs = get_args_const('fmt(fmt="str")')
    assert name == "fmt"
    assert args == []
    assert kwargs["fmt"].value == "str"

    name, args, kwargs = get_args_const("datetime")
    assert name == "datetime"
    assert args == []
    assert kwargs == {}

    with pytest.raises(UtilException):
        get_args_const("lambda x: x + 1\nfoo()")

    with pytest.raises(UtilException):
        get_args_const('fmt(fmt="str") + fmt()')

    with pytest.raises(UtilException):
        get_args_const("foo(datetime.timedelta)")

    with pytest.raises(UtilException):
        get_args_const("foo(fmt=datetime.timedelta)")


def test_map_post_filter():
    with mock.patch.object(
        Config,
        "regis_filter_str",
        "ddeutil.workflow.utils,tests.test_utils_filter,foo.bar",
    ):
        assert "bar" == map_post_filter("demo", ["foo"], make_filter_registry())
        assert "'bar'" == map_post_filter(
            "bar", ["rstr"], make_filter_registry()
        )

        with pytest.raises(UtilException):
            map_post_filter(
                "demo",
                ['rstr(fmt="foo")'],
                make_filter_registry(),
            )

        with pytest.raises(UtilException):
            map_post_filter(
                "demo",
                ["raise_err"],
                make_filter_registry(),
            )

        with pytest.raises(UtilException):
            map_post_filter(
                "2024",
                ["fmt"],
                make_filter_registry(),
            )
