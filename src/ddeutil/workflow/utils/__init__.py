import inspect
from functools import wraps
from importlib import import_module
from typing import Callable, Optional, Protocol

from ddeutil.core import lazy


class TagFunc(Protocol):
    ref_name: str
    tag: str

    def __call__(self, *args, **kwargs): ...


def tag(name: str, ref_name: Optional[str] = None):
    def func_internal(func: TagFunc):
        func.tag = name
        func.ref_name = ref_name or func.__name__

        @wraps(func)
        def wrapped(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapped

    return func_internal


def make_registry(module: str):
    rs: dict[str, dict[str, Callable[[], Callable]]] = {}
    for fstr, func in inspect.getmembers(
        import_module(module), inspect.isfunction
    ):
        if not hasattr(func, "tag"):
            continue
        if func.ref_name in rs:
            rs[func.ref_name][func.tag] = lazy(f"{module}.{fstr}")
        else:
            rs[func.ref_name] = {func.tag: lazy(f"{module}.{fstr}")}
    return rs
