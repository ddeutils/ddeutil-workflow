# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import inspect
import os
import stat
from abc import ABC, abstractmethod
from datetime import date, datetime
from functools import wraps
from importlib import import_module
from pathlib import Path
from typing import Any, Callable, Literal, Optional, Protocol, Union

from ddeutil.core import lazy
from ddeutil.io import PathData
from ddeutil.io.models.lineage import dt_now
from pydantic import BaseModel, Field
from pydantic.functional_validators import model_validator
from typing_extensions import Self

from .__types import DictData


class Engine(BaseModel):
    """Engine Model"""

    paths: PathData = Field(default_factory=PathData)
    registry: list[str] = Field(
        default_factory=lambda: [
            "ddeutil.workflow",
        ],
    )

    @model_validator(mode="before")
    def __prepare_registry(cls, values: DictData) -> DictData:
        """Prepare registry value that passing with string type. It convert the
        string type to list of string.
        """
        if (_regis := values.get("registry")) and isinstance(_regis, str):
            values["registry"] = [_regis]
        return values


class ConfParams(BaseModel):
    """Params Model"""

    engine: Engine = Field(
        default_factory=Engine,
        description="A engine mapping values.",
    )


def config() -> ConfParams:
    """Load Config data from ``workflows-conf.yaml`` file."""
    root_path: str = os.getenv("WORKFLOW_ROOT_PATH", ".")

    regis: list[str] = []
    if regis_env := os.getenv("WORKFLOW_CORE_REGISTRY"):
        regis = [r.strip() for r in regis_env.split(",")]

    conf_path: str = (
        f"{root_path}/{conf_env}"
        if (conf_env := os.getenv("WORKFLOW_CORE_PATH_CONF"))
        else None
    )
    return ConfParams.model_validate(
        obj={
            "engine": {
                "registry": regis,
                "paths": {
                    "root": root_path,
                    "conf": conf_path,
                },
            },
        }
    )


class TagFunc(Protocol):
    """Tag Function Protocol"""

    name: str
    tag: str

    def __call__(self, *args, **kwargs): ...


def tag(value: str, name: str | None = None):
    """Tag decorator function that set function attributes, ``tag`` and ``name``
    for making registries variable.

    :param: value: A tag value for make different use-case of a function.
    :param: name: A name that keeping in registries.
    """

    def func_internal(func: callable) -> TagFunc:
        func.tag = value
        func.name = name or func.__name__.replace("_", "-")

        @wraps(func)
        def wrapped(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapped

    return func_internal


Registry = dict[str, Callable[[], TagFunc]]


def make_registry(submodule: str) -> dict[str, Registry]:
    """Return registries of all functions that able to called with task.

    :param submodule: A module prefix that want to import registry.
    """
    rs: dict[str, Registry] = {}
    for module in config().engine.registry:
        # NOTE: try to sequential import task functions
        try:
            importer = import_module(f"{module}.{submodule}")
        except ModuleNotFoundError:
            continue

        for fstr, func in inspect.getmembers(importer, inspect.isfunction):
            # NOTE: check function attribute that already set tag by
            #   ``utils.tag`` decorator.
            if not hasattr(func, "tag"):
                continue

            # NOTE: Create new register name if it not exists
            if func.name not in rs:
                rs[func.name] = {func.tag: lazy(f"{module}.{submodule}.{fstr}")}
                continue

            if func.tag in rs[func.name]:
                raise ValueError(
                    f"The tag {func.tag!r} already exists on "
                    f"{module}.{submodule}, you should change this tag name or "
                    f"change it func name."
                )
            rs[func.name][func.tag] = lazy(f"{module}.{submodule}.{fstr}")

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


def make_exec(path: str | Path):
    """Change mode of file to be executable file."""
    f: Path = Path(path) if isinstance(path, str) else path
    f.chmod(f.stat().st_mode | stat.S_IEXEC)
