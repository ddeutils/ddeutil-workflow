# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import inspect
from functools import wraps
from importlib import import_module
from typing import Callable, Protocol

from ddeutil.core import lazy


class TagFunc(Protocol):
    name: str
    tag: str

    def __call__(self, *args, **kwargs): ...


def tag(tag_value: str, name: str | None = None):
    """Tag decorator function that set function attributes, tag and name for
    make registries object.
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
