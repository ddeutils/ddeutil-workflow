# ------------------------------------------------------------------------------
# Copyright (c) 2023 Priyanshu Panwar. All rights reserved.
# Licensed under the MIT License.
# This code refs from: https://github.com/priyanshu-panwar/fastapi-utilities
# ------------------------------------------------------------------------------
import asyncio
import logging
import os
from asyncio import ensure_future
from datetime import datetime
from functools import wraps
from zoneinfo import ZoneInfo

from croniter import croniter
from starlette.concurrency import run_in_threadpool


def get_cron_delta(cron: str):
    """This function returns the time delta between now and the next cron
    execution time.
    """
    now: datetime = datetime.now(
        tz=ZoneInfo(os.getenv("WORKFLOW_CORE_TIMEZONE", "UTC"))
    )
    cron = croniter(cron, now)
    return (cron.get_next(datetime) - now).total_seconds()


def repeat_at(
    *,
    cron: str,
    logger: logging.Logger = None,
    raise_exceptions: bool = False,
    max_repetitions: int = None,
):
    """This function returns a decorator that makes a function execute
    periodically as per the cron expression provided.

    :param cron: str
        Cron-style string for periodic execution, eg. '0 0 * * *' every midnight
    :param logger: logging.Logger (default None)
        Logger object to log exceptions
    :param raise_exceptions: bool (default False)
        Whether to raise exceptions or log them
    :param max_repetitions: int (default None)
        Maximum number of times to repeat the function. If None, repeat
        indefinitely.

    """

    def decorator(func):
        is_coroutine = asyncio.iscoroutinefunction(func)

        @wraps(func)
        def wrapper(*_args, **_kwargs):
            repititions = 0
            if not croniter.is_valid(cron):
                raise ValueError("Invalid cron expression")

            async def loop(*args, **kwargs):
                nonlocal repititions
                while max_repetitions is None or repititions < max_repetitions:
                    try:
                        sleep_time = get_cron_delta(cron)
                        await asyncio.sleep(sleep_time)
                        if is_coroutine:
                            await func(*args, **kwargs)
                        else:
                            await run_in_threadpool(func, *args, **kwargs)
                    except Exception as e:
                        if logger:
                            logger.exception(e)
                        if raise_exceptions:
                            raise e
                    repititions += 1

            ensure_future(loop(*_args, **_kwargs))

        return wrapper

    return decorator


def repeat_every(
    *,
    seconds: float,
    wait_first: bool = False,
    logger: logging.Logger = None,
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
    :param logger: logging.Logger (default None)
        The logger to use for logging exceptions.
    :param raise_exceptions: bool (default False)
        Whether to raise exceptions instead of logging them.
    :param max_repetitions: int (default None)
        The maximum number of times to repeat the function. If None, the
        function will repeat indefinitely.
    """

    def decorator(func):
        is_coroutine = asyncio.iscoroutinefunction(func)

        @wraps(func)
        async def wrapper(*_args, **_kwargs):
            repetitions = 0

            async def loop(*args, **kwargs):
                nonlocal repetitions
                if wait_first:
                    await asyncio.sleep(seconds)
                while max_repetitions is None or repetitions < max_repetitions:
                    try:
                        if is_coroutine:
                            await func(*args, **kwargs)
                        else:
                            await run_in_threadpool(func, *args, **kwargs)
                    except Exception as e:
                        if logger is not None:
                            logger.exception(e)
                        if raise_exceptions:
                            raise e
                    repetitions += 1
                    await asyncio.sleep(seconds)

            ensure_future(loop(*_args, **_kwargs))

        return wrapper

    return decorator
