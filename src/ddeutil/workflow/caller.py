# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
# [x] Use config
from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from functools import wraps
from importlib import import_module
from typing import Any, Callable, Optional, Protocol, TypeVar

try:
    from typing import ParamSpec
except ImportError:
    from typing_extensions import ParamSpec

from ddeutil.core import lazy

from .__types import Re
from .conf import config

T = TypeVar("T")
P = ParamSpec("P")

logger = logging.getLogger("ddeutil.workflow")
logging.getLogger("asyncio").setLevel(logging.INFO)


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

    :param: name: (str) A tag name for make different use-case of a function.
    :param: alias: (str) A alias function name that keeping in registries.
        If this value does not supply, it will use original function name
        from `__name__` argument.

    :rtype: Callable[P, TagFunc]
    """

    def func_internal(func: Callable[[...], Any]) -> ReturnTagFunc:
        func.tag = name
        func.name = alias or func.__name__.replace("_", "-")

        @wraps(func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> TagFunc:
            return func(*args, **kwargs)

        @wraps(func)
        async def awrapped(*args: P.args, **kwargs: P.kwargs) -> TagFunc:
            return await func(*args, **kwargs)

        return awrapped if inspect.iscoroutinefunction(func) else wrapped

    return func_internal


Registry = dict[str, Callable[[], TagFunc]]


def make_registry(
    submodule: str,
    registries: Optional[list[str]] = None,
) -> dict[str, Registry]:
    """Return registries of all functions that able to called with task.

    :param submodule: (str) A module prefix that want to import registry.
    :param registries: (Optional[list[str]]) A list of registry.

    :rtype: dict[str, Registry]
    """
    rs: dict[str, Registry] = {}
    regis_calls: list[str] = registries or config.regis_call  # pragma: no cov
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
                hasattr(func, "tag") and hasattr(func, "name")
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
    registries: Optional[list[str]] = None,
) -> Callable[[], TagFunc]:
    """Extract Call function from string value to call partial function that
    does run it at runtime.

    :param call: (str) A call value that able to match with Task regex.
    :param registries: (Optional[list[str]]) A list of registry.

        The format of call value should contain 3 regular expression groups
    which match with the below config format:

        >>> "^(?P<path>[^/@]+)/(?P<func>[^@]+)@(?P<tag>.+)$"

    Examples:
        >>> extract_call("tasks/el-postgres-to-delta@polars")
        ...
        >>> extract_call("tasks/return-type-not-valid@raise")
        ...

    :raise NotImplementedError: When the searching call's function result does
        not exist in the registry.
    :raise NotImplementedError: When the searching call's tag result does not
        exist in the registry with its function key.

    :rtype: Callable[[], TagFunc]
    """
    if not (found := Re.RE_TASK_FMT.search(call)):
        raise ValueError(
            f"Call {call!r} does not match with the call regex format."
        )

    # NOTE: Pass the searching call string to `path`, `func`, and `tag`.
    call: CallSearchData = CallSearchData(**found.groupdict())

    # NOTE: Registry object should implement on this package only.
    rgt: dict[str, Registry] = make_registry(
        submodule=f"{call.path}",
        registries=registries,
    )
    if call.func not in rgt:
        raise NotImplementedError(
            f"`REGISTER-MODULES.{call.path}.registries` does not "
            f"implement registry: {call.func!r}."
        )

    if call.tag not in rgt[call.func]:
        raise NotImplementedError(
            f"tag: {call.tag!r} does not found on registry func: "
            f"`REGISTER-MODULES.{call.path}.registries.{call.func}`"
        )
    return rgt[call.func][call.tag]
