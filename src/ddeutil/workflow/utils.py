# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import inspect
import logging
import os
import stat
from abc import ABC, abstractmethod
from ast import Call, Constant, Expr, Module, Name, parse
from collections.abc import Iterator
from datetime import date, datetime
from functools import partial, wraps
from hashlib import md5
from importlib import import_module
from inspect import isfunction
from itertools import product
from pathlib import Path
from typing import Any, Callable, Literal, Optional, Protocol, Union
from zoneinfo import ZoneInfo

try:
    from typing import ParamSpec
except ImportError:
    from typing_extensions import ParamSpec

from ddeutil.core import getdot, hasdot, hash_str, import_string, lazy, str2bool
from ddeutil.io import PathData, search_env_replace
from ddeutil.io.models.lineage import dt_now
from pydantic import BaseModel, ConfigDict, Field
from pydantic.functional_validators import model_validator
from typing_extensions import Self

from .__types import DictData, Matrix, Re
from .exceptions import ParamValueException, UtilException

P = ParamSpec("P")


def get_diff_sec(dt: datetime, tz: ZoneInfo | None = None) -> int:
    """Return second value that come from diff of an input datetime and the
    current datetime with specific timezone.
    """
    return round(
        (dt - datetime.now(tz=(tz or ZoneInfo("UTC")))).total_seconds()
    )


class Engine(BaseModel):
    """Engine Model"""

    paths: PathData = Field(default_factory=PathData)
    registry: list[str] = Field(
        default_factory=lambda: ["ddeutil.workflow"],  # pragma: no cover
    )
    registry_filter: list[str] = Field(
        default_factory=lambda: ["ddeutil.workflow.utils"],  # pragma: no cover
    )

    @model_validator(mode="before")
    def __prepare_registry(cls, values: DictData) -> DictData:
        """Prepare registry value that passing with string type. It convert the
        string type to list of string.
        """
        if (_regis := values.get("registry")) and isinstance(_regis, str):
            values["registry"] = [_regis]
        if (_regis_filter := values.get("registry_filter")) and isinstance(
            _regis, str
        ):
            values["registry_filter"] = [_regis_filter]
        return values


class CoreConf(BaseModel):
    """Core Config Model"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tz: ZoneInfo = Field(default_factory=lambda: ZoneInfo("UTC"))


class ConfParams(BaseModel):
    """Params Model"""

    engine: Engine = Field(
        default_factory=Engine,
        description="A engine mapping values.",
    )
    core: CoreConf = Field(
        default_factory=CoreConf,
        description="A core config value",
    )


def config() -> ConfParams:
    """Load Config data from ``workflows-conf.yaml`` file.

    Configuration Docs:
    ---
    :var engine.registry:
    :var engine.registry_filter:
    :var paths.root:
    :var paths.conf:
    """
    root_path: str = os.getenv("WORKFLOW_ROOT_PATH", ".")

    regis: list[str] = ["ddeutil.workflow"]
    if regis_env := os.getenv("WORKFLOW_CORE_REGISTRY"):
        regis = [r.strip() for r in regis_env.split(",")]

    regis_filter: list[str] = ["ddeutil.workflow.utils"]
    if regis_filter_env := os.getenv("WORKFLOW_CORE_REGISTRY_FILTER"):
        regis_filter = [r.strip() for r in regis_filter_env.split(",")]

    conf_path: str = (
        f"{root_path}/{conf_env}"
        if (conf_env := os.getenv("WORKFLOW_CORE_PATH_CONF"))
        else None
    )
    return ConfParams.model_validate(
        obj={
            "engine": {
                "registry": regis,
                "registry_filter": regis_filter,
                "paths": {
                    "root": root_path,
                    "conf": conf_path,
                },
            },
        }
    )


def gen_id(
    value: Any,
    *,
    sensitive: bool = True,
    unique: bool = False,
) -> str:
    """Generate running ID for able to tracking. This generate process use `md5`
    algorithm function if ``WORKFLOW_CORE_PIPELINE_ID_SIMPLE`` set to false.
    But it will cut this hashing value length to 10 it the setting value set to
    true.

    :param value: A value that want to add to prefix before hashing with md5.
    :param sensitive: A flag that convert the value to lower case before hashing
    :param unique: A flag that add timestamp at microsecond level to value
        before hashing.
    :rtype: str
    """
    if not isinstance(value, str):
        value: str = str(value)

    tz: ZoneInfo = ZoneInfo(os.getenv("WORKFLOW_CORE_TIMEZONE", "UTC"))
    if str2bool(os.getenv("WORKFLOW_CORE_PIPELINE_ID_SIMPLE", "true")):
        return hash_str(f"{(value if sensitive else value.lower())}", n=10) + (
            f"{datetime.now(tz=tz):%Y%m%d%H%M%S%f}" if unique else ""
        )
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
        raise NotImplementedError(
            "Receive value and validate typing before return valid value."
        )


class DefaultParam(BaseParam):
    """Default Parameter that will check default if it required"""

    default: Optional[str] = None

    @abstractmethod
    def receive(self, value: Optional[Any] = None) -> Any:
        raise NotImplementedError(
            "Receive value and validate typing before return valid value."
        )

    @model_validator(mode="after")
    def __check_default(self) -> Self:
        """Check default value should pass when it set required."""
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
        """Receive value that match with datetime. If a input value pass with
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
        return datetime.fromisoformat(value)


