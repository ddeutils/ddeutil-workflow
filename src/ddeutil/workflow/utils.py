# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import inspect
import logging
import stat
import time
from ast import Call, Constant, Expr, Module, Name, parse
from collections.abc import Iterator
from datetime import datetime, timedelta
from functools import wraps
from hashlib import md5
from importlib import import_module
from inspect import isfunction
from itertools import chain, islice, product
from pathlib import Path
from random import randrange
from typing import Any, Callable, Protocol, TypeVar, Union
from zoneinfo import ZoneInfo

try:
    from typing import ParamSpec
except ImportError:
    from typing_extensions import ParamSpec

from ddeutil.core import getdot, hasdot, hash_str, import_string, lazy
from ddeutil.io import search_env_replace
from pydantic import BaseModel

from .__types import DictData, Matrix, Re
from .conf import config
from .exceptions import UtilException

T = TypeVar("T")
P = ParamSpec("P")
AnyModel = TypeVar("AnyModel", bound=BaseModel)
AnyModelType = type[AnyModel]

logger = logging.getLogger("ddeutil.workflow")


def get_dt_now(
    tz: ZoneInfo | None = None, offset: float = 0.0
) -> datetime:  # pragma: no cov
    """Return the current datetime object.

    :param tz:
    :param offset:
    :return: The current datetime object that use an input timezone or UTC.
    """
    return datetime.now(tz=(tz or ZoneInfo("UTC"))) - timedelta(seconds=offset)


def get_diff_sec(
    dt: datetime, tz: ZoneInfo | None = None, offset: float = 0.0
) -> int:  # pragma: no cov
    """Return second value that come from diff of an input datetime and the
    current datetime with specific timezone.

    :param dt:
    :param tz:
    :param offset:
    """
    return round(
        (
            dt
            - datetime.now(tz=(tz or ZoneInfo("UTC")))
            - timedelta(seconds=offset)
        ).total_seconds()
    )


def wait_a_minute(now: datetime, second: float = 2) -> None:  # pragma: no cov
    """Wait with sleep to the next minute with an offset second value."""
    future = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    time.sleep((future - now).total_seconds() + second)


def delay(second: float = 0) -> None:  # pragma: no cov
    """Delay time that use time.sleep with random second value between
    0.00 - 0.99 seconds.

    :param second: A second number that want to adds-on random value.
    """
    time.sleep(second + randrange(0, 99, step=10) / 100)


def gen_id(
    value: Any,
    *,
    sensitive: bool = True,
    unique: bool = False,
) -> str:
    """Generate running ID for able to tracking. This generate process use `md5`
    algorithm function if ``WORKFLOW_CORE_WORKFLOW_ID_SIMPLE_MODE`` set to
    false. But it will cut this hashing value length to 10 it the setting value
    set to true.

    :param value: A value that want to add to prefix before hashing with md5.
    :param sensitive: A flag that convert the value to lower case before hashing
    :param unique: A flag that add timestamp at microsecond level to value
        before hashing.
    :rtype: str
    """
    if not isinstance(value, str):
        value: str = str(value)

    if config.gen_id_simple_mode:
        return hash_str(f"{(value if sensitive else value.lower())}", n=10) + (
            f"{datetime.now(tz=config.tz):%Y%m%d%H%M%S%f}" if unique else ""
        )
    return md5(
        (
            f"{(value if sensitive else value.lower())}"
            + (f"{datetime.now(tz=config.tz):%Y%m%d%H%M%S%f}" if unique else "")
        ).encode()
    ).hexdigest()


class TagFunc(Protocol):
    """Tag Function Protocol"""

    name: str
    tag: str

    def __call__(self, *args, **kwargs): ...  # pragma: no cov


ReturnTagFunc = Callable[P, TagFunc]
DecoratorTagFunc = Callable[[Callable[[...], Any]], ReturnTagFunc]


def tag(
    name: str, alias: str | None = None
) -> DecoratorTagFunc:  # pragma: no cov
    """Tag decorator function that set function attributes, ``tag`` and ``name``
    for making registries variable.

    :param: name: A tag name for make different use-case of a function.
    :param: alias: A alias function name that keeping in registries. If this
        value does not supply, it will use original function name from __name__.
    :rtype: Callable[P, TagFunc]
    """

    def func_internal(func: Callable[[...], Any]) -> ReturnTagFunc:
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
    for module in config.regis_hook:
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


