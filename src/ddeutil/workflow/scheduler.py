# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import copy
import json
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
from typing import Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic.functional_validators import model_validator
from typing_extensions import Self

try:
    from schedule import CancelJob, Scheduler
except ImportError:
    raise ImportError(
        "Should install schedule package before use this module."
    ) from None

from .__types import DictData
from .cron import CronRunner
from .exceptions import WorkflowException
from .log import FileLog, Log
from .on import On
from .pipeline import Pipeline
from .utils import (
    Loader,
    Result,
    batch,
    delay,
    get_diff_sec,
    param2template,
)

load_dotenv()
tz: ZoneInfo = ZoneInfo(os.getenv("WORKFLOW_CORE_TIMEZONE", "UTC"))
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


__all__ = (
    "PipelineSchedule",
    "Schedule",
    "workflow",
)


class PipelineSchedule(BaseModel):
    """Pipeline schedule Pydantic Model."""

    name: str = Field(description="A pipeline name.")
    on: list[On] = Field(
        default_factory=list,
        description="An override On instance value.",
    )
    params: DictData = Field(
        default_factory=dict,
        description="A parameters that want to use to pipeline execution.",
    )

    @model_validator(mode="before")
    def __prepare__values(cls, values: DictData) -> DictData:
        """Prepare incoming values before validating with model fields."""

        values["name"] = values["name"].replace(" ", "_")

        cls.__bypass_on(values)
        return values

    @classmethod
    def __bypass_on(cls, data: DictData, externals: DictData | None = None):
        """Bypass the on data to loaded config data."""
        if on := data.pop("on", []):

            if isinstance(on, str):
                on = [on]

            if any(not isinstance(n, (dict, str)) for n in on):
                raise TypeError("The ``on`` key should be list of str or dict")

            # NOTE: Pass on value to Loader and keep on model object to on field
            data["on"] = [
                (
                    Loader(n, externals=(externals or {})).data
                    if isinstance(n, str)
                    else n
                )
                for n in on
            ]
        return data


class Schedule(BaseModel):
    """Schedule Pydantic Model that use to run with scheduler package. It does
    not equal the on value in Pipeline model but it use same logic to running
    release date with crontab interval.
    """

    desc: Optional[str] = Field(
        default=None,
        description=(
            "A schedule description that can be string of markdown content."
        ),
    )
    pipelines: list[PipelineSchedule] = Field(
        default_factory=list,
        description="A list of PipelineSchedule models.",
    )

    @classmethod
    def from_loader(
        cls,
        name: str,
        externals: DictData | None = None,
    ) -> Self:
        loader: Loader = Loader(name, externals=(externals or {}))

        # NOTE: Validate the config type match with current connection model
        if loader.type != cls:
            raise ValueError(f"Type {loader.type} does not match with {cls}")

        loader_data: DictData = copy.deepcopy(loader.data)

        # NOTE: Add name to loader data
        loader_data["name"] = name.replace(" ", "_")

        return cls.model_validate(obj=loader_data)

    def tasks(
        self,
        start_date: datetime,
        queue: dict[str, list[datetime]],
        running: dict[str, list[datetime]],
        externals: DictData | None = None,
    ) -> list[PipelineTask]:
        """Generate Task from the current datetime.

        :param start_date: A start date that get from the workflow schedule.
        :param queue:
        :param running:
        :param externals: An external parameters that pass to the Loader object.
        :rtype: list[PipelineTask]
        """

        # NOTE: Create pair of pipeline and on.
        pipeline_tasks: list[PipelineTask] = []
        externals: DictData = externals or {}

        for pipe in self.pipelines:
            pipeline: Pipeline = Pipeline.from_loader(
                pipe.name, externals=externals
            )

            # NOTE: Create default list of release datetime.
            queue[pipe.name]: list[datetime] = []
            running[pipe.name]: list[datetime] = []

            for on in pipeline.on:
                on_gen = on.generate(start_date)
                next_running_date = on_gen.next
                while next_running_date in queue[pipe.name]:
                    next_running_date = on_gen.next

                heappush(queue[pipe.name], next_running_date)

                pipeline_tasks.append(
                    PipelineTask(
                        pipeline=pipeline,
                        on=on,
                        params=pipe.params,
                        queue=queue,
                        running=running,
                    ),
                )

        return pipeline_tasks


def catch_exceptions(cancel_on_failure=False):
    """Catch exception error from scheduler job."""

    def catch_exceptions_decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as err:
                logging.exception(err)
                if cancel_on_failure:
                    return CancelJob

        return wrapper

    return catch_exceptions_decorator


