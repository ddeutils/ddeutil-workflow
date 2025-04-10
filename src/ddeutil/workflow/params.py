# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""This module include all Param Pydantic Models that use for parsing an
incoming parameters that was passed to the Workflow and Schedule objects before
execution or release methods.

    The Param model allow you to handle validation and preparation steps before
passing an input value to target execution method.
"""
from __future__ import annotations

import decimal
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Annotated, Any, Literal, Optional, TypeVar, Union

from ddeutil.core import str2dict, str2list
from pydantic import BaseModel, Field

from .__types import TupleStr
from .exceptions import ParamValueException
from .utils import get_d_now, get_dt_now

__all__: TupleStr = (
    "ChoiceParam",
    "DatetimeParam",
    "DateParam",
    "IntParam",
    "Param",
    "StrParam",
    "ArrayParam",
    "MapParam",
)

T = TypeVar("T")


class BaseParam(BaseModel, ABC):
    """Base Parameter that use to make any Params Models. The parameter type
    will dynamic with the setup type field that made from literal string.
    """

    desc: Optional[str] = Field(
        default=None,
        description=(
            "A description of this parameter provide to the workflow model."
        ),
    )
    required: bool = Field(
        default=True,
        description="A require flag that force to pass this parameter value.",
    )
    type: str = Field(description="A type of parameter.")

    @abstractmethod
    def receive(self, value: Optional[T] = None) -> T:
        """Abstract method receive value to this parameter model."""
        raise NotImplementedError(
            "Receive value and validate typing before return valid value."
        )


class DefaultParam(BaseParam):
    """Default Parameter that will check default if it required. This model do
    not implement the `receive` method.
    """

    required: bool = Field(
        default=False,
        description="A require flag for the default-able parameter value.",
    )
    default: Optional[Any] = Field(
        default=None,
        description="A default value if parameter does not pass.",
    )

    @abstractmethod
    def receive(self, value: Optional[Any] = None) -> Any:
        """Abstract method receive value to this parameter model."""
        raise NotImplementedError(
            "Receive value and validate typing before return valid value."
        )


class DateParam(DefaultParam):  # pragma: no cov
    """Date parameter model."""

    type: Literal["date"] = "date"
    default: date = Field(
        default_factory=get_d_now,
        description="A default date that make from the current date func.",
    )

    def receive(self, value: Optional[str | datetime | date] = None) -> date:
        """Receive value that match with date. If an input value pass with
        None, it will use default value instead.

        :param value: A value that want to validate with date parameter type.

        :rtype: date
        """
        if value is None:
            return self.default

        if isinstance(value, datetime):
            return value.date()
        elif isinstance(value, date):
            return value
        elif not isinstance(value, str):
            raise ParamValueException(
                f"Value that want to convert to date does not support for "
                f"type: {type(value)}"
            )
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise ParamValueException(
                f"Invalid the ISO format string for date: {value!r}"
            ) from None


class DatetimeParam(DefaultParam):
    """Datetime parameter model."""

    type: Literal["datetime"] = "datetime"
    default: datetime = Field(
        default_factory=get_dt_now,
        description=(
            "A default datetime that make from the current datetime func."
        ),
    )

    def receive(self, value: str | datetime | date | None = None) -> datetime:
        """Receive value that match with datetime. If an input value pass with
        None, it will use default value instead.

        :param value: A value that want to validate with datetime parameter
            type.

        :rtype: datetime
        """
        if value is None:
            return self.default

        if isinstance(value, datetime):
            return value
        elif isinstance(value, date):
            return datetime(value.year, value.month, value.day)
        elif not isinstance(value, str):
            raise ParamValueException(
                f"Value that want to convert to datetime does not support for "
                f"type: {type(value)}"
            )
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            raise ParamValueException(
                f"Invalid the ISO format string for datetime: {value!r}"
            ) from None


class StrParam(DefaultParam):
    """String parameter."""

    type: Literal["str"] = "str"

    def receive(self, value: str | None = None) -> str | None:
        """Receive value that match with str.

        :param value: A value that want to validate with string parameter type.
        :rtype: str | None
        """
        if value is None:
            return self.default
        return str(value)


class IntParam(DefaultParam):
    """Integer parameter."""

    type: Literal["int"] = "int"

    def receive(self, value: int | None = None) -> int | None:
        """Receive value that match with int.

        :param value: A value that want to validate with integer parameter type.
        :rtype: int | None
        """
        if value is None:
            return self.default
        if not isinstance(value, int):
            try:
                return int(str(value))
            except ValueError as err:
                raise ParamValueException(
                    f"Value can not convert to int, {value}, with base 10"
                ) from err
        return value


# TODO: Not implement this parameter yet
class DecimalParam(DefaultParam):  # pragma: no cov
    type: Literal["decimal"] = "decimal"

    def receive(self, value: float | None = None) -> decimal.Decimal: ...


class ChoiceParam(BaseParam):
    """Choice parameter."""

    type: Literal["choice"] = "choice"
    options: Union[list[str], list[int]] = Field(
        description="A list of choice parameters that able be str or int.",
    )

    def receive(self, value: Union[str, int] | None = None) -> Union[str, int]:
        """Receive value that match with options.

        :param value: A value that want to select from the options field.
        :rtype: str
        """
        # NOTE:
        #   Return the first value in options if it does not pass any input value
        if value is None:
            return self.options[0]
        if value not in self.options:
            raise ParamValueException(
                f"{value!r} does not match any value in choice options."
            )
        return value


class MapParam(DefaultParam):  # pragma: no cov
    """Map parameter."""

    type: Literal["map"] = "map"
    default: dict[Any, Any] = Field(
        default_factory=dict,
        description="A default dict that make from the dict built-in func.",
    )

    def receive(
        self,
        value: Optional[Union[dict[Any, Any], str]] = None,
    ) -> dict[Any, Any]:
        """Receive value that match with map type.

        :param value: A value that want to validate with map parameter type.
        :rtype: dict[Any, Any]
        """
        if value is None:
            return self.default

        if isinstance(value, str):
            try:
                value: dict[Any, Any] = str2dict(value)
            except ValueError as e:
                raise ParamValueException(
                    f"Value that want to convert to map does not support for "
                    f"type: {type(value)}"
                ) from e
        elif not isinstance(value, dict):
            raise ParamValueException(
                f"Value of map param support only string-dict or dict type, "
                f"not {type(value)}"
            )
        return value


class ArrayParam(DefaultParam):  # pragma: no cov
    """Array parameter."""

    type: Literal["array"] = "array"
    default: list[Any] = Field(
        default_factory=list,
        description="A default list that make from the list built-in func.",
    )

    def receive(
        self, value: Optional[Union[list[T], tuple[T, ...], str]] = None
    ) -> list[T]:
        """Receive value that match with array type.

        :param value: A value that want to validate with array parameter type.
        :rtype: list[Any]
        """
        if value is None:
            return self.default
        if isinstance(value, str):
            try:
                value: list[T] = str2list(value)
            except ValueError as e:
                raise ParamValueException(
                    f"Value that want to convert to array does not support for "
                    f"type: {type(value)}"
                ) from e
        elif isinstance(value, (tuple, set)):
            return list(value)
        elif not isinstance(value, list):
            raise ParamValueException(
                f"Value of map param support only string-list or list type, "
                f"not {type(value)}"
            )
        return value


Param = Annotated[
    Union[
        MapParam,
        ArrayParam,
        ChoiceParam,
        DatetimeParam,
        DateParam,
        IntParam,
        StrParam,
    ],
    Field(discriminator="type"),
]
