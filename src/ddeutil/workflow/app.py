# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import functools
import time

import schedule


def catch_exceptions(cancel_on_failure=False):
    """Catch exception error from scheduler job."""

    def catch_exceptions_decorator(job_func):
        @functools.wraps(job_func)
        def wrapper(*args, **kwargs):
            try:
                return job_func(*args, **kwargs)
            except Exception as err:
                print(err)

                if cancel_on_failure:
                    return schedule.CancelJob

        return wrapper

    return catch_exceptions_decorator


@catch_exceptions(cancel_on_failure=True)
def bad_task():
    return 1 / 0


schedule.every(5).seconds.do(bad_task)

if __name__ == "__main__":
    while True:
        schedule.run_pending()
        time.sleep(1)
        if not schedule.get_jobs():
            break
