# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Parameter Models for Workflow Validation and Processing.

This module provides comprehensive parameter models for handling validation and
preparation of input values passed to workflows and scheduled executions. The
parameter system ensures type safety and provides default value management.

The parameter models support various data types including strings, numbers,
dates, choices, and complex types like maps and arrays. Each parameter type
provides validation and transformation capabilities.

Classes:
    BaseParam: Abstract base class for all parameter types.
    DefaultParam: Base class for parameters with default values.
    DateParam: Date parameter with validation.
    DatetimeParam: Datetime parameter with validation.
    StrParam: String parameter type.
    IntParam: Integer parameter type.
    FloatParam: Float parameter with precision control.
    DecimalParam: Decimal parameter for financial calculations.
    ChoiceParam: Parameter with predefined choices.
    MapParam: Dictionary/mapping parameter type.
    ArrayParam: List/array parameter type.

Example:
    ```python
    from ddeutil.workflow.params import StrParam, IntParam

    # Define parameters
    name_param = StrParam(desc="Username", required=True)
    age_param = IntParam(desc="User age", default=18, required=False)

    # Process values
    name = name_param.receive("John")
    age = age_param.receive(None)  # Uses default value
    ```
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal, Optional, TypeVar, Union

from ddeutil.core import str2dict, str2list
from pydantic import BaseModel, Field

from .__types import StrOrInt
from .errors import ParamError
from .utils import UTC, get_d_now, get_dt_now

T = TypeVar("T")


class BaseParam(BaseModel, ABC):
    """Base Parameter that use to make any Params Models.

    The parameter type will dynamic with the setup type field that made from
    literal string. This abstract base class provides the foundation for all
    parameter types with common validation and processing capabilities.
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
        """Abstract method receive value to this parameter model.

        Args:
            value: The value to validate and process.

        Returns:
            T: The validated and processed value.

        Raises:
            NotImplementedError: If not implemented by subclass.
        """
        raise NotImplementedError(
            "Receive value and validate typing before return valid value."
        )


class DefaultParam(BaseParam, ABC):
    """Default Parameter that will check default if it required.

    This model extends BaseParam and provides default value handling capabilities.
    It does not implement the `receive` method, which must be implemented by
    concrete subclasses.
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
        """Abstract method receive value to this parameter model.

        Args:
            value: The value to validate and process.

        Returns:
            Any: The validated and processed value.

        Raises:
            NotImplementedError: If not implemented by subclass.
        """
        raise NotImplementedError(
            "Receive value and validate typing before return valid value."
        )


class DateParam(DefaultParam):  # pragma: no cov
    """Date parameter model.

    This class provides date parameter validation and processing with support
    for various input formats including ISO date strings, datetime objects,
    and date objects.
    """

    type: Literal["date"] = "date"
    default: date = Field(
        default_factory=get_d_now,
        description="A default date that make from the current date func.",
    )

    def receive(
        self, value: Optional[Union[str, datetime, date]] = None
    ) -> date:
        """Receive value that match with date.

        If an input value pass with None, it will use default value instead.

        Args:
            value: A value that want to validate with date parameter type.

        Returns:
            date: The validated date value.

        Raises:
            ParamError: If the value cannot be converted to a valid date.
        """
        if value is None:
            return self.default

        if isinstance(value, datetime):
            return value.date()
        elif isinstance(value, date):
            return value
        elif not isinstance(value, str):
            raise ParamError(
                f"Value that want to convert to date does not support for "
                f"type: {type(value)}"
            )
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise ParamError(
                f"Invalid the ISO format string for date: {value!r}"
            ) from None


