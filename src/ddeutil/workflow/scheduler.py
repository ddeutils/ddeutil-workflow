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
import inspect
import logging
import time
from concurrent.futures import (
    Future,
    ProcessPoolExecutor,
    as_completed,
)
from datetime import datetime, timedelta
from functools import wraps
from textwrap import dedent
from threading import Thread
from typing import Callable, Optional

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
from .conf import Loader, config, get_logger
from .exceptions import WorkflowException
from .on import On
from .utils import (
    batch,
    delay,
    queue2str,
)
from .workflow import Workflow, WorkflowQueue, WorkflowTaskData

P = ParamSpec("P")
logger = get_logger("ddeutil.workflow")

# NOTE: Adjust logging level on the `schedule` package.
logging.getLogger("schedule").setLevel(logging.INFO)


__all__: TupleStr = (
    "Schedule",
    "WorkflowSchedule",
    "workflow_task_release",
    "monitor",
    "schedule_control",
    "schedule_runner",
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
        contain every minute value, it should has only one on value.

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
        queue: dict[str, WorkflowQueue],
        *,
        externals: DictData | None = None,
    ) -> list[WorkflowTaskData]:
        """Return the list of WorkflowTaskData object from the specific input
        datetime that mapping with the on field.

            This task creation need queue to tracking release date already
        mapped or not.

        :param start_date: A start date that get from the workflow schedule.
        :param queue: A mapping of name and list of datetime for queue.
        :param externals: An external parameters that pass to the Loader object.

        :rtype: list[WorkflowTaskData]
        :return: Return the list of WorkflowTaskData object from the specific
            input datetime that mapping with the on field.
        """
        workflow_tasks: list[WorkflowTaskData] = []
        extras: DictData = externals or {}

        # NOTE: Loading workflow model from the name of workflow.
        wf: Workflow = Workflow.from_loader(self.name, externals=extras)
        wf_queue: WorkflowQueue = queue[self.alias]

        # IMPORTANT: Create the default 'on' value if it does not passing
        #   the on field to the Schedule object.
        ons: list[On] = self.on or wf.on.copy()

        for on in ons:

            # NOTE: Create CronRunner instance from the start_date param.
            runner: CronRunner = on.generate(start_date)
            next_running_date = runner.next

            while wf_queue.check_queue(next_running_date):
                next_running_date = runner.next

            workflow_tasks.append(
                WorkflowTaskData(
                    alias=self.alias,
                    workflow=wf,
                    runner=runner,
                    values=self.values,
                ),
            )

        return workflow_tasks