def catch_exceptions_method(cancel_on_failure=False):
    """Catch exception error from scheduler job."""

    def catch_exceptions_decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as err:
                logging.exception(err)
                if cancel_on_failure:
                    return CancelJob

        return wrapper

    return catch_exceptions_decorator


@dataclass(frozen=True)
class PipelineTask:
    """Pipeline task dataclass that use to keep mapping data and objects for
    passing in multithreading task.
    """

    pipeline: Pipeline
    on: On
    params: DictData
    queue: list[datetime]
    running: list[datetime]

    @catch_exceptions_method(cancel_on_failure=True)
    def release(self, log: Log | None = None) -> None:
        """Pipeline release, it will use with the same logic of
        `pipeline.release` method.

        :param log: A log object.
        """
        log: Log = log or FileLog
        pipeline: Pipeline = self.pipeline
        on: On = self.on

        gen: CronRunner = on.generate(
            datetime.now(tz=tz).replace(second=0, microsecond=0)
        )
        cron_tz: ZoneInfo = gen.tz

        # NOTE: get next schedule time that generate from now.
        next_time: datetime = gen.next

        # NOTE: get next utils it does not running.
        while next_time in self.running[pipeline.name]:
            next_time: datetime = gen.next

        logging.debug(
            f"({pipeline.run_id}) [CORE]: {pipeline.name!r} : {on.cronjob} : "
            f"{next_time:%Y-%m-%d %H:%M:%S}"
        )
        heappush(self.running[pipeline.name], next_time)

        if get_diff_sec(next_time, tz=cron_tz) > 55:
            logging.debug(
                f"({pipeline.run_id}) [CORE]: {pipeline.name!r} : {on.cronjob} "
                f": Does not closely >> {next_time:%Y-%m-%d %H:%M:%S}"
            )

            # NOTE: Add this next running datetime that not in period to queue
            #   and remove it to running.
            self.running[pipeline.name].remove(next_time)
            heappush(self.queue[pipeline.name], next_time)

            time.sleep(0.2)
            return

        logging.debug(
            f"({pipeline.run_id}) [CORE]: {pipeline.name!r} : {on.cronjob} : "
            f"Closely to run >> {next_time:%Y-%m-%d %H:%M:%S}"
        )

        # NOTE: Release when the time is nearly to schedule time.
        while (duration := get_diff_sec(next_time, tz=tz)) > (15 + 5):
            logging.debug(
                f"({pipeline.run_id}) [CORE]: {pipeline.name!r} : {on.cronjob} "
                f": Sleep until: {duration}"
            )
            time.sleep(15)

        time.sleep(0.5)

        # NOTE: Release parameter that use to change if params has
        #   templating.
        release_params: DictData = {
            "release": {
                "logical_date": next_time,
            },
        }

        # WARNING: Re-create pipeline object that use new running pipeline
        #   ID.
        runner: Pipeline = pipeline.get_running_id(run_id=pipeline.new_run_id)
        rs: Result = runner.execute(
            params=param2template(self.params, release_params),
        )
        logging.debug(
            f"({runner.run_id}) [CORE]: {pipeline.name!r} : {on.cronjob} : "
            f"End release"
        )

        del runner

        # NOTE: remove this release date from running
        self.running[pipeline.name].remove(next_time)

        # IMPORTANT:
        #   Add the next running datetime to pipeline queue
        finish_time: datetime = datetime.now(tz=cron_tz).replace(
            second=0, microsecond=0
        )
        future_running_time: datetime = gen.next
        while (
            future_running_time in self.running[pipeline.name]
            or future_running_time in self.queue[pipeline.name]
            or future_running_time < finish_time
        ):
            future_running_time: datetime = gen.next

        heappush(self.queue[pipeline.name], future_running_time)

        # NOTE: Set parent ID on this result.
        rs.set_parent_run_id(pipeline.run_id)

        # NOTE: Save result to log object saving.
        rs_log: Log = log.model_validate(
            {
                "name": pipeline.name,
                "on": str(on.cronjob),
                "release": next_time,
                "context": rs.context,
                "parent_run_id": rs.run_id,
                "run_id": rs.run_id,
            }
        )
        rs_log.save(excluded=None)

        logging.debug(f"[CORE]: {'-' * 100}")


def queue2str(queue: list[datetime]) -> Iterator[str]:
    return (f"{q:%Y-%m-%d %H:%M:%S}" for q in queue)