class DatetimeParam(DefaultParam):
    """Datetime parameter model.

    This class provides datetime parameter validation and processing with support
    for various input formats including ISO datetime strings, datetime objects,
    and date objects. All datetime values are normalized to UTC timezone.
    """

    type: Literal["datetime"] = "datetime"
    default: datetime = Field(
        default_factory=get_dt_now,
        description=(
            "A default datetime that make from the current datetime func."
        ),
    )

    def receive(
        self, value: Optional[Union[str, datetime, date]] = None
    ) -> datetime:
        """Receive value that match with datetime.

        If an input value pass with None, it will use default value instead.

        Args:
            value: A value that want to validate with datetime parameter type.

        Returns:
            datetime: The validated datetime value in UTC timezone.

        Raises:
            ParamError: If the value cannot be converted to a valid datetime.
        """
        if value is None:
            return self.default

        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value.astimezone(UTC)
        elif isinstance(value, date):
            return datetime(value.year, value.month, value.day, tzinfo=UTC)
        elif not isinstance(value, str):
            raise ParamError(
                f"Value that want to convert to datetime does not support for "
                f"type: {type(value)}"
            )
        try:
            return datetime.fromisoformat(value).replace(tzinfo=UTC)
        except ValueError:
            raise ParamError(
                f"Invalid the ISO format string for datetime: {value!r}"
            ) from None


class StrParam(DefaultParam):
    """String parameter.

    This class provides string parameter validation and processing with support
    for converting various input types to strings.
    """

    type: Literal["str"] = "str"

    def receive(self, value: Optional[Any] = None) -> Optional[str]:
        """Receive value that match with str.

        Args:
            value: A value that want to validate with string parameter type.

        Returns:
            Optional[str]: The validated string value or None.
        """
        if value is None:
            return self.default
        return str(value)


class IntParam(DefaultParam):
    """Integer parameter.

    This class provides integer parameter validation and processing with support
    for converting various numeric types to integers.
    """

    type: Literal["int"] = "int"

    def receive(self, value: Optional[StrOrInt] = None) -> Optional[int]:
        """Receive value that match with int.

        Args:
            value: A value that want to validate with integer parameter type.

        Returns:
            Optional[int]: The validated integer value or None.

        Raises:
            ParamError: If the value cannot be converted to an integer.
        """
        if value is None:
            return self.default
        if not isinstance(value, int):
            try:
                return int(str(value))
            except ValueError as err:
                raise ParamError(
                    f"Value can not convert to int, {value}, with base 10"
                ) from err
        return value


class FloatParam(DefaultParam):  # pragma: no cov
    """Float parameter.

    This class provides float parameter validation and processing with precision
    control for rounding float values to a specified number of decimal places.
    """

    type: Literal["float"] = "float"
    precision: int = 6

    def rounding(self, value: float) -> float:
        """Rounding float value with the specific precision field.

        Args:
            value: A float value that want to round with the precision value.

        Returns:
            float: The rounded float value.
        """
        round_str: str = f"{{0:.{self.precision}f}}"
        return float(round_str.format(round(value, self.precision)))

    def receive(
        self, value: Optional[Union[float, int, str]] = None
    ) -> Optional[float]:
        """Receive value that match with float.

        Args:
            value: A value that want to validate with float parameter type.

        Returns:
            Optional[float]: The validated float value or None.

        Raises:
            TypeError: If the value type is not supported.
        """
        if value is None:
            return self.default

        if isinstance(value, float):
            return self.rounding(value)
        elif isinstance(value, int):
            return self.rounding(float(value))
        elif not isinstance(value, str):
            raise TypeError(
                "Received value type does not math with str, float, or int."
            )
        return self.rounding(float(value))