class StrParam(DefaultParam):
    """String parameter."""

    type: Literal["str"] = "str"

    def receive(self, value: Optional[str] = None) -> str | None:
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

    def receive(self, value: Optional[int] = None) -> int | None:
        """Receive value that match with int.

        :param value: A value that want to validate with integer parameter type.
        :rtype: int | None
        """
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
    """Choice parameter."""

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
    IntParam,
    StrParam,
]


class Context(BaseModel):
    """Context Pydantic Model that use to passing context data between workflow
    objects such as Pipeline, Job, and Stage.
    """

    params: dict = Field(default_factory=dict)
    jobs: dict = Field(default_factory=dict)
    error: dict = Field(default_factory=dict)


class Result(BaseModel):
    """Result Pydantic Model for passing parameter and receiving output from
    the pipeline execution.
    """

    status: int = Field(default=2)
    context: DictData = Field(default_factory=dict)

    # NOTE: Ignore this field to compare another result model with __eq__.
    run_id: str = Field(
        default_factory=partial(gen_id, "manual", unique=True),
        repr=False,
    )

    def receive(self, result: Result) -> Result:
        self.__dict__["status"] = result.status
        self.__dict__["context"].update(result.context)
        return self

    def receive_jobs(self, result: Result) -> Result:
        self.__dict__["status"] = result.status
        if "jobs" not in self.__dict__["context"]:
            self.__dict__["context"]["jobs"] = {}
        self.__dict__["context"]["jobs"].update(result.context)
        return self


class ReContext(BaseModel):
    """Context Pydantic Model"""

    params: dict = Field(default_factory=dict)
    jobs: dict = Field(default_factory=dict)
    error: dict = Field(default_factory=dict)


class ReResult(BaseModel):
    """Result Pydantic Model for passing parameter and receiving output from
    the pipeline execution.
    """

    # TODO: Add running ID to this result dataclass.
    # ---
    # parent_run_id: str
    # run_id: str
    #
    status: int = Field(default=2)
    context: ReContext = Field(default_factory=Context)

    def receive(self, result: ReResult) -> ReResult:
        self.__dict__["status"] = result.status
        self.__dict__["context"].__dict__["jobs"].update(result.context.jobs)
        self.__dict__["context"].__dict__["error"].update(result.context.error)
        return self


def make_exec(path: str | Path):
    """Change mode of file to be executable file."""
    f: Path = Path(path) if isinstance(path, str) else path
    f.chmod(f.stat().st_mode | stat.S_IEXEC)


