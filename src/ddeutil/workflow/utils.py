# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Utility Functions for Workflow Operations.

This module provides essential utility functions used throughout the workflow
system for ID generation, datetime handling, string processing, template
operations, and other common tasks.

Functions:
    to_train: Convert camel case strings to train case format
    prepare_newline: Format messages with multiple newlines
    replace_sec: Replace seconds and microseconds in datetime objects
    clear_tz: Clear timezone info from datetime objects
    get_dt_now: Get current datetime with timezone
    get_d_now: Get current date
    get_diff_sec: Calculate time difference in seconds
    reach_next_minute: Check if datetime reaches next minute
    wait_until_next_minute: Wait until next minute
    delay: Add random delay to execution
    gen_id: Generate unique identifiers for workflow components
    default_gen_id: Generate default running ID
    make_exec: Make files executable
    filter_func: Filter function objects from data structures
    cross_product: Generate cross product of matrix values
    cut_id: Cut running ID to specified length
    dump_all: Serialize nested BaseModel objects to dictionaries
    obj_name: Get object name or class name

Example:
    ```python
    from ddeutil.workflow.utils import gen_id, get_dt_now

    # Generate unique ID
    run_id = gen_id("workflow")

    # Get current datetime
    now = get_dt_now()
    ```
"""
from __future__ import annotations

import stat
import time
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from hashlib import md5
from inspect import isclass, isfunction
from itertools import product
from pathlib import Path
from random import randrange
from typing import Any, Final, Optional, TypeVar, Union, overload
from zoneinfo import ZoneInfo

from ddeutil.core import hash_str
from pydantic import BaseModel

from .__types import DictData, Matrix

T = TypeVar("T")
UTC: Final[ZoneInfo] = ZoneInfo("UTC")
MARK_NEWLINE: Final[str] = "||"

# Cache for random delay values to avoid repeated randrange calls
_CACHED_DELAYS = [randrange(0, 99, step=10) / 100 for _ in range(100)]
_DELAY_INDEX = 0


def to_train(camel: str) -> str:
    """Convert camel case string to train case.

    Args:
        camel: A camel case string that want to convert.

    Returns:
        str: The converted train-case string.
    """
    return "".join("-" + i if i.isupper() else i for i in camel).lstrip("-")


def prepare_newline(msg: str) -> str:
    """Prepare message that has multiple newline char.

    Args:
        msg: A message that want to prepare.

    Returns:
        str: The prepared message with formatted newlines.
    """
    # NOTE: Remove ending with "\n" and replace "\n" with the "||" value.
    msg: str = msg.strip("\n").replace("\n", MARK_NEWLINE)
    if MARK_NEWLINE not in msg:
        return msg

    msg_lines: list[str] = msg.split(MARK_NEWLINE)
    msg_last: str = msg_lines[-1]
    msg_body: str = (
        "\n" + "\n".join(f" ... |  \t{s}" for s in msg_lines[1:-1])
        if len(msg_lines) > 2
        else ""
    )
    return msg_lines[0] + msg_body + f"\n ... ╰─ \t{msg_last}"


def replace_sec(dt: datetime) -> datetime:
    """Replace second and microsecond values to 0.

    Args:
        dt: A datetime object that want to replace.

    Returns:
        datetime: The datetime with seconds and microseconds set to 0.
    """
    return dt.replace(second=0, microsecond=0)


def clear_tz(dt: datetime) -> datetime:
    """Replace timezone info on an input datetime object to UTC."""
    return dt.replace(tzinfo=UTC)


def get_dt_now(offset: float = 0.0) -> datetime:
    """Return the current datetime object.

    Args:
        offset: An offset second value to subtract from current time.

    Returns:
        datetime: The current datetime object with UTC timezone.
    """
    return datetime.now().replace(tzinfo=UTC) - timedelta(seconds=offset)


def get_d_now(offset: float = 0.0) -> date:  # pragma: no cov
    """Return the current date object.

    Args:
        offset: An offset second value to subtract from current time.

    Returns:
        date: The current date object.
    """
    return (
        datetime.now().replace(tzinfo=UTC) - timedelta(seconds=offset)
    ).date()


def get_diff_sec(dt: datetime, offset: float = 0.0) -> int:
    """Return second value from difference between input datetime and current datetime.

    Args:
        dt: A datetime object to calculate difference from.
        offset: An offset second value to add to the difference.

    Returns:
        int: The difference in seconds between the input datetime and current time.
    """
    return round(
        (
            dt - datetime.now(tz=dt.tzinfo) - timedelta(seconds=offset)
        ).total_seconds()
    )


def reach_next_minute(dt: datetime, offset: float = 0.0) -> bool:
    """Check if datetime object reaches the next minute level.

    Args:
        dt: A datetime object to check.
        offset: An offset second value.

    Returns:
        bool: True if datetime reaches next minute, False otherwise.

    Raises:
        ValueError: If the input datetime is less than current date.
    """
    diff: float = (
        replace_sec(clear_tz(dt)) - replace_sec(get_dt_now(offset=offset))
    ).total_seconds()
    if diff >= 60:
        return True
    elif diff >= 0:
        return False
    raise ValueError(
        "Check reach the next minute function should check a datetime that not "
        "less than the current date"
    )


def wait_until_next_minute(
    dt: datetime, second: float = 0
) -> None:  # pragma: no cov
    """Wait with sleep to the next minute with an offset second value.

    Args:
        dt: The datetime to wait until next minute from.
        second: Additional seconds to wait after reaching next minute.
    """
    future: datetime = replace_sec(dt) + timedelta(minutes=1)
    time.sleep((future - dt).total_seconds() + second)


def delay(second: float = 0) -> None:  # pragma: no cov
    """Delay execution with time.sleep and random second value between 0.00-0.99 seconds.

    Args:
        second: Additional seconds to add to the random delay.
    """
    global _DELAY_INDEX
    cached_random = _CACHED_DELAYS[_DELAY_INDEX % len(_CACHED_DELAYS)]
    _DELAY_INDEX = (_DELAY_INDEX + 1) % len(_CACHED_DELAYS)
    time.sleep(second + cached_random)


def gen_id(
    value: Any,
    *,
    sensitive: bool = True,
    unique: bool = False,
    simple_mode: Optional[bool] = None,
    extras: DictData | None = None,
) -> str:
    """Generate running ID for tracking purposes.

    This function uses MD5 algorithm if simple mode is disabled, or cuts the
    hashing value length to 10 if simple mode is enabled.

    Simple Mode Format:
        YYYYMMDDHHMMSSffffffTxxxxxxxxxx
        year month day hour minute second microsecond sep simple-id

    Args:
        value: A value to add as prefix before hashing with MD5.
        sensitive: Flag to convert value to lowercase before hashing.
        unique: Flag to add timestamp at microsecond level before hashing.
        simple_mode: Flag to generate ID using simple mode.
        extras: Extra parameters to override config values.

    Returns:
        str: Generated unique identifier.
    """
    from .conf import dynamic

    if not isinstance(value, str):
        value: str = str(value)

    dt: datetime = datetime.now(tz=UTC)
    if dynamic("generate_id_simple_mode", f=simple_mode, extras=extras):
        return (f"{dt:%Y%m%d%H%M%S%f}T" if unique else "") + hash_str(
            f"{(value if sensitive else value.lower())}", n=10
        )

    return md5(
        (
            (f"{dt}T" if unique else "")
            + f"{(value if sensitive else value.lower())}"
        ).encode()
    ).hexdigest()


def default_gen_id() -> str:
    """Return running ID for making default ID for the Result model.

    This function is used when a run_id field is initialized for the first time.

    Returns:
        str: Generated default running ID.
    """
    return gen_id("MOCK", unique=True)


def make_exec(path: Union[Path, str]) -> None:
    """Change file mode to be executable.

    Args:
        path: A file path to make executable.
    """
    f: Path = Path(path) if isinstance(path, str) else path
    f.chmod(f.stat().st_mode | stat.S_IEXEC)


def filter_func(value: T) -> T:
    """Filter out custom functions from mapping context by replacing with function names.

    This function replaces custom functions with their function names in data
    structures. Built-in functions remain unchanged.

    Args:
        value: A value or data structure to filter function values from.

    Returns:
        T: The filtered value with functions replaced by their names.
    """
    if isinstance(value, dict):
        return {k: filter_func(value[k]) for k in value}
    elif isinstance(value, (list, tuple, set)):
        try:
            return type(value)(filter_func(i) for i in value)
        except TypeError:
            return value

    if isfunction(value):
        # NOTE: If it wants to improve to get this function, it is able to save
        # to some global memory storage.
        #   ---
        #   >>> GLOBAL_DICT[value.__name__] = value
        #
        return value.__name__
    return value


def cross_product(matrix: Matrix) -> Iterator[DictData]:
    """Generate iterator of product values from matrix.

    Args:
        matrix: A matrix to generate cross products from.

    Returns:
        Iterator[DictData]: Iterator of dictionary combinations.
    """
    yield from (
        {_k: _v for e in mapped for _k, _v in e.items()}
        for mapped in product(
            *[[{k: v} for v in vs] for k, vs in matrix.items()]
        )
    )


def cut_id(run_id: str, *, num: int = 6) -> str:
    """Cut running ID to specified length.

    Example:
        >>> cut_id(run_id='20240101081330000000T1354680202')
        '202401010813680202'

    Args:
        run_id: A running ID to cut.
        num: Number of characters to keep from the end.

    Returns:
        str: The cut running ID.
    """
    if "T" in run_id:
        dt, simple = run_id.split("T", maxsplit=1)
        return dt[:12] + simple[-num:]
    return run_id[:12] + run_id[-num:]


@overload
def dump_all(
    value: BaseModel, by_alias: bool = False
) -> DictData: ...  # pragma: no cov


@overload
def dump_all(value: T, by_alias: bool = False) -> T: ...  # pragma: no cov


def dump_all(
    value: Union[T, BaseModel],
    by_alias: bool = False,
) -> Union[T, DictData]:
    """Dump all nested BaseModel objects to dictionary objects.

    Args:
        value: A value that may contain BaseModel objects.
        by_alias: Whether to use field aliases when dumping.

    Returns:
        Union[T, DictData]: The value with BaseModel objects converted to dictionaries.
    """
    if isinstance(value, dict):
        return {k: dump_all(value[k], by_alias=by_alias) for k in value}
    elif isinstance(value, (list, tuple, set)):
        try:
            return type(value)(dump_all(i, by_alias=by_alias) for i in value)
        except TypeError:
            return value
    elif isinstance(value, BaseModel):
        return value.model_dump(by_alias=by_alias)
    return value


def obj_name(obj: Optional[Union[str, object]] = None) -> Optional[str]:
    """Get object name or class name.

    Args:
        obj: An object or string to get the name from.

    Returns:
        Optional[str]: The object name, class name, or None if obj is None.
    """
    if not obj:
        return None
    elif isinstance(obj, str):
        obj_type: str = obj
    elif isclass(obj):
        obj_type: str = obj.__name__
    else:
        obj_type: str = obj.__class__.__name__
    return obj_type
