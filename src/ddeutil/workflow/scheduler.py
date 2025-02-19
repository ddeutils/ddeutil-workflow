# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""
The main schedule running is ``schedule_runner`` function that trigger the
multiprocess of ``workflow_control`` function for listing schedules on the
config by ``Loader.finds(Schedule)``.

    The ``workflow_control`` is the scheduler function that release 2 schedule
functions; ``workflow_task``, and ``workflow_monitor``.

    ``workflow_control`` --- Every minute at :02 --> ``workflow_task``
                         --- Every 5 minutes     --> ``workflow_monitor``

    The ``workflow_task`` will run ``task.release`` method in threading object
for multithreading strategy. This ``release`` method will run only one crontab
value with the on field.
"""
from __future__ import annotations

import copy
import logging
import time
from concurrent.futures import (
    Future,
    ProcessPoolExecutor,
    as_completed,
)
from datetime import datetime, timedelta
from functools import wraps
from heapq import heappop, heappush
from textwrap import dedent
from threading import Thread
from typing import Callable, Optional, TypedDict

from pydantic import BaseModel, Field
from pydantic.functional_validators import field_validator, model_validator
from typing_extensions import Self

try:
    from typing import ParamSpec
except ImportError:
    from typing_extensions import ParamSpec

try:
    from schedule import CancelJob
except ImportError:  # pragma: no cov
    CancelJob = None

from .__cron import CronRunner
from .__types import DictData, TupleStr
from .conf import Loader, Log, config, get_log, get_logger
from .cron import On
from .exceptions import WorkflowException
from .utils import (
    batch,
    delay,
)
from .workflow import Release, ReleaseQueue, Workflow, WorkflowTask

P = ParamSpec("P")
logger = get_logger("ddeutil.workflow")

# NOTE: Adjust logging level on the `schedule` package.
logging.getLogger("schedule").setLevel(logging.INFO)


__all__: TupleStr = (
    "Schedule",
    "WorkflowSchedule",
    "schedule_task",
    "monitor",
    "schedule_control",
    "schedule_runner",
    "ReleaseThreads",
    "ReleaseThread",
)


class WorkflowSchedule(BaseModel):
    """Workflow Schedule Pydantic model that use to keep workflow model for
    the Schedule model. it should not use Workflow model directly because on the
    schedule config it can adjust crontab value that different from the Workflow
    model.
    """

    alias: Optional[str] = Field(
        default=None,
        description="An alias name of workflow that use for schedule model.",
    )
    name: str = Field(description="A workflow name.")
    on: list[On] = Field(
        default_factory=list,
        description="An override the list of On object values.",
    )
    values: DictData = Field(
        default_factory=dict,
        description=(
            "A value that want to pass to the workflow parameters when "
            "calling release method."
        ),
        alias="params",
    )

    @model_validator(mode="before")
    def __prepare_before__(cls, values: DictData) -> DictData:
        """Prepare incoming values before validating with model fields.

        :rtype: DictData
        """
        # VALIDATE: Prepare a workflow name that should not include space.
        if name := values.get("name"):
            values["name"] = name.replace(" ", "_")

        # VALIDATE: Add default the alias field with the name.
        if not values.get("alias"):
            values["alias"] = values.get("name")

        cls.__bypass_on(values)
        return values

    @classmethod
    def __bypass_on(cls, data: DictData) -> DictData:
        """Bypass and prepare the on data to loaded config data.

        :param data: A data that want to validate for model initialization.

        :rtype: DictData
        """
        if on := data.pop("on", []):

            if isinstance(on, str):
                on: list[str] = [on]

            if any(not isinstance(n, (dict, str)) for n in on):
                raise TypeError("The ``on`` key should be list of str or dict")

            # NOTE: Pass on value to Loader and keep on model object to on
            #   field.
            data["on"] = [
                Loader(n, externals={}).data if isinstance(n, str) else n
                for n in on
            ]

        return data

    @field_validator("on", mode="after")
    def __on_no_dup__(cls, value: list[On]) -> list[On]:
        """Validate the on fields should not contain duplicate values and if it
        contains every minute value, it should have only one on value.

        :rtype: list[On]
        """
        set_ons: set[str] = {str(on.cronjob) for on in value}
        if len(set_ons) != len(value):
            raise ValueError(
                "The on fields should not contain duplicate on value."
            )

        if len(set_ons) > config.max_on_per_workflow:
            raise ValueError(
                f"The number of the on should not more than "
                f"{config.max_on_per_workflow} crontab."
            )

        return value

    def tasks(
        self,
        start_date: datetime,
        queue: dict[str, ReleaseQueue],
        *,
        externals: DictData | None = None,
    ) -> list[WorkflowTask]:
        """Return the list of WorkflowTask object from the specific input
        datetime that mapping with the on field.

            This task creation need queue to tracking release date already
        mapped or not.

        :param start_date: A start date that get from the workflow schedule.
        :param queue: A mapping of name and list of datetime for queue.
        :param externals: An external parameters that pass to the Loader object.

        :rtype: list[WorkflowTask]
        :return: Return the list of WorkflowTask object from the specific
            input datetime that mapping with the on field.
        """
        workflow_tasks: list[WorkflowTask] = []
        extras: DictData = externals or {}

        # NOTE: Loading workflow model from the name of workflow.
        wf: Workflow = Workflow.from_loader(self.name, externals=extras)
        wf_queue: ReleaseQueue = queue[self.alias]

        # IMPORTANT: Create the default 'on' value if it does not pass the `on`
        #   field to the Schedule object.
        ons: list[On] = self.on or wf.on.copy()

        for on in ons:

            # NOTE: Create CronRunner instance from the start_date param.
            runner: CronRunner = on.generate(start_date)
            next_running_date = runner.next

            while wf_queue.check_queue(next_running_date):
                next_running_date = runner.next

            workflow_tasks.append(
                WorkflowTask(
                    alias=self.alias,
                    workflow=wf,
                    runner=runner,
                    values=self.values,
                ),
            )

        return workflow_tasks


class Schedule(BaseModel):
    """Schedule Pydantic model that use to run with any scheduler package.

        It does not equal the on value in Workflow model, but it uses same logic
    to running release date with crontab interval.
    """

    desc: Optional[str] = Field(
        default=None,
        description=(
            "A schedule description that can be string of markdown content."
        ),
    )
    workflows: list[WorkflowSchedule] = Field(
        default_factory=list,
        description="A list of WorkflowSchedule models.",
    )

    @field_validator("desc", mode="after")
    def __dedent_desc__(cls, value: str) -> str:
        """Prepare description string that was created on a template.

        :param value: A description string value that want to dedent.

        :rtype: str
        """
        return dedent(value)

    @classmethod
    def from_loader(
        cls,
        name: str,
        externals: DictData | None = None,
    ) -> Self:
        """Create Schedule instance from the Loader object that only receive
        an input schedule name. The loader object will use this schedule name to
        searching configuration data of this schedule model in conf path.

        :param name: A schedule name that want to pass to Loader object.
        :param externals: An external parameters that want to pass to Loader
            object.

        :rtype: Self
        """
        loader: Loader = Loader(name, externals=(externals or {}))

        # NOTE: Validate the config type match with current connection model
        if loader.type != cls.__name__:
            raise ValueError(f"Type {loader.type} does not match with {cls}")

        loader_data: DictData = copy.deepcopy(loader.data)

        # NOTE: Add name to loader data
        loader_data["name"] = name.replace(" ", "_")

        return cls.model_validate(obj=loader_data)

    def tasks(
        self,
        start_date: datetime,
        queue: dict[str, ReleaseQueue],
        *,
        externals: DictData | None = None,
    ) -> list[WorkflowTask]:
        """Return the list of WorkflowTask object from the specific input
        datetime that mapping with the on field from workflow schedule model.

        :param start_date: A start date that get from the workflow schedule.
        :param queue: A mapping of name and list of datetime for queue.
        :type queue: dict[str, ReleaseQueue]
        :param externals: An external parameters that pass to the Loader object.
        :type externals: DictData | None

        :rtype: list[WorkflowTask]
        :return: Return the list of WorkflowTask object from the specific
            input datetime that mapping with the on field.
        """
        workflow_tasks: list[WorkflowTask] = []

        for workflow in self.workflows:

            if workflow.alias not in queue:
                queue[workflow.alias] = ReleaseQueue()

            workflow_tasks.extend(
                workflow.tasks(start_date, queue=queue, externals=externals)
            )

        return workflow_tasks


ReturnCancelJob = Callable[P, Optional[CancelJob]]
DecoratorCancelJob = Callable[[ReturnCancelJob], ReturnCancelJob]


def catch_exceptions(cancel_on_failure: bool = False) -> DecoratorCancelJob:
    """Catch exception error from scheduler job that running with schedule
    package and return CancelJob if this function raise an error.

    :param cancel_on_failure: A flag that allow to return the CancelJob or not
        it will raise.

    :rtype: DecoratorCancelJob
    """

    def decorator(func: ReturnCancelJob) -> ReturnCancelJob:  # pragma: no cov
        try:

            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper

        except Exception as err:
            logger.exception(err)
            if cancel_on_failure:
                return CancelJob
            raise err

    return decorator


class ReleaseThread(TypedDict):
    thread: Thread
    start_date: datetime


ReleaseThreads = dict[str, ReleaseThread]


@catch_exceptions(cancel_on_failure=True)
def schedule_task(
    tasks: list[WorkflowTask],
    stop: datetime,
    queue: dict[str, ReleaseQueue],
    threads: ReleaseThreads,
    log: type[Log],
) -> CancelJob | None:
    """Workflow task generator that create release pair of workflow and on to
    the threading in background.

        This workflow task will start every minute at ':02' second.

    :param tasks: A list of WorkflowTask object.
    :param stop: A stop datetime object that force stop running scheduler.
    :param queue: A mapping of alias name and ReleaseQueue object.
    :param threads: A mapping of alias name and Thread object.
    :param log: A log class that want to make log object.

    :rtype: CancelJob | None
    """
    current_date: datetime = datetime.now(tz=config.tz)
    if current_date > stop.replace(tzinfo=config.tz):
        return CancelJob

    # IMPORTANT:
    #       Filter workflow & on that should to run with `workflow_release`
    #   function. It will deplicate running with different schedule value
    #   because I use current time in this condition.
    #
    #       For example, if a workflow A queue has '00:02:00' time that
    #   should to run and its schedule has '*/2 * * * *' and '*/35 * * * *'.
    #   This condition will release with 2 threading job.
    #
    #   '00:02:00'  --> '*/2 * * * *'   --> running
    #               --> '*/35 * * * *'  --> skip
    #
    for task in tasks:

        q: ReleaseQueue = queue[task.alias]

        # NOTE: Start adding queue and move the runner date in the WorkflowTask.
        task.queue(stop, q, log=log)

        # NOTE: Get incoming datetime queue.
        logger.debug(f"[WORKFLOW]: Queue: {task.alias!r} : {list(q.queue)}")

        # VALIDATE: Check the queue is empty or not.
        if not q.is_queued:
            logger.warning(
                f"[WORKFLOW]: Queue is empty for : {task.alias!r} : "
                f"{task.runner.cron}"
            )
            continue

        # VALIDATE: Check this task is the first release in the queue or not.
        current_release: datetime = current_date.replace(
            second=0, microsecond=0
        )
        if (first_date := q.first_queue.date) != current_release:
            logger.debug(
                f"[WORKFLOW]: Skip schedule "
                f"{first_date:%Y-%m-%d %H:%M:%S} for : {task.alias!r}"
            )
            continue

        # NOTE: Pop the latest release and push it to running.
        release: Release = heappop(q.queue)
        heappush(q.running, release)

        logger.info(
            f"[WORKFLOW]: Start thread: '{task.alias}|"
            f"{release.date:%Y%m%d%H%M}'"
        )

        # NOTE: Create thread name that able to tracking with observe schedule
        #   job.
        thread_name: str = f"{task.alias}|{release.date:%Y%m%d%H%M}"
        thread: Thread = Thread(
            target=catch_exceptions(cancel_on_failure=True)(task.release),
            kwargs={"release": release, "queue": q, "log": log},
            name=thread_name,
            daemon=True,
        )

        threads[thread_name] = {
            "thread": thread,
            "start_date": datetime.now(tz=config.tz),
        }

        thread.start()

        delay()

    logger.debug(f"[SCHEDULE]: End schedule release {'=' * 80}")


def monitor(threads: ReleaseThreads) -> None:  # pragma: no cov
    """Monitoring function that running every five minute for track long-running
    thread instance from the schedule_control function that run every minute.

    :param threads: A mapping of Thread object and its name.
    :type threads: ReleaseThreads
    """
    logger.debug(
        "[MONITOR]: Start checking long running workflow release task."
    )

    snapshot_threads: list[str] = list(threads.keys())
    for t_name in snapshot_threads:

        thread_release: ReleaseThread = threads[t_name]

        # NOTE: remove the thread that running success.
        if not thread_release["thread"].is_alive():
            threads.pop(t_name)


def schedule_control(
    schedules: list[str],
    stop: datetime | None = None,
    externals: DictData | None = None,
    *,
    log: type[Log] | None = None,
) -> list[str]:  # pragma: no cov
    """Scheduler control function that running every minute.

    :param schedules: A list of workflow names that want to schedule running.
    :param stop: A datetime value that use to stop running schedule.
    :param externals: An external parameters that pass to Loader.
    :param log:

    :rtype: list[str]
    """
    # NOTE: Lazy import Scheduler object from the schedule package.
    try:
        from schedule import Scheduler
    except ImportError:
        raise ImportError(
            "Should install schedule package before use this module."
        ) from None

    log: type[Log] = log or get_log()
    scheduler: Scheduler = Scheduler()
    start_date: datetime = datetime.now(tz=config.tz)
    stop_date: datetime = stop or (start_date + config.stop_boundary_delta)

    # IMPORTANT: Create main mapping of queue and thread object.
    queue: dict[str, ReleaseQueue] = {}
    threads: ReleaseThreads = {}

    start_date_waiting: datetime = start_date.replace(
        second=0, microsecond=0
    ) + timedelta(minutes=1)

    # NOTE: Start create workflow tasks from list of schedule name.
    tasks: list[WorkflowTask] = []
    for name in schedules:
        schedule: Schedule = Schedule.from_loader(name, externals=externals)
        tasks.extend(
            schedule.tasks(
                start_date_waiting,
                queue=queue,
                externals=externals,
            ),
        )

    # NOTE: This schedule job will start every minute at :02 seconds.
    (
        scheduler.every(1)
        .minutes.at(":02")
        .do(
            schedule_task,
            tasks=tasks,
            stop=stop_date,
            queue=queue,
            threads=threads,
            log=log,
        )
        .tag("control")
    )

    # NOTE: Checking zombie task with schedule job will start every 5 minute.
    (
        scheduler.every(5)
        .minutes.at(":10")
        .do(
            monitor,
            threads=threads,
        )
        .tag("monitor")
    )

    # NOTE: Start running schedule
    logger.info(
        f"[SCHEDULE]: Schedule: {schedules} with stopper: "
        f"{stop_date:%Y-%m-%d %H:%M:%S}"
    )

    while True:
        scheduler.run_pending()
        time.sleep(1)

        # NOTE: Break the scheduler when the control job does not exist.
        if not scheduler.get_jobs("control"):
            scheduler.clear("monitor")

            while len(threads) > 0:
                logger.warning(
                    "[SCHEDULE]: Waiting schedule release thread that still "
                    "running in background."
                )
                delay(15)
                monitor(threads)

            break

    logger.warning(
        f"[SCHEDULE]: Queue: {[list(queue[wf].queue) for wf in queue]}"
    )
    return schedules


def schedule_runner(
    stop: datetime | None = None,
    externals: DictData | None = None,
    excluded: list[str] | None = None,
) -> list[str]:  # pragma: no cov
    """Schedule runner function for start submit the ``schedule_control`` func
    in multiprocessing pool with chunk of schedule config that exists in config
    path by ``WORKFLOW_APP_MAX_SCHEDULE_PER_PROCESS``.

    :param stop: A stop datetime object that force stop running scheduler.
    :param externals:
    :param excluded: A list of schedule name that want to exclude from finding.

    :rtype: list[str]

        This function will get all workflows that include on value that was
    created in config path and chuck it with application config variable
    ``WORKFLOW_APP_MAX_SCHEDULE_PER_PROCESS`` env var to multiprocess executor
    pool.

        The current workflow logic that split to process will be below diagram:

        MAIN ==> process 01 ==> schedule --> thread of release task 01 01
                                        --> thread of release task 01 02
                            ==> schedule --> thread of release task 02 01
                                        --> thread of release task 02 02
            ==> process 02
    """
    results: list[str] = []

    with ProcessPoolExecutor(
        max_workers=config.max_schedule_process,
    ) as executor:

        futures: list[Future] = [
            executor.submit(
                schedule_control,
                schedules=[load[0] for load in loader],
                stop=stop,
                externals=(externals or {}),
            )
            for loader in batch(
                Loader.finds(Schedule, excluded=excluded),
                n=config.max_schedule_per_process,
            )
        ]

        for future in as_completed(futures):

            # NOTE: Raise error when it has any error from schedule_control.
            if err := future.exception():
                logger.error(str(err))
                raise WorkflowException(str(err)) from err

            results.extend(future.result(timeout=1))

    return results