FILTERS: dict[str, callable] = {
    "abs": abs,
    "str": str,
    "int": int,
    "upper": lambda x: x.upper(),
    "lower": lambda x: x.lower(),
    "rstr": [str, repr],
}


class FilterFunc(Protocol):
    """Tag Function Protocol"""

    name: str

    def __call__(self, *args, **kwargs): ...


def custom_filter(name: str) -> Callable[P, TagFunc]:
    """Custom filter decorator function that set function attributes, ``filter``
    for making filter registries variable.

    :param: name: A filter name for make different use-case of a function.
    """

    def func_internal(func: Callable[[...], Any]) -> TagFunc:
        func.filter = name

        @wraps(func)
        def wrapped(*args, **kwargs):
            # NOTE: Able to do anything before calling custom filter function.
            return func(*args, **kwargs)

        return wrapped

    return func_internal


FilterRegistry = Union[FilterFunc, Callable[[...], Any]]


def make_filter_registry() -> dict[str, FilterRegistry]:
    """Return registries of all functions that able to called with task.

    :rtype: dict[str, Registry]
    """
    rs: dict[str, Registry] = {}
    for module in config().engine.registry_filter:
        # NOTE: try to sequential import task functions
        try:
            importer = import_module(module)
        except ModuleNotFoundError:
            continue

        for fstr, func in inspect.getmembers(importer, inspect.isfunction):
            # NOTE: check function attribute that already set tag by
            #   ``utils.tag`` decorator.
            if not hasattr(func, "filter"):
                continue

            rs[func.filter] = import_string(f"{module}.{fstr}")

    rs.update(FILTERS)
    return rs


def get_args_const(
    expr: str,
) -> tuple[str, list[Constant], dict[str, Constant]]:
    """Get arguments and keyword-arguments from function calling string."""
    try:
        mod: Module = parse(expr)
    except SyntaxError:
        raise UtilException(
            f"Post-filter: {expr} does not valid because it raise syntax error."
        ) from None
    body: list[Expr] = mod.body

    if len(body) > 1:
        raise UtilException(
            "Post-filter function should be only one calling per pipe"
        )

    caller: Union[Name, Call]
    if isinstance((caller := body[0].value), Name):
        return caller.id, [], {}
    elif not isinstance(caller, Call):
        raise UtilException(
            f"Get arguments does not support for caller type: {type(caller)}"
        )

    name: Name = caller.func
    args: list[Constant] = caller.args
    keywords: dict[str, Constant] = {k.arg: k.value for k in caller.keywords}

    if any(not isinstance(i, Constant) for i in args):
        raise UtilException("Argument should be constant.")

    return name.id, args, keywords


