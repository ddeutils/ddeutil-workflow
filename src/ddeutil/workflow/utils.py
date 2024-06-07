# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from datetime import date, datetime
from functools import wraps
from importlib import import_module
from typing import Any, Callable, Literal, Optional, Protocol, Union

from ddeutil.core import lazy
from ddeutil.io.models.lineage import dt_now
from pydantic import BaseModel, Field
from pydantic.functional_validators import model_validator
from typing_extensions import Self


class TagFunc(Protocol):
    """Tag Function Protocol"""

    name: str
    tag: str

    def __call__(self, *args, **kwargs): ...


def tag(tag_value: str, name: str | None = None):
    """Tag decorator function that set function attributes, ``tag`` and ``name``
    for making registries variable.

    :param: tag_value: A tag value for make different use-case of a function.
    :param: name: A name that keeping in registries.
    """

    def func_internal(func: TagFunc):
        func.tag = tag_value
        func.name = name or func.__name__.replace("_", "-")

        @wraps(func)
        def wrapped(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapped

    return func_internal


def make_registry(module: str) -> dict[str, dict[str, Callable[[], TagFunc]]]:
    """Return registries of all functions that able to called with task."""
    rs: dict[str, dict[str, Callable[[], Callable]]] = {}
    for fstr, func in inspect.getmembers(
        import_module(module), inspect.isfunction
    ):
        if not hasattr(func, "tag"):
            continue

        if func.name in rs:
            if func.tag in rs[func.name]:
                raise ValueError(
                    f"The tag {func.tag!r} already exists on module {module}"
                )
            rs[func.name][func.tag] = lazy(f"{module}.{fstr}")
            continue

        # NOTE: Create new register name if it not exists
        rs[func.name] = {func.tag: lazy(f"{module}.{fstr}")}
    return rs


class BaseParams(BaseModel, ABC):
    """Base Parameter that use to make Params Model."""

    desc: Optional[str] = None
    required: bool = True
    type: str

    @abstractmethod
    def receive(self, value: Optional[Any] = None) -> Any:
        raise ValueError(
            "Receive value and validate typing before return valid value."
        )


class DefaultParams(BaseParams):
    """Default Parameter that will check default if it required"""

    default: Optional[str] = None

    @abstractmethod
    def receive(self, value: Optional[Any] = None) -> Any:
        raise ValueError(
            "Receive value and validate typing before return valid value."
        )

    @model_validator(mode="after")
    def check_default(self) -> Self:
        if not self.required and self.default is None:
            raise ValueError(
                "Default should set when this parameter does not required."
            )
        return self


class DatetimeParams(DefaultParams):
    """Datetime parameter."""

    type: Literal["datetime"] = "datetime"
    required: bool = False
    default: datetime = Field(default_factory=dt_now)

    def receive(self, value: str | datetime | date | None = None) -> datetime:
        if value is None:
            return self.default

        if isinstance(value, datetime):
            return value
        elif isinstance(value, date):
            return datetime(value.year, value.month, value.day)
        elif not isinstance(value, str):
            raise ValueError(
                f"Value that want to convert to datetime does not support for "
                f"type: {type(value)}"
            )
        return datetime.fromisoformat(value)


class StrParams(DefaultParams):
    """String parameter."""

    type: Literal["str"] = "str"

    def receive(self, value: Optional[str] = None) -> str | None:
        if value is None:
            return self.default
        return str(value)


class IntParams(DefaultParams):
    """Integer parameter."""

    type: Literal["int"] = "int"

    def receive(self, value: Optional[int] = None) -> int | None:
        if value is None:
            return self.default
        if not isinstance(value, int):
            try:
                return int(str(value))
            except TypeError as err:
                raise ValueError(
                    f"Value that want to convert to integer does not support "
                    f"for type: {type(value)}"
                ) from err
        return value


class ChoiceParams(BaseParams):
    type: Literal["choice"] = "choice"
    options: list[str]

    def receive(self, value: Optional[str] = None) -> str:
        """Receive value that match with options."""
        # NOTE:
        #   Return the first value in options if does not pass any input value
        if value is None:
            return self.options[0]
        if any(value not in self.options):
            raise ValueError(f"{value} does not match any value in options")
        return value


Params = Union[
    ChoiceParams,
    DatetimeParams,
    StrParams,
]
