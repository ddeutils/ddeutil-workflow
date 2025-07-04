# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Reusable Components and Registry System.

This module provides a registry system for reusable workflow components including
tagged functions, template operations, and utility functions for parameter
processing and template rendering.

The registry system allows developers to create custom callable functions that
can be invoked from workflows using the CallStage, enabling extensible and
modular workflow design.

Classes:
    TagFunc: Tagged function wrapper for registry storage

Functions:
    tag: Decorator for registering callable functions
    param2template: Convert parameters to template format
    has_template: Check if string contains template variables
    not_in_template: Validate template restrictions
    extract_call: Extract callable information from registry
    create_model_from_caller: Generate Pydantic models from function signatures

Example:
    ```python
    from ddeutil.workflow.reusables import tag

    @tag("data-processing", alias="process-csv")
    def process_csv_file(input_path: str, output_path: str) -> dict:
        # Custom processing logic
        return {"status": "completed", "rows_processed": 1000}

    # Use in workflow YAML:
    # stages:
    #   - name: "Process data"
    #     uses: "data-processing/process-csv@latest"
    #     args:
    #       input_path: "/data/input.csv"
    #       output_path: "/data/output.csv"
    ```

Note:
    The registry system supports versioning and aliasing for better function
    management and backward compatibility.
"""
from __future__ import annotations

import copy
import inspect
import logging
from ast import Call, Constant, Expr, Module, Name, parse
from datetime import datetime
from functools import wraps
from importlib import import_module
from typing import (
    Annotated,
    Any,
    Callable,
    Literal,
    Optional,
    Protocol,
    TypeVar,
    Union,
    get_type_hints,
)

try:
    from typing import ParamSpec
except ImportError:
    from typing_extensions import ParamSpec

from ddeutil.core import getdot, import_string, lazy
from ddeutil.io import search_env_replace
from pydantic import BaseModel, ConfigDict, Field, create_model
from pydantic.alias_generators import to_pascal
from pydantic.dataclasses import dataclass

from .__types import DictData, Re
from .conf import dynamic
from .errors import UtilError

T = TypeVar("T")
P = ParamSpec("P")

# NOTE: Adjust logging level of the ``asyncio`` to INFO level.
logging.getLogger("asyncio").setLevel(logging.INFO)


FILTERS: dict[str, Callable] = {  # pragma: no cov
    "abs": abs,
    "str": str,
    "int": int,
    "list": list,
    "dict": dict,
    "title": lambda x: x.title(),
    "upper": lambda x: x.upper(),
    "lower": lambda x: x.lower(),
    "rstr": [str, repr],
    "keys": lambda x: x.keys(),
    "values": lambda x: x.values(),
}


class FilterFunc(Protocol):
    """Tag Function Protocol. This protocol that use to represent any callable
    object that able to access the filter attribute.
    """

    filter: str
    mark: Literal["filter"] = "filter"

    def __call__(self, *args, **kwargs): ...  # pragma: no cov


FilterRegistry = Union[FilterFunc, Callable[[...], Any]]


def custom_filter(name: str) -> Callable[P, FilterFunc]:
    """Custom filter decorator function that sets function attributes.

    This decorator sets the `filter` attribute for making filter registries variable.

    Args:
        name: A filter name for different use-cases of a function.

    Returns:
        Callable[P, FilterFunc]: Decorated function with filter attributes.
    """

    def func_internal(func: Callable[[...], Any]) -> FilterFunc:
        func.filter = name
        func.mark = "filter"

        @wraps(func)
        def wrapped(*args, **kwargs):
            # NOTE: Able to do anything before calling custom filter function.
            return func(*args, **kwargs)

        return wrapped

    return func_internal


def make_filter_registry(
    registers: Optional[list[str]] = None,
) -> dict[str, FilterRegistry]:
    """Return registries of all functions that can be called with tasks.

    Args:
        registers: Optional override list of registers.

    Returns:
        dict[str, FilterRegistry]: Dictionary mapping filter names to functions.
    """
    rs: dict[str, FilterRegistry] = {}
    for module in dynamic("registry_filter", f=registers):
        # NOTE: try to sequential import task functions
        try:
            importer = import_module(module)
        except ModuleNotFoundError:
            continue

        for fstr, func in inspect.getmembers(importer, inspect.isfunction):
            # NOTE: check function attribute that already set tag by
            #   ``utils.tag`` decorator.
            if not (
                hasattr(func, "filter")
                and str(getattr(func, "mark", "NOT SET")) == "filter"
            ):  # pragma: no cov
                continue

            func: FilterFunc

            rs[func.filter] = import_string(f"{module}.{fstr}")

    rs.update(FILTERS)
    return rs


def get_args_const(
    expr: str,
) -> tuple[str, list[Constant], dict[str, Constant]]:
    """Get arguments and keyword-arguments from function calling string.

    Args:
        expr: A string expression representing a function call.

    Returns:
        tuple[str, list[Constant], dict[str, Constant]]: Function name, args, and kwargs.

    Raises:
        UtilError: If the expression has syntax errors or invalid format.
    """
    try:
        mod: Module = parse(expr)
    except SyntaxError:
        raise UtilError(
            f"Post-filter: {expr} does not valid because it raise syntax error."
        ) from None

    body: list[Expr] = mod.body
    if len(body) > 1:
        raise UtilError(
            "Post-filter function should be only one calling per workflow."
        )

    caller: Union[Name, Call]
    if isinstance((caller := body[0].value), Name):
        return caller.id, [], {}
    elif not isinstance(caller, Call):
        raise UtilError(
            f"Get arguments does not support for caller type: {type(caller)}"
        )

    name: Name = caller.func
    args: list[Constant] = caller.args
    keywords: dict[str, Constant] = {k.arg: k.value for k in caller.keywords}

    if any(not isinstance(i, Constant) for i in args):
        raise UtilError(f"Argument of {expr} should be constant.")

    if any(not isinstance(i, Constant) for i in keywords.values()):
        raise UtilError(f"Keyword argument of {expr} should be constant.")

    return name.id, args, keywords


def get_args_from_filter(
    ft: str,
    filters: dict[str, FilterRegistry],
) -> tuple[str, FilterRegistry, list[Any], dict[Any, Any]]:  # pragma: no cov
    """Get arguments and keyword-arguments from filter function calling string.

    This function validates the filter function call with the filter functions mapping dict.

    Args:
        ft: Filter function calling string.
        filters: A mapping of filter registry.

    Returns:
        tuple[str, FilterRegistry, list[Any], dict[Any, Any]]: Function name, function, args, and kwargs.

    Raises:
        UtilError: If the filter function is not supported or has invalid arguments.
    """
    func_name, _args, _kwargs = get_args_const(ft)
    args: list[Any] = [arg.value for arg in _args]
    kwargs: dict[Any, Any] = {k: v.value for k, v in _kwargs.items()}

    if func_name not in filters:
        raise UtilError(f"The post-filter: {func_name!r} does not support yet.")

    if isinstance((f_func := filters[func_name]), list) and (args or kwargs):
        raise UtilError(
            "Chain filter function does not support for passing arguments."
        )

    return func_name, f_func, args, kwargs


def map_post_filter(
    value: T,
    post_filter: list[str],
    filters: dict[str, FilterRegistry],
) -> T:
    """Map post-filter functions to value with sequence of filter function names.

    Args:
        value: A value to map with filter functions.
        post_filter: A list of post-filter function names.
        filters: A mapping of filter registry.

    Returns:
        T: The value after applying all post-filter functions.

    Raises:
        UtilError: If a post-filter function fails or is incompatible with the value.
    """
    for ft in post_filter:
        func_name, f_func, args, kwargs = get_args_from_filter(ft, filters)
        try:
            if isinstance(f_func, list):
                for func in f_func:
                    value: T = func(value)
            else:
                value: T = f_func(value, *args, **kwargs)
        except UtilError:
            raise
        except Exception:
            raise UtilError(
                f"The post-filter: {func_name!r} does not fit with {value!r} "
                f"(type: {type(value).__name__})."
            ) from None
    return value


def not_in_template(value: Any, *, not_in: str = "matrix.") -> bool:
    """Check if value should not pass template with not_in value prefix.

    Args:
        value: A value to check for parameter template prefix.
        not_in: The not-in string to use in the `.startswith` function.
            Default is `matrix.`.

    Returns:
        bool: True if value should not pass template, False otherwise.
    """
    if isinstance(value, dict):
        return any(not_in_template(value[k], not_in=not_in) for k in value)
    elif isinstance(value, (list, tuple, set)):
        return any(not_in_template(i, not_in=not_in) for i in value)
    elif not isinstance(value, str):
        return False
    return any(
        (not found.caller.strip().startswith(not_in))
        for found in Re.finditer_caller(value.strip())
    )


def has_template(value: Any) -> bool:
    """Check if value includes templating string.

    Args:
        value: A value to check for parameter template.

    Returns:
        bool: True if value contains template variables, False otherwise.
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
    context: Optional[DictData] = None,
    filters: Optional[dict[str, FilterRegistry]] = None,
    registers: Optional[list[str]] = None,
) -> Optional[str]:
    """Pass parameters to template string using RE_CALLER regular expression.

    This is a sub-function that processes template strings. The getter value
    that maps a template should have typing support aligned with workflow
    parameter types: `str`, `int`, `datetime`, and `list`.

    Args:
        value: A string value to map with parameters.
        params: Parameter values to get with matched regular expression.
        context: Optional context data.
        filters: Optional mapping of filter registry.
        registers: Optional override list of registers.

    Returns:
        Optional[str]: The processed template string or None if value is "None".

    Raises:
        UtilError: If parameters cannot be retrieved or template processing fails.
    """
    filters: dict[str, FilterRegistry] = filters or make_filter_registry(
        registers=registers
    )

    # NOTE: remove space before and after this string value.
    value: str = value.strip()
    for found in Re.finditer_caller(value):
        # NOTE:
        #   Get caller and filter values that setting inside;
        #
        #   ... ``${{ <caller-value> [ | <filter-value>] ... }}``
        #
        caller: str = found.caller
        pfilter: list[str] = [
            i.strip()
            for i in (found.post_filters.strip().removeprefix("|").split("|"))
            if i != ""
        ]

        # NOTE: from validate step, it guarantees that caller exists in params.
        #   I recommend to avoid logging params context on this case because it
        #   can include secret value.
        try:
            getter: Any = getdot(caller, params | (context or {}))
        except ValueError:
            raise UtilError(
                f"Parameters does not get dot with caller: {caller!r}."
            ) from None

        # NOTE:
        #   If type of getter caller is not string type, and it does not use to
        #   concat other string value, it will return origin value from the
        #   ``getdot`` function.
        if value.replace(found.full, "", 1) == "":
            return map_post_filter(getter, pfilter, filters=filters)

        # NOTE: map post-filter function.
        getter: Any = map_post_filter(getter, pfilter, filters=filters)
        if not isinstance(getter, str):
            getter: str = str(getter)

        value: str = value.replace(found.full, getter, 1)

    if value == "None":
        return None

    return search_env_replace(value)