def make_exec(path: str | Path) -> None:
    """Change mode of file to be executable file.

    :param path: A file path that want to make executable permission.
    """
    f: Path = Path(path) if isinstance(path, str) else path
    f.chmod(f.stat().st_mode | stat.S_IEXEC)


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
    object that able to access the name attribute.
    """

    name: str

    def __call__(self, *args, **kwargs): ...  # pragma: no cov


def custom_filter(name: str) -> Callable[P, FilterFunc]:
    """Custom filter decorator function that set function attributes, ``filter``
    for making filter registries variable.

    :param: name: A filter name for make different use-case of a function.
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


FilterRegistry = Union[FilterFunc, Callable[[...], Any]]


def make_filter_registry() -> dict[str, FilterRegistry]:
    """Return registries of all functions that able to called with task.

    :rtype: dict[str, Registry]
    """
    rs: dict[str, Registry] = {}
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

            rs[func.filter] = import_string(f"{module}.{fstr}")

    rs.update(FILTERS)
    return rs


def get_args_const(
    expr: str,
) -> tuple[str, list[Constant], dict[str, Constant]]:
    """Get arguments and keyword-arguments from function calling string.

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


@custom_filter("fmt")  # pragma: no cov
def datetime_format(value: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime object to string with the format.

    :param value: A datetime value that want to format to string value.
    :param fmt: A format string pattern that passing to the `dt.strftime`
        method.

    :rtype: str
    """
    if isinstance(value, datetime):
        return value.strftime(fmt)
    raise UtilException(
        "This custom function should pass input value with datetime type."
    )


def map_post_filter(
    value: T,
    post_filter: list[str],
    filters: dict[str, FilterRegistry],
) -> T:
    """Mapping post-filter to value with sequence list of filter function name
    that will get from the filter registry.

    :param value: A string value that want to mapped with filter function.
    :param post_filter: A list of post-filter function name.
    :param filters: A filter registry.

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
                f"The post-filter function: {func_name} does not fit with "
                f"{value} (type: {type(value).__name__})."
            ) from None
    return value


def not_in_template(value: Any, *, not_in: str = "matrix.") -> bool:
    """Check value should not pass template with not_in value prefix.

    :param value: A value that want to find parameter template prefix.
    :param not_in: The not in string that use in the `.startswith` function.
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
) -> Any:
    """(Sub-function) Pass param to template string that can search by
    ``RE_CALLER`` regular expression.

        The getter value that map a template should have typing support align
    with the workflow parameter types that is `str`, `int`, `datetime`, and
    `list`.

    :param value: A string value that want to mapped with an params
    :param params: A parameter value that getting with matched regular
        expression.
    :param filters:
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
        if not hasdot(caller, params):
            raise UtilException(f"The params does not set caller: {caller!r}.")

        # NOTE: from validate step, it guarantee that caller exists in params.
        getter: Any = getdot(caller, params)

        # NOTE:
        #   If type of getter caller is not string type and it does not use to
        #   concat other string value, it will return origin value from the
        #   ``getdot`` function.
        if value.replace(found.full, "", 1) == "":
            return map_post_filter(getter, pfilter, filters=filters)

        # NOTE: map post-filter function.
        getter: Any = map_post_filter(getter, pfilter, filters=filters)
        if not isinstance(getter, str):
            getter: str = str(getter)

        value: str = value.replace(found.full, getter, 1)

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
    """Filter out an own created function of any value of mapping context by
    replacing it to its function name. If it is built-in function, it does not
    have any changing.

    :param value: A value context data that want to filter out function value.
    :type: The same type of an input ``value``.
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
    """Change key name that has dash to underscore.

    :rtype: DictData
    """
    if key in values:
        values[(fixed or key.replace("-", "_"))] = values.pop(key)
    return values


def cross_product(matrix: Matrix) -> Iterator[DictData]:
    """Iterator of products value from matrix.

    :rtype: Iterator[DictData]
    """
    yield from (
        {_k: _v for e in mapped for _k, _v in e.items()}
        for mapped in product(
            *[[{k: v} for v in vs] for k, vs in matrix.items()]
        )
    )


def batch(iterable: Iterator[Any], n: int) -> Iterator[Any]:
    """Batch data into iterators of length n. The last batch may be shorter.

    Example:
        >>> for b in batch('ABCDEFG', 3):
        ...     print(list(b))
        ['A', 'B', 'C']
        ['D', 'E', 'F']
        ['G']
    """
    if n < 1:
        raise ValueError("n must be at least one")

    it: Iterator[Any] = iter(iterable)
    while True:
        chunk_it = islice(it, n)
        try:
            first_el = next(chunk_it)
        except StopIteration:
            return
        yield chain((first_el,), chunk_it)


def cut_id(run_id: str, *, num: int = 6):
    """Cutting running ID with length.

    Example:
        >>> cut_id(run_id='668931127320241228100331254567')
        '254567'

    :param run_id:
    :param num:
    :return:
    """
    return run_id[-num:]