class Schedule(BaseModel):
    """Schedule Pydantic model that use to run with any scheduler package.

        It does not equal the on value in Workflow model but it use same logic
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
        if loader.type != cls:
            raise ValueError(f"Type {loader.type} does not match with {cls}")

        loader_data: DictData = copy.deepcopy(loader.data)

        # NOTE: Add name to loader data
        loader_data["name"] = name.replace(" ", "_")

        return cls.model_validate(obj=loader_data)

    def tasks(
        self,
        start_date: datetime,
        queue: dict[str, WorkflowQueue],
        *,
        externals: DictData | None = None,
    ) -> list[WorkflowTaskData]:
        """Return the list of WorkflowTaskData object from the specific input
        datetime that mapping with the on field from workflow schedule model.

        :param start_date: A start date that get from the workflow schedule.
        :param queue: A mapping of name and list of datetime for queue.
        :type queue: dict[str, WorkflowQueue]
        :param externals: An external parameters that pass to the Loader object.
        :type externals: DictData | None

        :rtype: list[WorkflowTaskData]
        :return: Return the list of WorkflowTaskData object from the specific
            input datetime that mapping with the on field.
        """
        workflow_tasks: list[WorkflowTaskData] = []

        for workflow in self.workflows:

            if workflow.alias not in queue:
                queue[workflow.alias] = WorkflowQueue()

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
            # NOTE: Check the function that want to handle is method or not.
            if inspect.ismethod(func):

                @wraps(func)
                def wrapper(self, *args, **kwargs):
                    return func(self, *args, **kwargs)

                return wrapper

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


@catch_exceptions(cancel_on_failure=True)  # pragma: no cov
def workflow_task_release(
    tasks: list[WorkflowTaskData],
    stop: datetime,
    queue: dict[str, WorkflowQueue],
    threads: dict[str, Thread],
) -> CancelJob | None:
    """Workflow task generator that create release pair of workflow and on to
    the threading in background.

        This workflow task will start every minute at ':02' second.

    :param tasks: A list of WorkflowTaskData object.
    :param stop: A stop datetime object that force stop running scheduler.
    :param queue:
    :param threads:
    :rtype: CancelJob | None
    """
    current_date: datetime = datetime.now(tz=config.tz)

    if current_date > stop.replace(tzinfo=config.tz):
        logger.info("[WORKFLOW]: Stop this schedule with datetime stopper.")
        while len(threads) > 0:
            logger.warning(
                "[WORKFLOW]: Waiting workflow release thread that still "
                "running in background."
            )
            time.sleep(15)
            monitor(threads)
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

        # NOTE: Get incoming datetime queue.
        logger.debug(
            f"[WORKFLOW]: Current queue: {task.workflow.name!r} : "
            f"{list(queue2str(queue[task.alias]))}"
        )

        if (
            len(queue[task.alias])
            > 0
            # and task.runner.date != queue[task.alias][0]
        ):
            logger.debug(
                f"[WORKFLOW]: Skip schedule "
                f"{task.runner.date:%Y-%m-%d %H:%M:%S} "
                f"for : {task.workflow.name!r} : {task.runner.cron}"
            )
            continue

        elif len(queue[task.alias]) == 0:
            logger.warning(
                f"[WORKFLOW]: Queue is empty for : {task.workflow.name!r} : "
                f"{task.runner.cron}"
            )
            continue

        # NOTE: Remove this datetime from queue.
        # queue[task.alias].pop(0)

        # NOTE: Create thread name that able to tracking with observe schedule
        #   job.
        thread_name: str = (
            f"{task.workflow.name}|{str(task.runner.cron)}|"
            f"{task.runner.date:%Y%m%d%H%M}"
        )

        wf_thread: Thread = Thread(
            target=catch_exceptions(cancel_on_failure=True)(task.release),
            kwargs={"queue": queue},
            name=thread_name,
            daemon=True,
        )

        threads[thread_name] = wf_thread

        wf_thread.start()

        delay()

    logger.debug(f"[WORKFLOW]: {'=' * 100}")


def monitor(threads: dict[str, Thread]) -> None:  # pragma: no cov
    """Workflow schedule for monitoring long running thread from the schedule
    control.

    :param threads: A mapping of Thread object and its name.
    :rtype: None
    """
    logger.debug(
        "[MONITOR]: Start checking long running workflow release task."
    )

    snapshot_threads: list[str] = list(threads.keys())
    for t_name in snapshot_threads:

        # NOTE: remove the thread that running success.
        if not threads[t_name].is_alive():
            threads.pop(t_name)


def schedule_control(
    schedules: list[str],
    stop: datetime | None = None,
    externals: DictData | None = None,
) -> list[str]:  # pragma: no cov
    """Scheduler control.

    :param schedules: A list of workflow names that want to schedule running.
    :param stop: An datetime value that use to stop running schedule.
    :param externals: An external parameters that pass to Loader.

    :rtype: list[str]
    """
    # NOTE: Lazy import Scheduler object from the schedule package.
    try:
        from schedule import Scheduler
    except ImportError:
        raise ImportError(
            "Should install schedule package before use this module."
        ) from None

    scheduler: Scheduler = Scheduler()
    start_date: datetime = datetime.now(tz=config.tz)
    queue: dict[str, WorkflowQueue] = {}
    thread_releases: dict[str, Thread] = {}

    start_date_waiting: datetime = start_date.replace(
        second=0, microsecond=0
    ) + timedelta(minutes=1)

    # NOTE: Start create workflow tasks from list of schedule name.
    workflow_tasks: list[WorkflowTaskData] = []
    for name in schedules:
        schedule: Schedule = Schedule.from_loader(name, externals=externals)
        workflow_tasks.extend(
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
            workflow_task_release,
            workflow_tasks=workflow_tasks,
            stop=(stop or (start_date + config.stop_boundary_delta)),
            queue=queue,
            threads=thread_releases,
        )
        .tag("control")
    )

    # NOTE: Checking zombie task with schedule job will start every 5 minute.
    (
        scheduler.every(5)
        .minutes.at(":10")
        .do(
            monitor,
            threads=thread_releases,
        )
        .tag("monitor")
    )

    # NOTE: Start running schedule
    logger.info(f"[SCHEDULE]: Start schedule: {schedules}")

    while True:
        scheduler.run_pending()
        time.sleep(1)

        # NOTE: Break the scheduler when the control job does not exists.
        if not scheduler.get_jobs("control"):
            scheduler.clear("monitor")
            logger.warning(
                f"[SCHEDULE]: Workflow release thread: {thread_releases}"
            )
            logger.warning("[SCHEDULE]: Does not have any schedule jobs !!!")
            break

    logger.warning(
        f"[SCHEDULE]: Queue: {[list(queue2str(queue[wf])) for wf in queue]}"
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
    :param excluded: A list of schedule name that want to excluded from finding.

    :rtype: list[str]

        This function will get all workflows that include on value that was
    created in config path and chuck it with application config variable
    ``WORKFLOW_APP_MAX_SCHEDULE_PER_PROCESS`` env var to multiprocess executor
    pool.

        The current workflow logic that split to process will be below diagram:

        PIPELINES ==> process 01 ==> schedule --> thread of release
                                                  workflow task 01 01
                                              --> thread of release
                                                  workflow task 01 02
                  ==> process 02 ==> schedule --> thread of release
                                                  workflow task 02 01
                                              --> thread of release
                                                  workflow task 02 02
                  ==> ...
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