def param2template(
    value: T,
    params: DictData,
    context: Optional[DictData] = None,
    filters: Optional[dict[str, FilterRegistry]] = None,
    *,
    extras: Optional[DictData] = None,
) -> Any:
    """Pass parameters to template string using RE_CALLER regular expression.

    Args:
        value: A value to map with parameters.
        params: Parameter values to get with matched regular expression.
        context: Optional context data.
        filters: Optional filter mapping for use with `map_post_filter` function.
        extras: Optional override extras.

    Returns:
        Any: The processed value with template variables replaced.
    """
    registers: Optional[list[str]] = (
        extras.get("registry_filter") if extras else None
    )
    filters: dict[str, FilterRegistry] = filters or make_filter_registry(
        registers=registers
    )
    if isinstance(value, dict):
        return {
            k: param2template(value[k], params, context, filters, extras=extras)
            for k in value
        }
    elif isinstance(value, (list, tuple, set)):
        try:
            return type(value)(
                param2template(i, params, context, filters, extras=extras)
                for i in value
            )
        except TypeError:
            return value
    elif not isinstance(value, str):
        return value
    return str2template(
        value, params, context=context, filters=filters, registers=registers
    )


@custom_filter("fmt")  # pragma: no cov
def datetime_format(value: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime object to string with the specified format.

    Examples:
        >>> "${{ start-date | fmt('%Y%m%d') }}"
        >>> "${{ start-date | fmt }}"

    Args:
        value: A datetime value to format to string.
        fmt: A format string pattern to pass to the `dt.strftime` method.

    Returns:
        str: The formatted datetime string.

    Raises:
        UtilError: If the input value is not a datetime object.
    """
    if isinstance(value, datetime):
        return value.strftime(fmt)
    raise UtilError(
        "This custom function should pass input value with datetime type."
    )


@custom_filter("coalesce")  # pragma: no cov
def coalesce(value: Optional[T], default: Any) -> T:
    """Coalesce with default value if the main value is None.

    Examples:
        >>> "${{ value | coalesce('foo') }}"

    Args:
        value: A value to check for null.
        default: A default value to return if the input value is null.

    Returns:
        T: The original value if not None, otherwise the default value.
    """
    return default if value is None else value


@custom_filter("getitem")  # pragma: no cov
def get_item(
    value: DictData, key: Union[str, int], default: Optional[Any] = None
) -> Any:
    """Get a value with a specific key.

    Examples:
        >>> "${{ value | getitem('key') }}"
        >>> "${{ value | getitem('key', 'default') }}"

    Args:
        value: A dictionary to get the value from.
        key: The key to look up in the dictionary.
        default: Optional default value if key is not found.

    Returns:
        Any: The value associated with the key, or the default value.

    Raises:
        UtilError: If the value is not a dictionary.
    """
    if not isinstance(value, dict):
        raise UtilError(
            f"The value that pass to `getitem` filter should be `dict` not "
            f"`{type(value)}`."
        )
    return value.get(key, default)


@custom_filter("getindex")  # pragma: no cov
def get_index(value: list[Any], index: int) -> Any:
    """Get a value with a specific index.

    Examples:
        >>> "${{ value | getindex(1) }}"

    Args:
        value: A list to get the value from.
        index: The index to access in the list.

    Returns:
        Any: The value at the specified index.

    Raises:
        UtilError: If the value is not a list or if the index is out of range.
    """
    if not isinstance(value, list):
        raise UtilError(
            f"The value that pass to `getindex` filter should be `list` not "
            f"`{type(value)}`."
        )
    try:
        return value[index]
    except IndexError as e:
        raise UtilError(
            f"Index: {index} is out of range of value (The maximum range is "
            f"{len(value)})."
        ) from e


class TagFunc(Protocol):
    """Tag Function Protocol"""

    name: str
    tag: str
    mark: Literal["tag"] = "tag"

    def __call__(self, *args, **kwargs): ...  # pragma: no cov


ReturnTagFunc = Callable[P, TagFunc]
DecoratorTagFunc = Callable[[Callable[[...], Any]], ReturnTagFunc]


def tag(
    name: Optional[str] = None,
    alias: Optional[str] = None,
) -> DecoratorTagFunc:  # pragma: no cov
    """Tag decorator function that sets function attributes for registry.

    This decorator sets the `tag` and `name` attributes for making registries variable.

    Args:
        name: A tag name for different use-cases of a function.
            Uses 'latest' if not set.
        alias: An alias function name to keep in registries.
            Uses original function name from `__name__` if not supplied.

    Returns:
        DecoratorTagFunc: Decorated function with tag attributes.
    """

    def func_internal(func: Callable[[...], Any]) -> ReturnTagFunc:
        func.tag = name or "latest"
        func.name = alias or func.__name__.replace("_", "-")
        func.mark = "tag"

        @wraps(func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> TagFunc:
            """Wrapped function."""
            return func(*args, **kwargs)

        @wraps(func)
        async def async_wrapped(*args: P.args, **kwargs: P.kwargs) -> TagFunc:
            """Wrapped async function."""
            return await func(*args, **kwargs)

        return async_wrapped if inspect.iscoroutinefunction(func) else wrapped

    return func_internal


Registry = dict[str, Callable[[], TagFunc]]


def make_registry(
    submodule: str,
    *,
    registries: Optional[list[str]] = None,
) -> dict[str, Registry]:
    """Return registries of all functions that can be called with tasks.

    Args:
        submodule: A module prefix to import registry from.
        registries: Optional list of registries.

    Returns:
        dict[str, Registry]: Dictionary mapping function names to their registries.

    Raises:
        ValueError: If a tag already exists for a function name.
    """
    rs: dict[str, Registry] = {}
    regis_calls: list[str] = copy.deepcopy(
        dynamic("registry_caller", f=registries)
    )
    regis_calls.extend(["ddeutil.vendors"])
    for module in regis_calls:
        # NOTE: try to sequential import task functions
        try:
            importer = import_module(f"{module}.{submodule}")
        except ModuleNotFoundError:
            continue

        for fstr, func in inspect.getmembers(importer, inspect.isfunction):
            # NOTE: check function attribute that already set tag by
            #   ``utils.tag`` decorator.
            if not (
                hasattr(func, "tag")
                and hasattr(func, "name")
                and str(getattr(func, "mark", "NOTSET")) == "tag"
            ):  # pragma: no cov
                continue

            # NOTE: Define type of the func value.
            func: TagFunc

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


@dataclass(frozen=True)
class CallSearchData:
    """Call Search dataclass that use for receive regular expression grouping
    dict from searching call string value.
    """

    path: str
    func: str
    tag: str


def extract_call(
    call: str,
    *,
    registries: Optional[list[str]] = None,
) -> Callable[[], TagFunc]:
    """Extract call function from string value to call partial function at runtime.

    The format of call value should contain 3 regular expression groups
    which match with the below config format:

        >>> "^(?P<path>[^/@]+)/(?P<func>[^@]+)@(?P<tag>.+)$"

    Examples:
        >>> extract_call("tasks/el-postgres-to-delta@polars")
        ...
        >>> extract_call("tasks/return-type-not-valid@raise")
        ...

    Args:
        call: A call value that matches the Task regex.
        registries: Optional list of registries.

    Returns:
        Callable[[], TagFunc]: A callable function that can be executed.

    Raises:
        ValueError: If the call does not match the regex format.
        NotImplementedError: If the function or tag does not exist in the registry.
    """
    if not (found := Re.RE_TASK_FMT.search(call)):
        raise ValueError(
            f"Call {call!r} does not match with the call regex format."
        )

    call: CallSearchData = CallSearchData(**found.groupdict())
    rgt: dict[str, Registry] = make_registry(
        submodule=f"{call.path}", registries=registries
    )

    if call.func not in rgt:
        raise NotImplementedError(
            f"`REGISTERS.{call.path}.registries` not implement "
            f"registry: {call.func!r}."
        )

    if call.tag not in rgt[call.func]:
        raise NotImplementedError(
            f"tag: {call.tag!r} not found on registry func: "
            f"`REGISTER.{call.path}.registries.{call.func}`"
        )
    return rgt[call.func][call.tag]


class BaseCallerArgs(BaseModel):  # pragma: no cov
    """Base Caller Args model."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        use_enum_values=True,
    )


