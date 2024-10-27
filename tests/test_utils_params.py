from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from ddeutil.workflow.exceptions import ParamValueException
from ddeutil.workflow.utils import (
    ChoiceParam,
    DatetimeParam,
    IntParam,
    StrParam,
)
from freezegun import freeze_time


def test_param_str():
    assert "foo" == StrParam().receive("foo")
    assert "bar" == StrParam(required=True, default="foo").receive("bar")


def test_param_datetime():
    assert DatetimeParam().receive("2024-01-01") == datetime(2024, 1, 1)
    assert DatetimeParam().receive(date(2024, 1, 1)) == datetime(2024, 1, 1)
    assert DatetimeParam().receive(datetime(2024, 1, 1)) == datetime(2024, 1, 1)

    with pytest.raises(ParamValueException):
        DatetimeParam().receive(2024)

    with pytest.raises(ParamValueException):
        DatetimeParam().receive("2024")


@freeze_time("2024-01-01 00:00:00")
def test_param_datetime_default():
    assert DatetimeParam().receive() == datetime(
        2024, 1, 1, tzinfo=ZoneInfo("UTC")
    )


def test_param_int():
    assert 1 == IntParam().receive(1)
    assert 1 == IntParam().receive("1")
    assert 0 == IntParam(default=0).receive()

    with pytest.raises(ParamValueException):
        IntParam().receive(1.0)

    with pytest.raises(ParamValueException):
        IntParam().receive("test")


def test_param_choice():
    assert "foo" == ChoiceParam(options=["foo", "bar"]).receive("foo")
    assert "foo" == ChoiceParam(options=["foo", "bar"]).receive()

    with pytest.raises(ParamValueException):
        ChoiceParam(options=["foo", "bar"]).receive("baz")
