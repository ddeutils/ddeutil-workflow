# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from heapq import heappush
from threading import Thread
from zoneinfo import ZoneInfo

from ddeutil.workflow.__types import DictData
from ddeutil.workflow.exceptions import WorkflowException
from ddeutil.workflow.loader import Loader
from ddeutil.workflow.on import On
from ddeutil.workflow.pipeline import Pipeline
from ddeutil.workflow.scheduler import CronRunner
from ddeutil.workflow.utils import (
    Result,
    batch,
    delay,
    get_diff_sec,
    param2template,
)
from dotenv import load_dotenv
from schedule import CancelJob, Scheduler

load_dotenv("../../../.env")
logging.basicConfig(
    level=logging.DEBUG,
    format=(
        "%(asctime)s.%(msecs)03d (%(name)-10s, %(process)-5d, %(thread)-5d) "
        "[%(levelname)-7s] %(message)-120s (%(filename)s:%(lineno)s)"
    ),
    handlers=[logging.StreamHandler()],
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("schedule").setLevel(logging.INFO)

tz: ZoneInfo = ZoneInfo(os.getenv("WORKFLOW_CORE_TIMEZONE", "UTC"))


def catch_exceptions(cancel_on_failure=False):
    """Catch exception error from scheduler job."""

    def catch_exceptions_decorator(job_func):
        @wraps(job_func)
        def wrapper(*args, **kwargs):
            try:
                return job_func(*args, **kwargs)
            except Exception as err:
                logging.exception(err)
                if cancel_on_failure:
                    return CancelJob

        return wrapper

    return catch_exceptions_decorator


@dataclass
class PipelineTask:
    pipeline: Pipeline
    on: On
    queue: list[datetime]
    running: list[datetime]


def queue2str(queue: list[datetime]) -> Iterator[str]:
    return (f"{q:%Y-%m-%d %H:%M:%S}" for q in queue)


def pipeline_release(task: PipelineTask) -> None:
    """Pipeline release, it will use with the same logic of `pipeline.release`
    method.

    :param task: A PipelineTask dataclass.
    """
    pipeline: Pipeline = task.pipeline
    on: On = task.on

    gen: CronRunner = on.generate(
        datetime.now(tz=tz).replace(second=0, microsecond=0)
    )
    cron_tz: ZoneInfo = gen.tz

    next_running_time: datetime = gen.next
    while next_running_time in task.running[pipeline.name]:
        next_running_time: datetime = gen.next

    logging.debug(
        f"[CORE]: {pipeline.name!r} : {on.cronjob} : "
        f"{next_running_time:%Y-%m-%d %H:%M:%S}"
    )
    heappush(task.running[pipeline.name], next_running_time)

    # TODO: event should set on this step for release next pipeline task?

    if get_diff_sec(next_running_time, tz=cron_tz) > 55:
        logging.debug(
            f"({pipeline.run_id}) [CORE]: {pipeline.name!r} : {on.cronjob} : "
            f"Does not closely >> {next_running_time:%Y-%m-%d %H:%M:%S}"
        )

        # NOTE: Add this next running datetime to queue
        heappush(task.queue[pipeline.name], next_running_time)
        task.running[pipeline.name].remove(next_running_time)
        time.sleep(0.5)
        return

    logging.debug(
        f"({pipeline.run_id}) [CORE]: {pipeline.name!r} : {on.cronjob} : "
        f"Closely to run >> {next_running_time:%Y-%m-%d %H:%M:%S}"
    )

    # NOTE: Release when the time is nearly to schedule time.
    while (duration := get_diff_sec(next_running_time, tz=tz)) > (15 + 5):
        logging.debug(
            f"({pipeline.run_id}) [CORE]: {pipeline.name!r} : {on.cronjob} : "
            f"Sleep until: {duration}"
        )
        time.sleep(15)

    time.sleep(0.5)

    # NOTE: Release parameter that use to change if params has
    #   templating.
    release_params: DictData = {
        "release": {
            "logical_date": next_running_time,
        },
    }

    # WARNING: Re-create pipeline object that use new running pipeline
    #   ID.
    runner: Pipeline = pipeline.get_running_id(run_id=pipeline.new_run_id)
    rs: Result = runner.execute(
        # FIXME: replace fix parameters on this execution process.
        params=param2template(
            {"asat-dt": "${{ release.logical_date }}"}, release_params
        ),
    )
    logging.debug(
        f"({runner.run_id}) [CORE]: {pipeline.name!r} : {on.cronjob} : "
        f"End release"
    )

    del runner

    # NOTE: remove this release date from running
    task.running[pipeline.name].remove(next_running_time)

    # IMPORTANT:
    #   Add the next running datetime to pipeline queue
    finish_time: datetime = datetime.now(tz=cron_tz).replace(
        second=0, microsecond=0
    )
    future_running_time: datetime = gen.next
    while (
        future_running_time in task.running[pipeline.name]
        or future_running_time in task.queue[pipeline.name]
        or future_running_time < finish_time
    ):
        future_running_time: datetime = gen.next

    heappush(task.queue[pipeline.name], future_running_time)

    # NOTE: Set parent ID on this result
    rs.set_parent_run_id(pipeline.run_id)
    logging.debug(f"[CORE]: {rs}")


@catch_exceptions(cancel_on_failure=True)
def workflow_task(
    pipeline_tasks: list[PipelineTask],
    stop: datetime,
    threads: dict[str, Thread],
) -> CancelJob | None:
    """Workflow task generator that create release pair of pipeline and on to
    the threading in background.

        This workflow task will start every minute at :02 second.
    """
    start_date: datetime = datetime.now(tz=tz)
    start_date_minute = start_date.replace(second=0, microsecond=0)

    if start_date > stop:
        logging.info("[WORKFLOW]: Stop this schedule with datetime stopper.")
        while len(threads) > 0:
            logging.warning(
                "[WORKFLOW]: Waiting pipeline release thread that still "
                "running in background."
            )
            time.sleep(15)
        return CancelJob

    # IMPORTANT:
    #       Filter pipeline & on that should to run with `pipeline_release`
    #   function. It will deplicate running with different schedule value
    #   because I use current time in this condition.
    #
    #       For example, if a pipeline A queue has '00:02:00' time that
    #   should to run and its schedule has '*/2 * * * *' and '*/35 * * * *'.
    #   This condition will release with 2 threading job.
    #
    #   '00:02:00'  --> '*/2 * * * *'   --> running
    #               --> '*/35 * * * *'  --> skip
    #
    for task in pipeline_tasks:

        # NOTE: Get incoming datetime queue.
        logging.debug(
            f"[WORKFLOW]: Current queue: {task.pipeline.name!r} : "
            f"{list(queue2str(task.queue[task.pipeline.name]))}"
        )

        # NOTE: Create minute unit value for any scheduler datetime that
        #   checking a pipeline task should run in this datetime.
        current_running_time: datetime = start_date_minute.astimezone(
            tz=ZoneInfo(task.on.tz)
        )
        if (
            len(task.queue[task.pipeline.name]) > 0
            and current_running_time != task.queue[task.pipeline.name][0]
        ) or (
            task.on.next(current_running_time)
            != task.queue[task.pipeline.name][0]
        ):
            logging.debug(
                f"[WORKFLOW]: Skip schedule "
                f"{current_running_time:%Y-%m-%d %H:%M:%S} "
                f"for : {task.pipeline.name!r} : {task.on.cronjob}"
            )
            continue
        elif len(task.queue[task.pipeline.name]) == 0:
            # TODO: Should auto add new queue?
            logging.warning(
                f"[WORKFLOW]: Queue is empty for : {task.pipeline.name!r} : "
                f"{task.on.cronjob}"
            )
            continue

        # NOTE: Remove this datetime from queue.
        task.queue[task.pipeline.name].pop(0)

        thread_name: str = (
            f"{task.pipeline.name}|{str(task.on.cronjob)}|"
            f"{current_running_time:%Y%m%d%H%M}"
        )
        pipe_thread: Thread = Thread(
            target=pipeline_release,
            args=(task,),
            name=thread_name,
            daemon=True,
        )

        threads[thread_name] = pipe_thread

        pipe_thread.start()

        delay()

    logging.debug(f"[WORKFLOW]: {'=' * 100}")


def workflow_long_running_task(threads: dict[str, Thread]) -> None:
    """Workflow schedule for monitoring long running thread from the schedule
    control.

    :param threads: A mapping of Thread object and its name.
    """
    logging.debug("[MONITOR]: Start checking long running pipeline release.")
    snapshot_threads = list(threads.keys())
    for t_name in snapshot_threads:

        # NOTE: remove the thread that running success.
        if not threads[t_name].is_alive():
            threads.pop(t_name)


def workflow_control(
    pipelines: list[str],
    until: datetime | None = None,
    externals: DictData | None = None,
) -> list[str]:
    """Workflow scheduler control.

    :param pipelines: A list of pipeline names that want to schedule running.
    :param until:
    :param externals: An external parameters that pass to Loader.
    """
    schedule: Scheduler = Scheduler()
    start_date: datetime = datetime.now(tz=tz)

    # NOTE: Design workflow queue caching.
    #   ---
    #   {"pipeline-name": [<release-datetime>, <release-datetime>, ...]}
    #
    wf_queue: dict[str, list[datetime]] = {}
    wf_running: dict[str, list[datetime]] = {}
    thread_releases: dict[str, Thread] = {}

    start_date_waiting: datetime = (start_date + timedelta(minutes=1)).replace(
        second=0, microsecond=0
    )

    # NOTE: Create pair of pipeline and on.
    pipeline_tasks: list[PipelineTask] = []

    for name in pipelines:
        pipeline: Pipeline = Pipeline.from_loader(name, externals=externals)

        # NOTE: Create default list of release datetime.
        wf_queue[name]: list[datetime] = []
        wf_running[name]: list[datetime] = []

        for on in pipeline.on:

            on_gen = on.generate(start_date_waiting)
            next_running_date = on_gen.next
            while next_running_date in wf_queue[name]:
                next_running_date = on_gen.next

            heappush(wf_queue[name], next_running_date)
            pipeline_tasks.append(
                PipelineTask(
                    pipeline=pipeline, on=on, queue=wf_queue, running=wf_running
                ),
            )

    # NOTE: This schedule job will start every minute at :02 seconds.
    schedule.every(1).minutes.at(":02").do(
        workflow_task,
        pipeline_tasks=pipeline_tasks,
        stop=until or (start_date + timedelta(minutes=5, seconds=20)),
        threads=thread_releases,
    ).tag("control")

    # NOTE: Checking zombie task with schedule job will start every 5 minute.
    schedule.every(5).minutes.at(":10").do(
        workflow_long_running_task,
        threads=thread_releases,
    ).tag("monitor")

    # NOTE: Start running schedule
    logging.info(f"[WORKFLOW]: Start schedule: {pipelines}")
    while True:
        schedule.run_pending()
        time.sleep(1)
        if not schedule.get_jobs("control"):
            schedule.clear("monitor")
            logging.warning(
                f"[WORKFLOW]: Pipeline release thread: {thread_releases}"
            )
            logging.warning("[WORKFLOW]: Does not have any schedule jobs !!!")
            break

    logging.warning(f"Queue: {[wf_queue[wf] for wf in wf_queue]}")
    logging.warning(f"Running: {[wf_running[wf] for wf in wf_running]}")
    return pipelines


def workflow(
    until: datetime | None = None,
    externals: DictData | None = None,
    excluded: list[str] | None = None,
):
    """Workflow application that running multiprocessing schedule with chunk of
    pipelines that exists in config path.

    :param until:
    :param excluded:
    :param externals:

        This function will get all pipelines that include on value that was
    created in config path and chuck it with WORKFLOW_APP_PIPELINE_PER_PROCESS
    value to multiprocess executor pool.

    The current workflow logic:
    ---
        PIPELINES ==> process 01 ==> schedule 1 minute --> thread of release
                                                           pipeline task 01 01
                                                       --> thread of release
                                                           pipeline task 01 02
                  ==> process 02 ==> schedule 1 minute --> thread of release
                                                           pipeline task 02 01
                                                       --> thread of release
                                                           pipeline task 02 02
                  ==> ...
    """
    excluded: list = excluded or []

    with ProcessPoolExecutor(max_workers=2) as executor:
        futures: list[Future] = [
            executor.submit(
                workflow_control,
                pipelines=[load[0] for load in loader],
                until=until,
                externals=(externals or {}),
            )
            for loader in batch(
                Loader.find(Pipeline, include=["on"], excluded=excluded),
                # [
                #     ("pipe-scheduling", None),
                #     # ("pipe-scheduling-minute", None),
                # ],
                n=1,
            )
        ]

        results: list[str] = []
        for future in as_completed(futures):
            if err := future.exception():
                logging.error(str(err))
                raise WorkflowException(str(err)) from err
            results.extend(future.result(timeout=1))
        return results


if __name__ == "__main__":
    # TODO: Define input arguments that want to manage this application.
    workflow_rs: list[str] = workflow()
    logging.info(f"Application run success: {workflow_rs}")
