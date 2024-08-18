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


@catch_exceptions(cancel_on_failure=True)
def observe_pipeline_able_to_poke():
    # TODO: Get the pipeline
    #   >>> for chunk of pipelines:
    #   ...     executor.submit(func, chuck)
    #   ---
    #   This function will multithread to running pipeline poke method.
    #
    return True


def task_sleep_more_than_interval():
    import threading
    from datetime import datetime

    time.sleep(3)
    n = datetime.now()
    print(f"{n:%Y-%m-%d %H:%M:%S} This running on: {threading.get_ident()}")


# schedule.every(5).seconds.do(bad_task)
schedule.every(2).seconds.do(task_sleep_more_than_interval)
# schedule.every(1).minutes.do(observe_pipeline_able_to_poke)


if __name__ == "__main__":
    while True:
        schedule.run_pending()
        # time.sleep(1)
        if not schedule.get_jobs():
            break