@custom_filter("fmt")
def datetime_format(value: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    if isinstance(value, datetime):
        return value.strftime(fmt)
    raise UtilException(
        "This custom function should pass input value with datetime type."
    )


def map_post_filter(
    value: Any,
    post_filter: list[str],
    filters: dict[str, FilterRegistry],
) -> Any:
    """Mapping post-filter to value with sequence list of filter function name
    that will get from the filter registry.

    :param value: A string value that want to mapped with filter function.
    :param post_filter: A list of post-filter function name.
    :param filters: A filter registry.
    """
    for _filter in post_filter:
        func_name, _args, _kwargs = get_args_const(_filter)
        args = [arg.value for arg in _args]
        kwargs = {k: v.value for k, v in _kwargs.items()}

        if func_name not in filters:
            raise UtilException(
                f"The post-filter: {func_name} does not support yet."
            )

        try:
            if isinstance((f_func := filters[func_name]), list):
                if args or kwargs:
                    raise UtilException(
                        "Chain filter function does not support for passing "
                        "arguments."
                    )
                for func in f_func:
                    value: Any = func(value)
            else:
                value: Any = f_func(value, *args, **kwargs)
        except Exception as err:
            logging.warning(str(err))
            raise UtilException(
                f"The post-filter function: {func_name} does not fit with "
                f"{value} (type: {type(value).__name__})."
            ) from None
    return value


def not_in_template(value: Any, *, not_in: str = "matrix.") -> bool:
    """Check value should not pass template with not_in value prefix.

    :param value:
    :param not_in:
    :rtype: bool
    """
    if isinstance(value, dict):
        return any(not_in_template(value[k], not_in=not_in) for k in value)
    elif isinstance(value, (list, tuple, set)):
        return any(not_in_template(i, not_in=not_in) for i in value)
    elif not isinstance(value, str):
        return False
    return any(
        (not found.group("caller").strip().startswith(not_in))
        for found in Re.RE_CALLER.finditer(value.strip())
    )


def has_template(value: Any) -> bool:
    """Check value include templating string.

    :param value:
    :rtype: bool
    """
    if isinstance(value, dict):
        return any(has_template(value[k]) for k in value)
    elif isinstance(value, (list, tuple, set)):
        return any(has_template(i) for i in value)
    elif not isinstance(value, str):
        return False
    return bool(Re.RE_CALLER.findall(value.strip()))


def str2template(
    value: str,
    params: DictData,
    *,
    filters: dict[str, FilterRegistry] | None = None,
) -> Any:
    """(Sub-function) Pass param to template string that can search by
    ``RE_CALLER`` regular expression.

        The getter value that map a template should have typing support align
    with the pipeline parameter types that is `str`, `int`, `datetime`, and
    `list`.

    :param value: A string value that want to mapped with an params
    :param params: A parameter value that getting with matched regular
        expression.
    :param filters:
    """
    filters: dict[str, FilterRegistry] = filters or make_filter_registry()

    # NOTE: remove space before and after this string value.
    value: str = value.strip()
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

        # NOTE: from validate step, it guarantee that caller exists in params.
        getter: Any = getdot(caller, params)

        # NOTE:
        #   If type of getter caller is not string type and it does not use to
        #   concat other string value, it will return origin value from the
        #   ``getdot`` function.
        if value.replace(found.group(0), "", 1) == "":
            return map_post_filter(getter, pfilter, filters=filters)

        # NOTE: map post-filter function.
        getter: Any = map_post_filter(getter, pfilter, filters=filters)
        if not isinstance(getter, str):
            getter: str = str(getter)

        value: str = value.replace(found.group(0), getter, 1)

    return search_env_replace(value)


def param2template(
    value: Any,
    params: DictData,
) -> Any:
    """Pass param to template string that can search by ``RE_CALLER`` regular
    expression.

    :param value: A value that want to mapped with an params
    :param params: A parameter value that getting with matched regular
        expression.

    :rtype: Any
    :returns: An any getter value from the params input.
    """
    filters: dict[str, FilterRegistry] = make_filter_registry()
    if isinstance(value, dict):
        return {k: param2template(value[k], params) for k in value}
    elif isinstance(value, (list, tuple, set)):
        return type(value)([param2template(i, params) for i in value])
    elif not isinstance(value, str):
        return value
    return str2template(value, params, filters=filters)


def filter_func(value: Any) -> Any:
    """Filter own created function out of any value with replace it to its
    function name. If it is built-in function, it does not have any changing.
    """
    if isinstance(value, dict):
        return {k: filter_func(value[k]) for k in value}
    elif isinstance(value, (list, tuple, set)):
        return type(value)([filter_func(i) for i in value])

    if isfunction(value):
        # NOTE: If it want to improve to get this function, it able to save to
        #   some global memory storage.
        #   ---
        #   >>> GLOBAL_DICT[value.__name__] = value
        #
        return value.__name__
    return value


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


def cross_product(matrix: Matrix) -> Iterator[DictData]:
    """Iterator of products value from matrix."""
    yield from (
        {_k: _v for e in mapped for _k, _v in e.items()}
        for mapped in product(
            *[[{k: v} for v in vs] for k, vs in matrix.items()]
        )
    )