def create_model_from_caller(func: Callable) -> BaseModel:  # pragma: no cov
    """Create model from the caller function.

    This function is used to validate the caller function argument type hints
    that are valid with the args field.

    Reference:
        - https://github.com/lmmx/pydantic-function-models
        - https://docs.pydantic.dev/1.10/usage/models/#dynamic-model-creation

    Args:
        func: A caller function to create a model from.

    Returns:
        BaseModel: A Pydantic model created from the function signature.
    """
    sig: inspect.Signature = inspect.signature(func)
    type_hints: dict[str, Any] = get_type_hints(func)
    fields: dict[str, Any] = {}
    for name in sig.parameters:
        param: inspect.Parameter = sig.parameters[name]

        # NOTE: Skip all `*args` and `**kwargs` parameters.
        if param.kind in (
            inspect.Parameter.VAR_KEYWORD,
            inspect.Parameter.VAR_POSITIONAL,
        ):
            continue

        if name.startswith("_"):
            kwargs = {"serialization_alias": name}
            rename: str = name.removeprefix("_")
        else:
            kwargs = {}
            rename: str = name

        if param.default != inspect.Parameter.empty:
            fields[rename] = Annotated[
                type_hints[name],
                Field(default=param.default, **kwargs),
            ]
        else:
            fields[rename] = Annotated[
                type_hints[name],
                Field(..., **kwargs),
            ]

    return create_model(
        to_pascal(func.__name__),
        __base__=BaseCallerArgs,
        **fields,
    )