class DecimalParam(DefaultParam):  # pragma: no cov
    """Decimal parameter.

    This class provides decimal parameter validation and processing with precision
    control for financial calculations and exact decimal arithmetic.
    """

    type: Literal["decimal"] = "decimal"
    precision: int = 6

    def rounding(self, value: Decimal) -> Decimal:
        """Rounding decimal value with the specific precision field.

        Args:
            value: A Decimal value that want to round with the precision value.

        Returns:
            Decimal: The rounded decimal value.
        """
        return value.quantize(Decimal(10) ** -self.precision)

    def receive(
        self, value: Optional[Union[float, int, str, Decimal]] = None
    ) -> Decimal:
        """Receive value that match with decimal.

        Args:
            value: A value that want to validate with decimal parameter type.

        Returns:
            Decimal: The validated decimal value.

        Raises:
            TypeError: If the value type is not supported.
            ValueError: If the string cannot be converted to a valid decimal.
        """
        if value is None:
            return self.default

        if isinstance(value, (float, int)):
            return self.rounding(Decimal(value))
        elif isinstance(value, Decimal):
            return self.rounding(value)
        elif not isinstance(value, str):
            raise TypeError(
                "Received value type does not math with str, float, or decimal."
            )

        try:
            return self.rounding(Decimal(value))
        except InvalidOperation as e:
            raise ValueError(
                "String that want to convert to decimal type does not valid."
            ) from e


class ChoiceParam(BaseParam):
    """Choice parameter.

    This class provides choice parameter validation and processing with support
    for predefined options. If no value is provided, it returns the first option.
    """

    type: Literal["choice"] = "choice"
    options: Union[list[str], list[int]] = Field(
        description="A list of choice parameters that able be str or int.",
    )

    def receive(self, value: Optional[StrOrInt] = None) -> StrOrInt:
        """Receive value that match with options.

        Args:
            value: A value that want to select from the options field.

        Returns:
            StrOrInt: The validated choice value.

        Raises:
            ParamError: If the value is not in the available options.
        """
        # NOTE:
        #   Return the first value in options if it does not pass any input
        #   value.
        if value is None:
            return self.options[0]
        if value not in self.options:
            raise ParamError(
                f"{value!r} does not match any value in choice options."
            )
        return value


class MapParam(DefaultParam):
    """Map parameter.

    This class provides dictionary/mapping parameter validation and processing
    with support for converting string representations to dictionaries.
    """

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

        Args:
            value: A value that want to validate with map parameter type.

        Returns:
            dict[Any, Any]: The validated dictionary value.

        Raises:
            ParamError: If the value cannot be converted to a valid dictionary.
        """
        if value is None:
            return self.default

        if isinstance(value, str):
            try:
                value: dict[Any, Any] = str2dict(value)
            except ValueError as e:
                raise ParamError(
                    f"Value that want to convert to map does not support for "
                    f"type: {type(value)}"
                ) from e
        elif not isinstance(value, dict):
            raise ParamError(
                f"Value of map param support only string-dict or dict type, "
                f"not {type(value)}"
            )
        return value


class ArrayParam(DefaultParam):
    """Array parameter.

    This class provides list/array parameter validation and processing with support
    for converting various sequence types to lists.
    """

    type: Literal["array"] = "array"
    default: list[Any] = Field(
        default_factory=list,
        description="A default list that make from the list built-in func.",
    )

    def receive(
        self, value: Optional[Union[list[T], tuple[T, ...], set[T], str]] = None
    ) -> list[T]:
        """Receive value that match with array type.

        Args:
            value: A value that want to validate with array parameter type.

        Returns:
            list[T]: The validated list value.

        Raises:
            ParamError: If the value cannot be converted to a valid list.
        """
        if value is None:
            return self.default
        if isinstance(value, str):
            try:
                value: list[T] = str2list(value)
            except ValueError as e:
                raise ParamError(
                    f"Value that want to convert to array does not support for "
                    f"type: {type(value)}"
                ) from e
        elif isinstance(value, (tuple, set)):
            return list(value)
        elif not isinstance(value, list):
            raise ParamError(
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
        FloatParam,
        DecimalParam,
        IntParam,
        StrParam,
    ],
    Field(
        discriminator="type",
        description=(
            "A parameter models that use for validate and receive on the "
            "workflow execution."
        ),
    ),
]
