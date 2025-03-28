# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import inspect
import logging
from ast import Call, Constant, Expr, Module, Name, parse
from datetime import datetime
from functools import wraps
from importlib import import_module
from typing import Any, Callable, Protocol, TypeVar, Union

try:
    from typing import ParamSpec
except ImportError:
    from typing_extensions import ParamSpec

from ddeutil.core import getdot, import_string
from ddeutil.io import search_env_replace

from .__types import DictData, Re
from .conf import config
from .exceptions import UtilException

T = TypeVar("T")
P = ParamSpec("P")

logger = logging.getLogger("ddeutil.workflow")


FILTERS: dict[str, callable] = {  # pragma: no cov
    "abs": abs,
    "str": str,
    "int": int,
    "title": lambda x: x.title(),
    "upper": lambda x: x.upper(),
    "lower": lambda x: x.lower(),
    "rstr": [str, repr],
}


class FilterFunc(Protocol):
    """Tag Function Protocol. This protocol that use to represent any callable
    object that able to access the filter attribute.
    """

    filter: str

    def __call__(self, *args, **kwargs): ...  # pragma: no cov


FilterRegistry = Union[FilterFunc, Callable[[...], Any]]


def custom_filter(name: str) -> Callable[P, FilterFunc]:
    """Custom filter decorator function that set function attributes, ``filter``
    for making filter registries variable.

    :param: name: (str) A filter name for make different use-case of a function.

    :rtype: Callable[P, FilterFunc]
    """

    def func_internal(func: Callable[[...], Any]) -> FilterFunc:
        func.filter = name

        @wraps(func)
        def wrapped(*args, **kwargs):
            # NOTE: Able to do anything before calling custom filter function.
            return func(*args, **kwargs)

        return wrapped

    return func_internal


def make_filter_registry() -> dict[str, FilterRegistry]:
    """Return registries of all functions that able to called with task.

    :rtype: dict[str, FilterRegistry]
    """
    rs: dict[str, FilterRegistry] = {}
    for module in config.regis_filter:
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

            func: FilterFunc

            rs[func.filter] = import_string(f"{module}.{fstr}")

    rs.update(FILTERS)
    return rs


def get_args_const(
    expr: str,
) -> tuple[str, list[Constant], dict[str, Constant]]:
    """Get arguments and keyword-arguments from function calling string.

    :param expr: (str) An expr string value.

    :rtype: tuple[str, list[Constant], dict[str, Constant]]
    """
    try:
        mod: Module = parse(expr)
    except SyntaxError:
        raise UtilException(
            f"Post-filter: {expr} does not valid because it raise syntax error."
        ) from None

    body: list[Expr] = mod.body
    if len(body) > 1:
        raise UtilException(
            "Post-filter function should be only one calling per workflow."
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
        raise UtilException(f"Argument of {expr} should be constant.")

    if any(not isinstance(i, Constant) for i in keywords.values()):
        raise UtilException(f"Keyword argument of {expr} should be constant.")

    return name.id, args, keywords


def get_args_from_filter(
    ft: str,
    filters: dict[str, FilterRegistry],
) -> tuple[str, FilterRegistry, list[Any], dict[Any, Any]]:  # pragma: no cov
    """Get arguments and keyword-arguments from filter function calling string.
    and validate it with the filter functions mapping dict.

    :param ft:
    :param filters: A mapping of filter registry.

    :rtype: tuple[str, FilterRegistry, list[Any], dict[Any, Any]]
    """
    func_name, _args, _kwargs = get_args_const(ft)
    args: list[Any] = [arg.value for arg in _args]
    kwargs: dict[Any, Any] = {k: v.value for k, v in _kwargs.items()}

    if func_name not in filters:
        raise UtilException(
            f"The post-filter: {func_name!r} does not support yet."
        )

    if isinstance((f_func := filters[func_name]), list) and (args or kwargs):
        raise UtilException(
            "Chain filter function does not support for passing arguments."
        )

    return func_name, f_func, args, kwargs


def map_post_filter(
    value: T,
    post_filter: list[str],
    filters: dict[str, FilterRegistry],
) -> T:
    """Mapping post-filter to value with sequence list of filter function name
    that will get from the filter registry.

    :param value: A string value that want to map with filter function.
    :param post_filter: A list of post-filter function name.
    :param filters: A mapping of filter registry.

    :rtype: T
    """
    for ft in post_filter:
        func_name, f_func, args, kwargs = get_args_from_filter(ft, filters)
        try:
            if isinstance(f_func, list):
                for func in f_func:
                    value: T = func(value)
            else:
                value: T = f_func(value, *args, **kwargs)
        except UtilException as err:
            logger.warning(str(err))
            raise
        except Exception as err:
            logger.warning(str(err))
            raise UtilException(
                f"The post-filter: {func_name!r} does not fit with {value!r} "
                f"(type: {type(value).__name__})."
            ) from None
    return value


def not_in_template(value: Any, *, not_in: str = "matrix.") -> bool:
    """Check value should not pass template with not_in value prefix.

    :param value: A value that want to find parameter template prefix.
    :param not_in: The not-in string that use in the `.startswith` function.

    :rtype: bool
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
    """Check value include templating string.

    :param value: A value that want to find parameter template.

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
) -> str:
    """(Sub-function) Pass param to template string that can search by
    ``RE_CALLER`` regular expression.

        The getter value that map a template should have typing support align
    with the workflow parameter types that is `str`, `int`, `datetime`, and
    `list`.

    :param value: (str) A string value that want to map with params.
    :param params: (DictData) A parameter value that getting with matched
        regular expression.
    :param filters: A mapping of filter registry.

    :rtype: str
    """
    filters: dict[str, FilterRegistry] = filters or make_filter_registry()

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
        try:
            getter: Any = getdot(caller, params)
        except ValueError as err:
            raise UtilException(
                f"Params does not set caller: {caller!r}."
            ) from err

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
    filters: dict[str, FilterRegistry] | None = None,
) -> T:
    """Pass param to template string that can search by ``RE_CALLER`` regular
    expression.

    :param value: A value that want to map with params
    :param params: A parameter value that getting with matched regular
        expression.
    :param filters: A filter mapping for mapping with `map_post_filter` func.

    :rtype: T
    :returns: An any getter value from the params input.
    """
    filters: dict[str, FilterRegistry] = filters or make_filter_registry()
    if isinstance(value, dict):
        return {k: param2template(value[k], params, filters) for k in value}
    elif isinstance(value, (list, tuple, set)):
        return type(value)([param2template(i, params, filters) for i in value])
    elif not isinstance(value, str):
        return value
    return str2template(value, params, filters=filters)


@custom_filter("fmt")  # pragma: no cov
def datetime_format(value: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime object to string with the format.

    :param value: (datetime) A datetime value that want to format to string
        value.
    :param fmt: (str) A format string pattern that passing to the `dt.strftime`
        method.

    :rtype: str
    """
    if isinstance(value, datetime):
        return value.strftime(fmt)
    raise UtilException(
        "This custom function should pass input value with datetime type."
    )


@custom_filter("coalesce")  # pragma: no cov
def coalesce(value: T | None, default: Any) -> T:
    """Coalesce with default value if the main value is None."""
    return default if value is None else value
