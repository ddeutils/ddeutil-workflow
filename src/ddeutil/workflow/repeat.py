# ------------------------------------------------------------------------------
# Copyright (c) 2023 Priyanshu Panwar. All rights reserved.
# Licensed under the MIT License.
# This code refs from: https://github.com/priyanshu-panwar/fastapi-utilities
# ------------------------------------------------------------------------------
from __future__ import annotations

import asyncio
from asyncio import ensure_future
from datetime import datetime
from functools import wraps

from starlette.concurrency import run_in_threadpool

from .__cron import CronJob
from .conf import config, get_logger

logger = get_logger("ddeutil.workflow")


def get_cronjob_delta(cron: str) -> float:
    """This function returns the time delta between now and the next cron
    execution time.
    """
    now: datetime = datetime.now(tz=config.tz)
    cron = CronJob(cron)
    return (cron.schedule(now).next - now).total_seconds()


def cron_valid(cron: str):
    try:
        CronJob(cron)
    except Exception as err:
        raise ValueError(f"Crontab value does not valid, {cron}") from err


async def run_func(
    is_coroutine,
    func,
    *args,
    raise_exceptions: bool = False,
    **kwargs,
):
    try:
        if is_coroutine:
            await func(*args, **kwargs)
        else:
            await run_in_threadpool(func, *args, **kwargs)
    except Exception as e:
        logger.exception(e)
        if raise_exceptions:
            raise e


def repeat_at(
    *,
    cron: str,
    delay: float = 0,
    raise_exceptions: bool = False,
    max_repetitions: int = None,
):
    """This function returns a decorator that makes a function execute
    periodically as per the cron expression provided.

    :param cron: str
        Cron-style string for periodic execution, eg. '0 0 * * *' every midnight
    :param delay:
    :param raise_exceptions: bool (default False)
        Whether to raise exceptions or log them
    :param max_repetitions: int (default None)
        Maximum number of times to repeat the function. If None, repeat
        indefinitely.
    """
    if max_repetitions and max_repetitions <= 0:
        raise ValueError(
            "max_repetitions should more than zero if it want to set"
        )

    def decorator(func):
        is_coroutine: bool = asyncio.iscoroutinefunction(func)

        @wraps(func)
        def wrapper(*_args, **_kwargs):
            repititions: int = 0
            cron_valid(cron)

            async def loop(*args, **kwargs):
                nonlocal repititions
                while max_repetitions is None or repititions < max_repetitions:
                    sleep_time = get_cronjob_delta(cron) + delay
                    await asyncio.sleep(sleep_time)
                    await run_func(
                        is_coroutine,
                        func,
                        *args,
                        raise_exceptions=raise_exceptions,
                        **kwargs,
                    )
                    repititions += 1

            ensure_future(loop(*_args, **_kwargs))

        return wrapper

    return decorator


def repeat_every(
    *,
    seconds: float,
    wait_first: bool = False,
    raise_exceptions: bool = False,
    max_repetitions: int = None,
):
    """This function returns a decorator that schedules a function to execute
    periodically after every `seconds` seconds.

    :param seconds: float
        The number of seconds to wait before executing the function again.
    :param wait_first: bool (default False)
        Whether to wait `seconds` seconds before executing the function for the
        first time.
    :param raise_exceptions: bool (default False)
        Whether to raise exceptions instead of logging them.
    :param max_repetitions: int (default None)
        The maximum number of times to repeat the function. If None, the
        function will repeat indefinitely.
    """
    if max_repetitions and max_repetitions <= 0:
        raise ValueError(
            "max_repetitions should more than zero if it want to set"
        )

    def decorator(func):
        is_coroutine: bool = asyncio.iscoroutinefunction(func)

        @wraps(func)
        async def wrapper(*_args, **_kwargs):
            repetitions = 0

            async def loop(*args, **kwargs):
                nonlocal repetitions

                if wait_first:
                    await asyncio.sleep(seconds)

                while max_repetitions is None or repetitions < max_repetitions:
                    await run_func(
                        is_coroutine,
                        func,
                        *args,
                        raise_exceptions=raise_exceptions,
                        **kwargs,
                    )

                    repetitions += 1
                    await asyncio.sleep(seconds)

            ensure_future(loop(*_args, **_kwargs))

        return wrapper

    return decorator
