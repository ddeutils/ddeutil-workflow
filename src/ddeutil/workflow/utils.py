# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import logging
import stat
import time
from collections.abc import Iterator
from datetime import datetime, timedelta
from hashlib import md5
from inspect import isfunction
from itertools import chain, islice, product
from pathlib import Path
from random import randrange
from typing import Any, TypeVar
from zoneinfo import ZoneInfo

from ddeutil.core import hash_str

from .__types import DictData, Matrix

T = TypeVar("T")
UTC = ZoneInfo("UTC")
logger = logging.getLogger("ddeutil.workflow")


def get_dt_now(
    tz: ZoneInfo | None = None, offset: float = 0.0
) -> datetime:  # pragma: no cov
    """Return the current datetime object.

    :param tz:
    :param offset:
    :return: The current datetime object that use an input timezone or UTC.
    """
    return datetime.now(tz=(tz or UTC)) - timedelta(seconds=offset)


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
            dt - datetime.now(tz=(tz or UTC)) - timedelta(seconds=offset)
        ).total_seconds()
    )


def reach_next_minute(
    dt: datetime, tz: ZoneInfo | None = None, offset: float = 0.0
) -> bool:
    """Check this datetime object is not in range of minute level on the current
    datetime.
    """
    diff: float = (
        (
            get_dt_now(tz=(tz or UTC), offset=offset).replace(
                second=0, microsecond=0
            )
        )
        - dt.replace(second=0, microsecond=0)
    ).total_seconds()

    if diff >= 60:
        return True
    elif diff >= 0:
        return False

    raise ValueError(
        "Check reach the next minute function should check a datetime that not "
        "gather than the current date"
    )


def wait_to_next_minute(
    dt: datetime, second: float = 0
) -> None:  # pragma: no cov
    """Wait with sleep to the next minute with an offset second value."""
    future = dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
    time.sleep((future - dt).total_seconds() + second)


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
    """Generate running ID for able to tracking. This generates process use `md5`
    algorithm function if ``WORKFLOW_CORE_WORKFLOW_ID_SIMPLE_MODE`` set to
    false. But it will cut this hashing value length to 10 it the setting value
    set to true.

    :param value: A value that want to add to prefix before hashing with md5.
    :param sensitive: A flag that convert the value to lower case before hashing
    :param unique: A flag that add timestamp at microsecond level to value
        before hashing.

    :rtype: str
    """
    from .conf import config

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


def make_exec(path: str | Path) -> None:
    """Change mode of file to be executable file.

    :param path: A file path that want to make executable permission.
    """
    f: Path = Path(path) if isinstance(path, str) else path
    f.chmod(f.stat().st_mode | stat.S_IEXEC)


def filter_func(value: T) -> T:
    """Filter out an own created function of any value of mapping context by
    replacing it to its function name. If it is built-in function, it does not
    have any changing.

    :param value: A value context data that want to filter out function value.
    :type: The same type of input ``value``.
    """
    if isinstance(value, dict):
        return {k: filter_func(value[k]) for k in value}
    elif isinstance(value, (list, tuple, set)):
        return type(value)([filter_func(i) for i in value])

    if isfunction(value):
        # NOTE: If it wants to improve to get this function, it is able to save
        # to some global memory storage.
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

    :param key
    :param values
    :param fixed

    :rtype: DictData
    """
    if key in values:
        values[(fixed or key.replace("-", "_"))] = values.pop(key)
    return values


def cross_product(matrix: Matrix) -> Iterator[DictData]:
    """Iterator of products value from matrix.

    :param matrix:

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
        >>> for b in batch(iter('ABCDEFG'), 3):
        ...     print(list(b))
        ['A', 'B', 'C']
        ['D', 'E', 'F']
        ['G']

    :param iterable:
    :param n:

    :rtype: Iterator[Any]
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


def cut_id(run_id: str, *, num: int = 6) -> str:
    """Cutting running ID with length.

    Example:
        >>> cut_id(run_id='668931127320241228100331254567')
        '254567'

    :param run_id:
    :param num:

    :rtype: str
    """
    return run_id[-num:]
