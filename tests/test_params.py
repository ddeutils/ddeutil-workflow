from datetime import date, datetime
from decimal import Decimal

import pytest
from ddeutil.workflow import UTC
from ddeutil.workflow.errors import ParamError
from ddeutil.workflow.params import (
    ArrayParam,
    ChoiceParam,
    DateParam,
    DatetimeParam,
    DecimalParam,
    IntParam,
    MapParam,
    Param,
    StrParam,
)
from freezegun import freeze_time
from pydantic import TypeAdapter, ValidationError


def test_param():
    model = TypeAdapter(Param).validate_python({"type": "str"})
    assert isinstance(model, StrParam)

    model = TypeAdapter(Param).validate_python({"type": "int"})
    assert isinstance(model, IntParam)

    model = TypeAdapter(Param).validate_python({"type": "datetime"})
    assert isinstance(model, DatetimeParam)

    model = TypeAdapter(Param).validate_python(
        {"type": "choice", "options": [1, 2, 3]}
    )
    assert isinstance(model, ChoiceParam)

    with pytest.raises(ValidationError):
        TypeAdapter(Param).validate_python({"type": "string"})


def test_param_str():
    assert "foo" == StrParam().receive("foo")
    assert "bar" == StrParam(required=True, default="foo").receive("bar")

    assert StrParam().receive() is None
    assert StrParam().receive(1) == "1"
    assert StrParam().receive({"foo": "bar"}) == "{'foo': 'bar'}"


def test_param_date():
    assert DateParam().receive("2024-01-01") == date(2024, 1, 1)
    assert DateParam().receive(date(2024, 1, 1)) == date(2024, 1, 1)
    assert DateParam().receive(datetime(2024, 1, 1, 13, 24)) == date(2024, 1, 1)

    with pytest.raises(ParamError):
        DateParam().receive(2024)

    with pytest.raises(ParamError):
        DateParam().receive("2024")


@freeze_time("2024-01-01 00:00:00")
def test_param_date_default():
    assert DateParam().receive() == date(2024, 1, 1)


def test_param_datetime():
    assert DatetimeParam().receive("2024-01-01") == datetime(
        2024, 1, 1, tzinfo=UTC
    )
    assert DatetimeParam().receive(date(2024, 1, 1)) == datetime(
        2024, 1, 1, tzinfo=UTC
    )
    assert DatetimeParam().receive(datetime(2024, 1, 1)) == datetime(
        2024, 1, 1, tzinfo=UTC
    )

    with pytest.raises(ParamError):
        DatetimeParam().receive(2024)

    with pytest.raises(ParamError):
        DatetimeParam().receive("2024")


@freeze_time("2024-01-01 00:00:00")
def test_param_datetime_default():
    assert DatetimeParam().receive() == datetime(2024, 1, 1, tzinfo=UTC)


def test_param_int():
    assert 1 == IntParam().receive(1)
    assert 1 == IntParam().receive("1")
    assert 0 == IntParam(default=0).receive()

    with pytest.raises(ParamError):
        IntParam().receive(1.0)

    with pytest.raises(ParamError):
        IntParam().receive("test")


def test_param_choice():
    assert "foo" == ChoiceParam(options=["foo", "bar"]).receive("foo")
    assert "foo" == ChoiceParam(options=["foo", "bar"]).receive()

    with pytest.raises(ParamError):
        ChoiceParam(options=["foo", "bar"]).receive("baz")


def test_param_array():
    assert [7, 8] == ArrayParam(default=[1]).receive([7, 8])
    assert [7, 8] == ArrayParam(default=[1]).receive((7, 8))

    # NOTE: If receive set type it does not guarantee ordering.
    assert {7, 8} == set(ArrayParam(default=[1]).receive({7, 8}))

    assert [1, 2, 3] == ArrayParam(default=[1]).receive("[1, 2, 3]")
    assert [1] == ArrayParam(default=[1]).receive()
    assert [] == ArrayParam().receive()

    with pytest.raises(ParamError):
        ArrayParam().receive('{"foo": 1}')

    with pytest.raises(ParamError):
        ArrayParam().receive("foo")

    with pytest.raises(ParamError):
        ArrayParam().receive(100)


def test_param_map():
    assert {1: "test"} == MapParam(default={"key": "value"}).receive(
        {1: "test"}
    )
    assert {"foo": "bar"} == MapParam(default={"key": "value"}).receive(
        '{"foo": "bar"}'
    )
    assert {"key": "value"} == MapParam(default={"key": "value"}).receive()
    assert {} == MapParam().receive()

    with pytest.raises(ParamError):
        MapParam().receive('["foo", 1]')

    with pytest.raises(ParamError):
        MapParam().receive(100)


def test_param_decimal():
    rs = DecimalParam().receive(value="1.015")
    respect = DecimalParam().rounding(Decimal(1.015))
    assert rs == respect
    assert not (rs > respect)
    assert not (rs < respect)
    assert not (rs == 1.015)

    assert Decimal(1) == DecimalParam().receive(1)

    with pytest.raises(TypeError):
        DecimalParam().receive(value=[1.2])

    with pytest.raises(ValueError):
        DecimalParam().receive(value="a1.015")