@catch_exceptions(cancel_on_failure=True)
def workflow_task(
    pipeline_tasks: list[PipelineTask],
    stop: datetime,
    threads: dict[str, Thread],
) -> CancelJob | None:
    """Workflow task generator that create release pair of pipeline and on to
    the threading in background.

        This workflow task will start every minute at :02 second.

    :param pipeline_tasks:
    :param stop:
    :param threads:
    :rtype: CancelJob | None
    """
    start_date: datetime = datetime.now(tz=tz)
    start_date_minute: datetime = start_date.replace(second=0, microsecond=0)

    if start_date > stop:
        logging.info("[WORKFLOW]: Stop this schedule with datetime stopper.")
        while len(threads) > 0:
            logging.warning(
                "[WORKFLOW]: Waiting pipeline release thread that still "
                "running in background."
            )
            time.sleep(15)
            workflow_long_running_task(threads)
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
            logging.warning(
                f"[WORKFLOW]: Queue is empty for : {task.pipeline.name!r} : "
                f"{task.on.cronjob}"
            )
            continue

        # NOTE: Remove this datetime from queue.
        task.queue[task.pipeline.name].pop(0)

        # NOTE: Create thread name that able to tracking with observe schedule
        #   job.
        thread_name: str = (
            f"{task.pipeline.name}|{str(task.on.cronjob)}|"
            f"{current_running_time:%Y%m%d%H%M}"
        )
        pipe_thread: Thread = Thread(
            target=task.release,
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
    :rtype: None
    """
    logging.debug(
        "[MONITOR]: Start checking long running pipeline release task."
    )
    snapshot_threads = list(threads.keys())
    for t_name in snapshot_threads:

        # NOTE: remove the thread that running success.
        if not threads[t_name].is_alive():
            threads.pop(t_name)


def workflow_control(
    schedules: list[str],
    stop: datetime | None = None,
    externals: DictData | None = None,
) -> list[str]:
    """Workflow scheduler control.

    :param schedules: A list of pipeline names that want to schedule running.
    :param stop: An datetime value that use to stop running schedule.
    :param externals: An external parameters that pass to Loader.
    :rtype: list[str]
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

    # NOTE: Create pair of pipeline and on from schedule model.
    pipeline_tasks: list[PipelineTask] = []
    for name in schedules:
        sch: Schedule = Schedule.from_loader(name, externals=externals)
        pipeline_tasks.extend(
            sch.tasks(start_date_waiting, wf_queue, wf_running, externals)
        )

    # NOTE: This schedule job will start every minute at :02 seconds.
    schedule.every(1).minutes.at(":02").do(
        workflow_task,
        pipeline_tasks=pipeline_tasks,
        stop=stop
        or (
            start_date
            + timedelta(
                **json.loads(
                    os.getenv("WORKFLOW_APP_STOP_BOUNDARY_DELTA")
                    or '{"minutes": 5, "seconds": 20}'
                )
            )
        ),
        threads=thread_releases,
    ).tag("control")

    # NOTE: Checking zombie task with schedule job will start every 5 minute.
    schedule.every(5).minutes.at(":10").do(
        workflow_long_running_task,
        threads=thread_releases,
    ).tag("monitor")

    # NOTE: Start running schedule
    logging.info(f"[WORKFLOW]: Start schedule: {schedules}")
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

    logging.warning(
        f"Queue: {[list(queue2str(wf_queue[wf])) for wf in wf_queue]}"
    )
    logging.warning(
        f"Running: {[list(queue2str(wf_running[wf])) for wf in wf_running]}"
    )
    return schedules


def workflow(
    stop: datetime | None = None,
    externals: DictData | None = None,
    excluded: list[str] | None = None,
) -> list[str]:
    """Workflow application that running multiprocessing schedule with chunk of
    pipelines that exists in config path.

    :param stop:
    :param excluded:
    :param externals:
    :rtype: list[str]

        This function will get all pipelines that include on value that was
    created in config path and chuck it with WORKFLOW_APP_SCHEDULE_PER_PROCESS
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
    excluded: list[str] = excluded or []

    with ProcessPoolExecutor(
        max_workers=int(os.getenv("WORKFLOW_APP_PROCESS_WORKER") or "2"),
    ) as executor:
        futures: list[Future] = [
            executor.submit(
                workflow_control,
                schedules=[load[0] for load in loader],
                stop=stop,
                externals=(externals or {}),
            )
            for loader in batch(
                Loader.find(Schedule, excluded=excluded),
                n=int(os.getenv("WORKFLOW_APP_SCHEDULE_PER_PROCESS") or "100"),
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
    workflow_rs: list[str] = workflow()
    logging.info(f"Application run success: {workflow_rs}")
