# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from functools import wraps
from importlib import import_module
from typing import Any, Callable, Protocol, TypeVar

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


@dataclass(frozen=True)
class HookSearchData:
    """Hook Search dataclass that use for receive regular expression grouping
    dict from searching hook string value.
    """

    path: str
    func: str
    tag: str


def extract_hook(hook: str) -> Callable[[], TagFunc]:
    """Extract Hook function from string value to hook partial function that
    does run it at runtime.

    :raise NotImplementedError: When the searching hook's function result does
        not exist in the registry.
    :raise NotImplementedError: When the searching hook's tag result does not
        exists in the registry with its function key.

    :param hook: A hook value that able to match with Task regex.
    :rtype: Callable[[], TagFunc]
    """
    if not (found := Re.RE_TASK_FMT.search(hook)):
        raise ValueError(
            f"Hook {hook!r} does not match with hook format regex."
        )

    # NOTE: Pass the searching hook string to `path`, `func`, and `tag`.
    hook: HookSearchData = HookSearchData(**found.groupdict())

    # NOTE: Registry object should implement on this package only.
    rgt: dict[str, Registry] = make_registry(f"{hook.path}")
    if hook.func not in rgt:
        raise NotImplementedError(
            f"``REGISTER-MODULES.{hook.path}.registries`` does not "
            f"implement registry: {hook.func!r}."
        )

    if hook.tag not in rgt[hook.func]:
        raise NotImplementedError(
            f"tag: {hook.tag!r} does not found on registry func: "
            f"``REGISTER-MODULES.{hook.path}.registries.{hook.func}``"
        )
    return rgt[hook.func][hook.tag]
