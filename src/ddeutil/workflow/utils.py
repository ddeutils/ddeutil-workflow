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
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import wraps
from hashlib import md5
from importlib import import_module
from itertools import product
from pathlib import Path
from typing import Any, Callable, Literal, Optional, Protocol, Union
from zoneinfo import ZoneInfo

from ddeutil.core import getdot, hasdot, lazy
from ddeutil.io import PathData
from ddeutil.io.models.lineage import dt_now
from pydantic import BaseModel, Field
from pydantic.functional_validators import model_validator
from typing_extensions import Self

from .__types import DictData, Matrix, Re
from .exceptions import ParamValueException, UtilException


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


def gen_id(value: Any, *, sensitive: bool = True, unique: bool = False) -> str:
    """Generate running ID for able to tracking. This generate process use `md5`
    function.

    :param value:
    :param sensitive:
    :param unique:
    :rtype: str
    """
    if not isinstance(value, str):
        value: str = str(value)

    tz: ZoneInfo = ZoneInfo(os.getenv("WORKFLOW_CORE_TIMEZONE", "UTC"))
    return md5(
        (
            f"{(value if sensitive else value.lower())}"
            + (f"{datetime.now(tz=tz):%Y%m%d%H%M%S%f}" if unique else "")
        ).encode()
    ).hexdigest()


class TagFunc(Protocol):
    """Tag Function Protocol"""

    name: str
    tag: str

    def __call__(self, *args, **kwargs): ...


def tag(name: str, alias: str | None = None):
    """Tag decorator function that set function attributes, ``tag`` and ``name``
    for making registries variable.

    :param: name: A tag value for make different use-case of a function.
    :param: alias: A alias function name that keeping in registries. If this
        value does not supply, it will use original function name from __name__.
    """

    def func_internal(func: Callable[[...], Any]) -> TagFunc:
        func.tag = name
        func.name = alias or func.__name__.replace("_", "-")

        @wraps(func)
        def wrapped(*args, **kwargs):
            # NOTE: Able to do anything before calling hook function.
            return func(*args, **kwargs)

        return wrapped

    return func_internal


Registry = dict[str, Callable[[], TagFunc]]


