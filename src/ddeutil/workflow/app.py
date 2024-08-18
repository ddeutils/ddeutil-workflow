# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Iterator
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta
from functools import wraps
from itertools import chain, islice
from typing import Any

from dotenv import load_dotenv
from schedule import CancelJob, Scheduler

try:
    from .loader import Loader
    from .pipeline import Pipeline
except ImportError:
    from ddeutil.workflow.loader import Loader
    from ddeutil.workflow.pipeline import Pipeline


load_dotenv("../../../.env")


def catch_exceptions(cancel_on_failure=False):
    """Catch exception error from scheduler job."""

    def catch_exceptions_decorator(job_func):
        @wraps(job_func)
        def wrapper(*args, **kwargs):
            try:
                return job_func(*args, **kwargs)
            except Exception as err:
                logging.error(str(err))

                if cancel_on_failure:
                    return CancelJob

        return wrapper

    return catch_exceptions_decorator


@catch_exceptions(cancel_on_failure=True)
def bad_task():
    return 1 / 0


@catch_exceptions(cancel_on_failure=True)
def task_sleep_more_than_interval(stop: datetime):
    time.sleep(3)
    n = datetime.now()
    print("Stop at:", stop)
    if n > stop:
        return CancelJob
    print(
        f"{n:%Y-%m-%d %H:%M:%S} This running on "
        f"thread: {threading.get_ident()}, process: {os.getpid()}"
    )


def workflow_scheduler(loader: list[str]) -> None:
    schedule = Scheduler()

    # NOTE: Create schedule jobs on this schedule object.
    schedule.every(5).seconds.do(bad_task)
    schedule.every(2).seconds.do(
        task_sleep_more_than_interval,
        datetime.now() + timedelta(seconds=10),
    )
    print(f"Start workflow schedule: {loader}")
    while True:
        schedule.run_pending()
        time.sleep(0.5)
        if not schedule.get_jobs():
            break


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
    it = iter(iterable)
    while True:
        chunk_it = islice(it, n)
        try:
            first_el = next(chunk_it)
        except StopIteration:
            return
        yield chain((first_el,), chunk_it)


def workflow():
    """Workflow application that running multiprocessing schedule with chunk of
    pipelines that exists in config path.
    """

    with ProcessPoolExecutor() as executor:
        futures: list[Future] = [
            executor.submit(
                workflow_scheduler,
                [load[0] for load in loader],
            )
            for loader in batch(
                Loader.find(Pipeline, include=["on"]),
                n=4,
            )
        ]
        for future in as_completed(futures):
            if err := future.exception():
                print(err)
                logging.info(str(err))
                continue
            rs = future.result()
            print(rs)


if __name__ == "__main__":
    workflow()
