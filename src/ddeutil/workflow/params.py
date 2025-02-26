# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""This module include all Param Models that use for parsing incoming parameters
that pass to the Workflow and Schedule objects.
"""
from __future__ import annotations

import decimal
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field

from .__types import TupleStr
from .exceptions import ParamValueException
from .utils import get_dt_now

__all__: TupleStr = (
    "ChoiceParam",
    "DatetimeParam",
    "IntParam",
    "Param",
    "StrParam",
)


class BaseParam(BaseModel, ABC):
    """Base Parameter that use to make any Params Models. The parameter type
    will dynamic with the setup type field that made from literal string.
    """

    desc: Optional[str] = Field(
        default=None, description="A description of parameter providing."
    )
    required: bool = Field(
        default=True,
        description="A require flag that force to pass this parameter value.",
    )
    type: str = Field(description="A type of parameter.")

    @abstractmethod
    def receive(self, value: Optional[Any] = None) -> Any:
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
    default: Optional[str] = Field(
        default=None,
        description="A default value if parameter does not pass.",
    )

    @abstractmethod
    def receive(self, value: Optional[Any] = None) -> Any:
        raise NotImplementedError(
            "Receive value and validate typing before return valid value."
        )


# TODO: Not implement this parameter yet
class DateParam(DefaultParam):  # pragma: no cov
    """Date parameter."""

    type: Literal["date"] = "date"

    def receive(self, value: Optional[str | date] = None) -> date: ...


class DatetimeParam(DefaultParam):
    """Datetime parameter."""

    type: Literal["datetime"] = "datetime"
    default: datetime = Field(default_factory=get_dt_now)

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
                f"Invalid the ISO format string: {value!r}"
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
    default: Optional[int] = Field(
        default=None,
        description="A default value if parameter does not pass.",
    )

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


# TODO: Not implement this parameter yet
class MappingParam(DefaultParam):  # pragma: no cov

    type: Literal["map"] = "map"
    default: dict[Any, Any] = Field(default_factory=dict)

    def receive(self, value: Optional[dict[Any, Any]] = None) -> dict[Any, Any]:
        if value is None:
            return self.default


# TODO: Not implement this parameter yet
class ArrayParam(DefaultParam):  # pragma: no cov

    type: Literal["array"] = "array"
    default: list[Any] = Field(default_factory=list)

    def receive(self, value: Optional[list[Any]] = None) -> list[Any]:
        if value is None:
            return self.default


Param = Annotated[
    Union[
        ChoiceParam,
        DatetimeParam,
        IntParam,
        StrParam,
    ],
    Field(discriminator="type"),
]