def make_registry(submodule: str) -> dict[str, Registry]:
    """Return registries of all functions that able to called with task.

    :param submodule: A module prefix that want to import registry.
    :rtype: dict[str, Registry]
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


class BaseParam(BaseModel, ABC):
    """Base Parameter that use to make Params Model."""

    desc: Optional[str] = None
    required: bool = True
    type: str

    @abstractmethod
    def receive(self, value: Optional[Any] = None) -> Any:
        raise ParamValueException(
            "Receive value and validate typing before return valid value."
        )


class DefaultParam(BaseParam):
    """Default Parameter that will check default if it required"""

    default: Optional[str] = None

    @abstractmethod
    def receive(self, value: Optional[Any] = None) -> Any:
        raise ParamValueException(
            "Receive value and validate typing before return valid value."
        )

    @model_validator(mode="after")
    def check_default(self) -> Self:
        if not self.required and self.default is None:
            raise ParamValueException(
                "Default should set when this parameter does not required."
            )
        return self


class DatetimeParam(DefaultParam):
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
            raise ParamValueException(
                f"Value that want to convert to datetime does not support for "
                f"type: {type(value)}"
            )
        return datetime.fromisoformat(value)


class StrParam(DefaultParam):
    """String parameter."""

    type: Literal["str"] = "str"

    def receive(self, value: Optional[str] = None) -> str | None:
        if value is None:
            return self.default
        return str(value)


class IntParam(DefaultParam):
    """Integer parameter."""

    type: Literal["int"] = "int"

    def receive(self, value: Optional[int] = None) -> int | None:
        if value is None:
            return self.default
        if not isinstance(value, int):
            try:
                return int(str(value))
            except TypeError as err:
                raise ParamValueException(
                    f"Value that want to convert to integer does not support "
                    f"for type: {type(value)}"
                ) from err
        return value


class ChoiceParam(BaseParam):
    type: Literal["choice"] = "choice"
    options: list[str]

    def receive(self, value: Optional[str] = None) -> str:
        """Receive value that match with options."""
        # NOTE:
        #   Return the first value in options if does not pass any input value
        if value is None:
            return self.options[0]
        if any(value not in self.options):
            raise ParamValueException(
                f"{value!r} does not match any value in choice options."
            )
        return value


Param = Union[
    ChoiceParam,
    DatetimeParam,
    StrParam,
    IntParam,
]


@dataclass
class Result:
    """Result Dataclass object for passing parameter and receiving output from
    the pipeline execution.
    """

    status: int = field(default=2)
    context: DictData = field(default_factory=dict)


def make_exec(path: str | Path):
    """Change mode of file to be executable file."""
    f: Path = Path(path) if isinstance(path, str) else path
    f.chmod(f.stat().st_mode | stat.S_IEXEC)


FILTERS: dict[str, callable] = {
    "abs": abs,
}


def __map_filter(
    value: Any,
    post_filter: list[str],
):
    for f in post_filter:
        try:
            value: Any = FILTERS[f](value)
        except Exception:
            raise UtilException(
                f"The post-filter function: {f} does not fit with "
                f"{value}({type(value)})."
            ) from None
    return value


def __param2template(
    value: str,
    params: DictData,
    repr_flag: bool = False,
) -> Any:
    for found in Re.RE_CALLER.finditer(value):
        # NOTE:
        #   Get caller and filter values that setting inside;
        #
        #   ... ``${{ <caller-value> [ | <filter-value>] ... }}``
        #
        caller: str = found.group("caller")
        pfilter: list[str] = [
            i.strip()
            for i in (
                found.group("post_filters").strip().removeprefix("|").split("|")
            )
            if i != ""
        ]
        if not hasdot(caller, params):
            raise UtilException(f"The params does not set caller: {caller!r}.")

        if f_not_sup := [f for f in pfilter if f not in FILTERS]:
            raise UtilException(
                f"The post-filter: {f_not_sup} does not support yet."
            )

        # NOTE: from validate step, it guarantee that caller exists in params.
        getter: Any = getdot(caller, params)

        # NOTE: check type of vars
        if isinstance(getter, (str, int)):

            # NOTE: map post-filter function.
            getter: Any = __map_filter(getter, pfilter)

            value: str = value.replace(
                found.group(0), (repr(getter) if repr_flag else str(getter)), 1
            )
            continue

        # NOTE:
        #   If type of getter caller does not formatting, it will return origin
        #   value from the ``getdot`` function.
        if value.replace(found.group(0), "", 1) != "":
            raise UtilException(
                "Callable variable should not pass other outside ${{ ... }}"
            )
        return __map_filter(getter, pfilter)
    return value


def param2template(
    value: Any,
    params: DictData,
    *,
    repr_flag: bool = False,
) -> Any:
    """Pass param to template string that can search by ``RE_CALLER`` regular
    expression.

    :param value: A value that want to mapped with an params
    :param params: A parameter value that getting with matched regular
        expression.
    :param repr_flag: A repr flag for using repr instead of str if it set be
        true.

    :rtype: Any
    :returns: An any getter value from the params input.
    """
    if isinstance(value, dict):
        return {k: param2template(value[k], params) for k in value}
    elif isinstance(value, (list, tuple, set)):
        return type(value)([param2template(i, params) for i in value])
    elif not isinstance(value, str):
        return value
    return __param2template(value, params, repr_flag=repr_flag)


def dash2underscore(
    key: str,
    values: DictData,
    *,
    fixed: str | None = None,
) -> DictData:
    """Change key name that has dash to underscore."""
    if key in values:
        values[(fixed or key.replace("-", "_"))] = values.pop(key)
    return values


def cross_product(matrix: Matrix) -> Iterator:
    """Iterator of products value from matrix."""
    yield from (
        {_k: _v for e in mapped for _k, _v in e.items()}
        for mapped in product(
            *[[{k: v} for v in vs] for k, vs in matrix.items()]
        )
    )
