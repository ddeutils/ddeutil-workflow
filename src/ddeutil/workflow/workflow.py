# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""The main schedule running is ``workflow_runner`` function that trigger the
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
import time
from concurrent.futures import (
    Future,
    ThreadPoolExecutor,
    as_completed,
)
from dataclasses import field
from datetime import datetime, timedelta
from enum import Enum
from functools import partial, total_ordering
from heapq import heappop, heappush
from queue import Queue
from textwrap import dedent
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.dataclasses import dataclass
from pydantic.functional_validators import field_validator, model_validator
from typing_extensions import Self

from .__cron import CronJob, CronRunner
from .__types import DictData, TupleStr
from .conf import Loader, config, get_logger
from .cron import On
from .exceptions import JobException, WorkflowException
from .job import Job
from .logs import Log, get_log
from .params import Param
from .result import Result
from .templates import has_template, param2template
from .utils import (
    cut_id,
    gen_id,
    get_dt_now,
    reach_next_minute,
    wait_to_next_minute,
)

logger = get_logger("ddeutil.workflow")

__all__: TupleStr = (
    "Release",
    "ReleaseQueue",
    "ReleaseType",
    "Workflow",
    "WorkflowTask",
)


class ReleaseType(str, Enum):
    """Release Type Enum support the type field on the Release dataclass."""

    DEFAULT: str = "manual"
    TASK: str = "task"
    POKE: str = "poking"


@total_ordering
@dataclass(
    config=ConfigDict(arbitrary_types_allowed=True, use_enum_values=True)
)
class Release:
    """Release Pydantic dataclass object that use for represent
    the release data that use with the `workflow.release` method."""

    date: datetime
    offset: float
    end_date: datetime
    runner: CronRunner
    type: ReleaseType = field(default=ReleaseType.DEFAULT)

    def __repr__(self) -> str:
        return repr(f"{self.date:%Y-%m-%d %H:%M:%S}")

    def __str__(self) -> str:
        return f"{self.date:%Y-%m-%d %H:%M:%S}"

    @classmethod
    def from_dt(cls, dt: datetime | str) -> Self:
        """Construct Release via datetime object only.

        :param dt: A datetime object.

        :rtype: Self
        """
        if isinstance(dt, str):
            dt: datetime = datetime.fromisoformat(dt)
        elif not isinstance(dt, datetime):
            raise TypeError(
                "The `from_dt` need argument type be str or datetime only."
            )

        return cls(
            date=dt,
            offset=0,
            end_date=dt + timedelta(days=1),
            runner=CronJob("* * * * *").schedule(dt.replace(tzinfo=config.tz)),
        )

    def __eq__(self, other: Release | datetime) -> bool:
        """Override equal property that will compare only the same type or
        datetime.
        """
        if isinstance(other, self.__class__):
            return self.date == other.date
        elif isinstance(other, datetime):
            return self.date == other
        return NotImplemented

    def __lt__(self, other: Release | datetime) -> bool:
        """Override equal property that will compare only the same type or
        datetime.
        """
        if isinstance(other, self.__class__):
            return self.date < other.date
        elif isinstance(other, datetime):
            return self.date < other
        return NotImplemented


@dataclass
class ReleaseQueue:
    """Workflow Queue object that is management of Release objects."""

    queue: list[Release] = field(default_factory=list)
    running: list[Release] = field(default_factory=list)
    complete: list[Release] = field(default_factory=list)

    @classmethod
    def from_list(
        cls, queue: list[datetime] | list[Release] | None = None
    ) -> Self:
        """Construct ReleaseQueue object from an input queue value that passing
        with list of datetime or list of Release.

        :raise TypeError: If the type of input queue does not valid.

        :rtype: Self
        """
        if queue is None:
            return cls()

        if isinstance(queue, list):

            if all(isinstance(q, datetime) for q in queue):
                return cls(queue=[Release.from_dt(q) for q in queue])

            if all(isinstance(q, Release) for q in queue):
                return cls(queue=queue)

        raise TypeError(
            "Type of the queue does not valid with ReleaseQueue "
            "or list of datetime or list of Release."
        )

    @property
    def is_queued(self) -> bool:
        """Return True if it has workflow release object in the queue.

        :rtype: bool
        """
        return len(self.queue) > 0

    @property
    def first_queue(self) -> Release:
        """Check an input Release object is the first value of the
        waiting queue.

        :rtype: bool
        """
        return self.queue[0]

    def check_queue(self, value: Release | datetime) -> bool:
        """Check a Release value already exists in list of tracking
        queues.

        :param value: A Release object that want to check it already in
            queues.

        :rtype: bool
        """
        if isinstance(value, datetime):
            value = Release.from_dt(value)

        return (
            (value in self.queue)
            or (value in self.running)
            or (value in self.complete)
        )

    def remove_running(self, value: Release) -> Self:
        """Remove Release in the running queue if it exists.

        :rtype: Self
        """
        if value in self.running:
            self.running.remove(value)

        return self

    def mark_complete(self, value: Release) -> Self:
        """Push Release to the complete queue.

        :rtype: Self
        """
        heappush(self.complete, value)

        # NOTE: Remove complete queue on workflow that keep more than the
        #   maximum config.
        num_complete_delete: int = (
            len(self.complete) - config.max_queue_complete_hist
        )

        if num_complete_delete > 0:
            for _ in range(num_complete_delete):
                heappop(self.complete)

        return self


class Workflow(BaseModel):
    """Workflow Pydantic model.

        This is the main future of this project because it uses to be workflow
    data for running everywhere that you want or using it to scheduler task in
    background. It uses lightweight coding line from Pydantic Model and enhance
    execute method on it.
    """

    name: str = Field(description="A workflow name.")
    desc: Optional[str] = Field(
        default=None,
        description=(
            "A workflow description that can be string of markdown content."
        ),
    )
    params: dict[str, Param] = Field(
        default_factory=dict,
        description="A parameters that need to use on this workflow.",
    )
    on: list[On] = Field(
        default_factory=list,
        description="A list of On instance for this workflow schedule.",
    )
    jobs: dict[str, Job] = Field(
        default_factory=dict,
        description="A mapping of job ID and job model that already loaded.",
    )

    @classmethod
    def from_loader(
        cls,
        name: str,
        externals: DictData | None = None,
    ) -> Self:
        """Create Workflow instance from the Loader object that only receive
        an input workflow name. The loader object will use this workflow name to
        searching configuration data of this workflow model in conf path.

        :raise ValueError: If the type does not match with current object.

        :param name: A workflow name that want to pass to Loader object.
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

        # NOTE: Prepare `on` data
        cls.__bypass_on(loader_data, externals=externals)
        return cls.model_validate(obj=loader_data)

    @classmethod
    def __bypass_on(
        cls,
        data: DictData,
        externals: DictData | None = None,
    ) -> DictData:
        """Bypass the on data to loaded config data.

        :param data:
        :param externals:
        :rtype: DictData
        """
        if on := data.pop("on", []):
            if isinstance(on, str):
                on = [on]
            if any(not isinstance(i, (dict, str)) for i in on):
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

    @model_validator(mode="before")
    def __prepare_model_before__(cls, values: DictData) -> DictData:
        """Prepare the params key in the data model before validating."""
        # NOTE: Prepare params type if it is passing with only type value.
        if params := values.pop("params", {}):
            values["params"] = {
                p: (
                    {"type": params[p]}
                    if isinstance(params[p], str)
                    else params[p]
                )
                for p in params
            }
        return values

    @field_validator("desc", mode="after")
    def __dedent_desc__(cls, value: str) -> str:
        """Prepare description string that was created on a template.

        :param value: A description string value that want to dedent.
        :rtype: str
        """
        return dedent(value)

    @field_validator("on", mode="after")
    def __on_no_dup_and_reach_limit__(cls, value: list[On]) -> list[On]:
        """Validate the on fields should not contain duplicate values and if it
        contains the every minute value more than one value, it will remove to
        only one value.

        :raise ValueError: If it has some duplicate value.

        :param value: A list of on object.

        :rtype: list[On]
        """
        set_ons: set[str] = {str(on.cronjob) for on in value}
        if len(set_ons) != len(value):
            raise ValueError(
                "The on fields should not contain duplicate on value."
            )

        # WARNING:
        # if '* * * * *' in set_ons and len(set_ons) > 1:
        #     raise ValueError(
        #         "If it has every minute cronjob on value, it should have "
        #         "only one value in the on field."
        #     )

        if len(set_ons) > config.max_on_per_workflow:
            raise ValueError(
                f"The number of the on should not more than "
                f"{config.max_on_per_workflow} crontab."
            )
        return value

    @model_validator(mode="after")
    def __validate_jobs_need__(self) -> Self:
        """Validate each need job in any jobs should exist.

        :raise WorkflowException: If it has not exists need value in this
            workflow job.

        :rtype: Self
        """
        for job in self.jobs:
            if not_exist := [
                need for need in self.jobs[job].needs if need not in self.jobs
            ]:
                raise WorkflowException(
                    f"The needed jobs: {not_exist} do not found in "
                    f"{self.name!r}."
                )

            # NOTE: update a job id with its job id from workflow template
            self.jobs[job].id = job

        # VALIDATE: Validate workflow name should not dynamic with params
        #   template.
        if has_template(self.name):
            raise ValueError(
                f"Workflow name should not has any template, please check, "
                f"{self.name!r}."
            )

        return self

    def job(self, name: str) -> Job:
        """Return this workflow's jobs that passing with the Job model.

        :param name: A job name that want to get from a mapping of job models.
        :type name: str

        :rtype: Job
        :return: A job model that exists on this workflow by input name.
        """
        if name not in self.jobs:
            raise ValueError(
                f"A Job {name!r} does not exists in this workflow, "
                f"{self.name!r}"
            )
        return self.jobs[name]

    def parameterize(self, params: DictData) -> DictData:
        """Prepare a passing parameters before use it in execution process.
        This method will validate keys of an incoming params with this object
        necessary params field and then create a jobs key to result mapping
        that will keep any execution result from its job.

            ... {
            ...     "params": <an-incoming-params>,
            ...     "jobs": {}
            ... }

        :param params: A parameter mapping that receive from workflow execution.
        :type params: DictData

        :raise WorkflowException: If parameter value that want to validate does
            not include the necessary parameter that had required flag.

        :rtype: DictData
        :return: The parameter value that validate with its parameter fields and
            adding jobs key to this parameter.
        """
        # VALIDATE: Incoming params should have keys that set on this workflow.
        if check_key := tuple(
            f"{k!r}"
            for k in self.params
            if (k not in params and self.params[k].required)
        ):
            raise WorkflowException(
                f"Required Param on this workflow setting does not set: "
                f"{', '.join(check_key)}."
            )

        # NOTE: Mapping type of param before adding it to the ``params`` key.
        return {
            "params": (
                params
                | {
                    k: self.params[k].receive(params[k])
                    for k in params
                    if k in self.params
                }
            ),
            "jobs": {},
        }

    def release(
        self,
        release: datetime | Release,
        params: DictData,
        *,
        run_id: str | None = None,
        log: type[Log] = None,
        queue: ReleaseQueue | None = None,
        override_log_name: str | None = None,
    ) -> Result:
        """Release the workflow execution with overriding parameter with the
        release templating that include logical date (release date), execution
        date, or running id to the params.

            This method allow workflow use log object to save the execution
        result to log destination like file log to the local `/logs` directory.

        Steps:
            - Initialize ReleaseQueue and Release if they do not pass.
            - Create release data for pass to parameter templating function.
            - Execute this workflow with mapping release data to its parameters.
            - Writing result log
            - Remove this release on the running queue
            - Push this release to complete queue

        :param release: A release datetime or Release object.
        :param params: A workflow parameter that pass to execute method.
        :param queue: A ReleaseQueue that use for mark complete.
        :param run_id: A workflow running ID for this release.
        :param log: A log class that want to save the execution result.
        :param queue: A ReleaseQueue object.
        :param override_log_name: An override logging name that use instead
            the workflow name.

        :rtype: Result
        """
        log: type[Log] = log or get_log()
        name: str = override_log_name or self.name
        run_id: str = run_id or gen_id(name, unique=True)
        rs_release: Result = Result(run_id=run_id)

        if queue is not None and not isinstance(queue, ReleaseQueue):
            raise TypeError(
                "The queue argument should be ReleaseQueue object only."
            )

        # VALIDATE: Change release value to Release object.
        rs_release_type: str = "release"
        if isinstance(release, datetime):
            rs_release_type: str = "datetime"
            release: Release = Release.from_dt(release)

        logger.debug(
            f"({cut_id(run_id)}) [RELEASE]: Start release - {name!r} : "
            f"{release.date:%Y-%m-%d %H:%M:%S}"
        )

        # NOTE: Release parameters that use to templating on the schedule
        #   config data.
        release_params: DictData = {
            "release": {
                "logical_date": release.date,
                "execute_date": datetime.now(tz=config.tz),
                "run_id": run_id,
                "timezone": config.tz,
            }
        }

        # NOTE: Execute workflow with templating params from release mapping.
        rs: Result = self.execute(
            params=param2template(params, release_params),
            run_id=run_id,
        )
        logger.debug(
            f"({cut_id(run_id)}) [RELEASE]: End release - {name!r} : "
            f"{release.date:%Y-%m-%d %H:%M:%S}"
        )

        rs.set_parent_run_id(run_id)

        # NOTE: Saving execution result to destination of the input log object.
        logger.debug(f"({cut_id(run_id)}) [LOG]: Writing log: {name!r}.")
        (
            log.model_validate(
                {
                    "name": name,
                    "release": release.date,
                    "type": release.type,
                    "context": rs.context,
                    "parent_run_id": rs.parent_run_id,
                    "run_id": rs.run_id,
                }
            ).save(excluded=None)
        )

        # NOTE: Remove this release from running.
        if queue is not None:
            queue.remove_running(release)
            queue.mark_complete(release)

        # NOTE: Remove the params key from the result context for deduplicate.
        context: dict[str, Any] = rs.context
        context.pop("params")

        return rs_release.catch(
            status=0,
            context={
                "params": params,
                "release": {
                    "status": "success",
                    "type": rs_release_type,
                    "logical_date": release.date,
                    "release": release,
                },
                "outputs": context,
            },
        )

    def queue(
        self,
        offset: float,
        end_date: datetime,
        queue: ReleaseQueue,
        log: type[Log],
        *,
        force_run: bool = False,
    ) -> ReleaseQueue:
        """Generate Release from all on values from the on field and store them
        to the ReleaseQueue object.

        Steps:
            - For-loop all the on value in the on field.
            - Create Release object from the current date that not reach the end
              date.
            - Check this release do not store on the release queue object.
              Generate the next date if it exists.
            - Push this release to the release queue

        :param offset: An offset in second unit for time travel.
        :param end_date: An end datetime object.
        :param queue: A workflow queue object.
        :param log: A log class that want to make log object.
        :param force_run: A flag that allow to release workflow if the log with
            that release was pointed.

        :rtype: ReleaseQueue
        """
        for on in self.on:

            runner: CronRunner = on.next(
                get_dt_now(tz=config.tz, offset=offset).replace(microsecond=0)
            )

            # NOTE: Skip this runner date if it more than the end date.
            if runner.date > end_date:
                continue

            workflow_release = Release(
                date=runner.date,
                offset=offset,
                end_date=end_date,
                runner=runner,
                type=ReleaseType.POKE,
            )

            while queue.check_queue(workflow_release) or (
                log.is_pointed(name=self.name, release=workflow_release.date)
                and not force_run
            ):
                workflow_release = Release(
                    date=runner.next,
                    offset=offset,
                    end_date=end_date,
                    runner=runner,
                    type=ReleaseType.POKE,
                )

            if runner.date > end_date:
                continue

            # NOTE: Push the Release object to queue.
            heappush(queue.queue, workflow_release)

        return queue

    def poke(
        self,
        start_date: datetime | None = None,
        params: DictData | None = None,
        *,
        run_id: str | None = None,
        periods: int = 1,
        log: Log | None = None,
        force_run: bool = False,
        timeout: int = 1800,
    ) -> list[Result]:
        """Poke this workflow with start datetime value that passing to its
        ``on`` field with threading executor pool for executing with all its
        schedules that was set on the `on` value.

            This method will observe its schedule that nearing to run with the
        ``self.release()`` method.

            The limitation of this method is not allow run a date that less
        than the current date.

        :param start_date: A start datetime object.
        :param params: A parameters that want to pass to the release method.
        :param run_id: A workflow running ID for this poke.
        :param periods: A periods in minutes value that use to run this poking.
        :param log: A log object that want to use on this poking process.
        :param force_run: A flag that allow to release workflow if the log with
            that release was pointed.
        :param timeout: A second value for timeout while waiting all futures
            run completely.

        :rtype: list[Result]
        :return: A list of all results that return from ``self.release`` method.
        """
        log: type[Log] = log or get_log()
        run_id: str = run_id or gen_id(self.name, unique=True)

        # VALIDATE: Check the periods value should gather than 0.
        if periods <= 0:
            raise WorkflowException(
                "The period of poking should be int and grater or equal than 1."
            )

        # NOTE: If this workflow does not set the on schedule, it will return
        #   empty result.
        if len(self.on) == 0:
            logger.info(
                f"({cut_id(run_id)}) [POKING]: {self.name!r} does not have any "
                f"schedule to run."
            )
            return []

        # NOTE: Create the current date that change microsecond to 0
        current_date: datetime = datetime.now(tz=config.tz).replace(
            microsecond=0
        )

        # NOTE: Create start_date and offset variables.
        if start_date and start_date <= current_date:
            start_date = start_date.replace(tzinfo=config.tz).replace(
                microsecond=0
            )
            offset: float = (current_date - start_date).total_seconds()
        else:
            # NOTE: Force change start date if it gathers than the current date,
            #   or it does not pass to this method.
            start_date: datetime = current_date
            offset: float = 0

        # NOTE: The end date is using to stop generate queue with an input
        #   periods value.
        end_date: datetime = start_date + timedelta(minutes=periods)

        logger.info(
            f"({cut_id(run_id)}) [POKING]: Start Poking: {self.name!r} from "
            f"{start_date:%Y-%m-%d %H:%M:%S} to {end_date:%Y-%m-%d %H:%M:%S}"
        )

        params: DictData = {} if params is None else params
        results: list[Result] = []

        # NOTE: Create empty ReleaseQueue object.
        q: ReleaseQueue = ReleaseQueue()

        # NOTE: Create reusable partial function and add Release to the release
        #   queue object.
        partial_queue = partial(
            self.queue, offset, end_date, log=log, force_run=force_run
        )
        partial_queue(q)

        # NOTE: Return the empty result if it does not have any Release.
        if not q.is_queued:
            logger.info(
                f"({cut_id(run_id)}) [POKING]: {self.name!r} does not have "
                f"any queue."
            )
            return []

        # NOTE: Start create the thread pool executor for running this poke
        #   process.
        with ThreadPoolExecutor(
            max_workers=config.max_poking_pool_worker,
            thread_name_prefix="wf_poking_",
        ) as executor:

            futures: list[Future] = []

            while q.is_queued:

                # NOTE: Pop the latest Release object from the release queue.
                release: Release = heappop(q.queue)

                if reach_next_minute(release.date, tz=config.tz, offset=offset):
                    logger.debug(
                        f"({cut_id(run_id)}) [POKING]: The latest release, "
                        f"{release.date:%Y-%m-%d %H:%M:%S}, is not able to run "
                        f"on this minute"
                    )
                    heappush(q.queue, release)
                    wait_to_next_minute(get_dt_now(tz=config.tz, offset=offset))

                    # WARNING: I already call queue poking again because issue
                    #   about the every minute crontab.
                    partial_queue(q)
                    continue

                # NOTE: Push the latest Release to the running queue.
                heappush(q.running, release)

                futures.append(
                    executor.submit(
                        self.release,
                        release=release,
                        params=params,
                        log=log,
                        queue=q,
                    )
                )

                partial_queue(q)

            # WARNING: This poking method does not allow to use fail-fast
            #   logic to catching parallel execution result.
            for future in as_completed(futures, timeout=timeout):
                results.append(future.result().set_parent_run_id(run_id))

        return results

    def execute_job(
        self,
        job_id: str,
        params: DictData,
        *,
        run_id: str | None = None,
        raise_error: bool = True,
    ) -> Result:
        """Job execution with passing dynamic parameters from the main workflow
        execution to the target job object via job's ID.

            This execution is the minimum level of execution of this workflow
        model. It different with ``self.execute`` because this method run only
        one job and return with context of this job data.

        :raise WorkflowException: If execute with not exist job's ID.
        :raise WorkflowException: If the job execution raise JobException.
        :raise NotImplementedError: If set raise_error argument to False.

        :param job_id: A job ID that want to execute.
        :param params: A params that was parameterized from workflow execution.
        :param run_id: A workflow running ID for this job execution.
        :param raise_error: A flag that raise error instead catching to result
            if it gets exception from job execution.

        :rtype: Result
        :return: Return the result object that receive the job execution result
            context.
        """
        run_id: str = run_id or gen_id(self.name, unique=True)
        rs: Result = Result(run_id=run_id)

        # VALIDATE: check a job ID that exists in this workflow or not.
        if job_id not in self.jobs:
            raise WorkflowException(
                f"The job: {job_id!r} does not exists in {self.name!r} "
                f"workflow."
            )

        logger.info(
            f"({cut_id(run_id)}) [WORKFLOW]: Start execute job: {job_id!r}"
        )

        # IMPORTANT:
        #   This execution change all job running IDs to the current workflow
        #   execution running ID (with passing run_id to the job execution
        #   argument).
        #
        try:
            job: Job = self.jobs[job_id]
            job.set_outputs(
                job.execute(params=params, run_id=run_id).context,
                to=params,
            )
        except JobException as err:
            logger.error(
                f"({cut_id(run_id)}) [WORKFLOW]: {err.__class__.__name__}: "
                f"{err}"
            )
            if raise_error:
                raise WorkflowException(
                    f"Get job execution error {job_id}: JobException: {err}"
                ) from None
            raise NotImplementedError(
                "Handle error from the job execution does not support yet."
            ) from None

        return rs.catch(status=0, context=params)

    def execute(
        self,
        params: DictData,
        *,
        run_id: str | None = None,
        timeout: int = 0,
    ) -> Result:
        """Execute workflow with passing a dynamic parameters to all jobs that
        included in this workflow model with ``jobs`` field.

            The result of execution process for each job and stages on this
        workflow will keep in dict which able to catch out with all jobs and
        stages by dot annotation.

            For example, when I want to use the output from previous stage, I
        can access it with syntax:

            ... ${job-name}.stages.${stage-id}.outputs.${key}

        :param params: An input parameters that use on workflow execution that
            will parameterize before using it. Default is None.
        :type params: DictData

        :param run_id: A workflow running ID for this job execution.
        :type run_id: str | None (default: None)
        :param timeout: A workflow execution time out in second unit that use
            for limit time of execution and waiting job dependency. This value
            does not force stop the task that still running more than this limit
            time.
        :type timeout: int (default: 0)

        :rtype: Result
        """
        run_id: str = run_id or gen_id(self.name, unique=True)
        logger.info(
            f"({cut_id(run_id)}) [WORKFLOW]: Start Execute: {self.name!r} ..."
        )

        # NOTE: I use this condition because this method allow passing empty
        #   params and I do not want to create new dict object.
        ts: float = time.monotonic()
        rs: Result = Result(run_id=run_id)

        # NOTE: It should not do anything if it does not have job.
        if not self.jobs:
            logger.warning(
                f"({cut_id(run_id)}) [WORKFLOW]: This workflow: {self.name!r} "
                f"does not have any jobs"
            )
            return rs.catch(status=0, context=params)

        # NOTE: Create a job queue that keep the job that want to run after
        #   its dependency condition.
        jq: Queue = Queue()
        for job_id in self.jobs:
            jq.put(job_id)

        # NOTE: Create data context that will pass to any job executions
        #   on this workflow.
        #
        #   {
        #       'params': <input-params>,
        #       'jobs': {},
        #   }
        #
        context: DictData = self.parameterize(params)
        status: int = 0
        try:
            if config.max_job_parallel == 1:
                self.__exec_non_threading(
                    run_id=run_id,
                    context=context,
                    ts=ts,
                    job_queue=jq,
                    timeout=timeout,
                )
            else:
                self.__exec_threading(
                    run_id=run_id,
                    context=context,
                    ts=ts,
                    job_queue=jq,
                    timeout=timeout,
                )
        except WorkflowException as err:
            status: int = 1
            context.update(
                {
                    "error": err,
                    "error_message": f"{err.__class__.__name__}: {err}",
                },
            )
        return rs.catch(status=status, context=context)

    def __exec_threading(
        self,
        run_id: str,
        context: DictData,
        ts: float,
        job_queue: Queue,
        *,
        timeout: int = 0,
        thread_timeout: int = 1800,
    ) -> DictData:
        """Workflow execution by threading strategy that use multithreading.

            If a job need dependency, it will check dependency job ID from
        context data before allow it run.

        :param context: A context workflow data that want to downstream passing.
        :param ts: A start timestamp that use for checking execute time should
            time out.
        :param job_queue: A job queue object.
        :param timeout: A second value unit that bounding running time.
        :param thread_timeout: A timeout to waiting all futures complete.

        :rtype: DictData
        """
        not_timeout_flag: bool = True
        timeout: int = timeout or config.max_job_exec_timeout
        logger.debug(
            f"({cut_id(run_id)}) [WORKFLOW]: Run {self.name!r} with threading."
        )

        # IMPORTANT: The job execution can run parallel and waiting by
        #   needed.
        with ThreadPoolExecutor(
            max_workers=config.max_job_parallel,
            thread_name_prefix="wf_exec_threading_",
        ) as executor:
            futures: list[Future] = []

            while not job_queue.empty() and (
                not_timeout_flag := ((time.monotonic() - ts) < timeout)
            ):
                job_id: str = job_queue.get()
                job: Job = self.jobs[job_id]

                if not job.check_needs(context["jobs"]):
                    job_queue.task_done()
                    job_queue.put(job_id)
                    time.sleep(0.25)
                    continue

                # NOTE: Start workflow job execution with deep copy context data
                #   before release.
                #
                #   Context:
                #   ---
                #   {
                #       'params': <input-params>,
                #       'jobs': { <job's-id>: ... },
                #   }
                #
                futures.append(
                    executor.submit(
                        self.execute_job,
                        job_id,
                        params=context,
                    ),
                )

                # NOTE: Mark this job queue done.
                job_queue.task_done()

            if not_timeout_flag:

                # NOTE: Wait for all items to finish processing by `task_done()`
                #   method.
                job_queue.join()

                for future in as_completed(futures, timeout=thread_timeout):
                    if err := future.exception():
                        logger.error(f"({cut_id(run_id)}) [WORKFLOW]: {err}")
                        raise WorkflowException(str(err))

                    # NOTE: This getting result does not do anything.
                    future.result()

                return context

            for future in futures:
                future.cancel()

        # NOTE: Raise timeout error.
        logger.warning(
            f"({cut_id(run_id)}) [WORKFLOW]: Execution: {self.name!r} "
            f"was timeout."
        )
        raise WorkflowException(f"Execution: {self.name!r} was timeout.")

    def __exec_non_threading(
        self,
        run_id: str,
        context: DictData,
        ts: float,
        job_queue: Queue,
        *,
        timeout: int = 0,
    ) -> DictData:
        """Workflow execution with non-threading strategy that use sequential
        job running and waiting previous job was run successful.

            If a job need dependency, it will check dependency job ID from
        context data before allow it run.

        :param context: A context workflow data that want to downstream passing.
        :param ts: A start timestamp that use for checking execute time should
            time out.
        :param timeout: A second value unit that bounding running time.

        :rtype: DictData
        """
        not_timeout_flag: bool = True
        timeout: int = timeout or config.max_job_exec_timeout
        logger.debug(
            f"({cut_id(run_id)}) [WORKFLOW]: Run {self.name!r} with "
            f"non-threading."
        )

        while not job_queue.empty() and (
            not_timeout_flag := ((time.monotonic() - ts) < timeout)
        ):
            job_id: str = job_queue.get()
            job: Job = self.jobs[job_id]

            # NOTE: Waiting dependency job run successful before release.
            if not job.check_needs(context["jobs"]):
                job_queue.task_done()
                job_queue.put(job_id)
                time.sleep(0.075)
                continue

            # NOTE: Start workflow job execution with deep copy context data
            #   before release. This job execution process will run until
            #   done before checking all execution timeout or not.
            #
            #   {
            #       'params': <input-params>,
            #       'jobs': {},
            #   }
            self.execute_job(job_id=job_id, params=context, run_id=run_id)

            # NOTE: Mark this job queue done.
            job_queue.task_done()

        if not_timeout_flag:

            # NOTE: Wait for all items to finish processing by `task_done()`
            #   method.
            job_queue.join()

            return context

        # NOTE: Raise timeout error.
        logger.warning(
            f"({cut_id(run_id)}) [WORKFLOW]: Execution: {self.name!r} "
            f"was timeout."
        )
        raise WorkflowException(f"Execution: {self.name!r} was timeout.")


@dataclass(config=ConfigDict(arbitrary_types_allowed=True))
class WorkflowTask:
    """Workflow task Pydantic dataclass object that use to keep mapping data and
    workflow model for passing to the multithreading task.

        This dataclass object is mapping 1-to-1 with workflow and cron runner
    objects.

        This dataclass has the release method for itself.

    """

    alias: str
    workflow: Workflow
    runner: CronRunner
    values: DictData = field(default_factory=dict)

    def release(
        self,
        release: datetime | Release | None = None,
        run_id: str | None = None,
        log: type[Log] = None,
        queue: ReleaseQueue | None = None,
    ) -> Result:
        """Release the workflow task data.

        :param release: A release datetime or Release object.
        :param run_id: A workflow running ID for this release.
        :param log: A log class that want to save the execution result.
        :param queue: A ReleaseQueue object that use to mark complete.

        :rtype: Result
        """
        log: type[Log] = log or get_log()

        if release is None:

            if queue is None:
                raise ValueError(
                    "If pass None release value, you should to pass the queue"
                    "for generate this release."
                )
            elif not isinstance(queue, ReleaseQueue):
                raise TypeError(
                    "The queue argument should be ReleaseQueue object only."
                )

            if queue.check_queue(self.runner.date):
                release = self.runner.next

                while queue.check_queue(release):
                    release = self.runner.next
            else:
                release = self.runner.date

        # NOTE: Call the workflow release method.
        return self.workflow.release(
            release=release,
            params=self.values,
            run_id=run_id,
            log=log,
            queue=queue,
            override_log_name=self.alias,
        )

    def queue(
        self,
        end_date: datetime,
        queue: ReleaseQueue,
        log: type[Log],
        *,
        force_run: bool = False,
    ) -> ReleaseQueue:
        """Generate Release from the runner field and store it to the
        ReleaseQueue object.

        :param end_date: An end datetime object.
        :param queue: A workflow queue object.
        :param log: A log class that want to make log object.
        :param force_run: A flag that allow to release workflow if the log with
            that release was pointed.

        :rtype: ReleaseQueue
        """
        if self.runner.date > end_date:
            return queue

        workflow_release = Release(
            date=self.runner.date,
            offset=0,
            end_date=end_date,
            runner=self.runner,
            type=ReleaseType.TASK,
        )

        while queue.check_queue(workflow_release) or (
            log.is_pointed(name=self.alias, release=workflow_release.date)
            and not force_run
        ):
            workflow_release = Release(
                date=self.runner.next,
                offset=0,
                end_date=end_date,
                runner=self.runner,
                type=ReleaseType.TASK,
            )

        if self.runner.date > end_date:
            return queue

        # NOTE: Push the Release object to queue.
        heappush(queue.queue, workflow_release)

        return queue

    def __repr__(self) -> str:
        """Override ___repr__ method."""
        return (
            f"{self.__class__.__name__}(alias={self.alias!r}, "
            f"workflow={self.workflow.name!r}, runner={self.runner!r}, "
            f"values={self.values})"
        )

    def __eq__(self, other: WorkflowTask) -> bool:
        """Override equal property that will compare only the same type."""
        if isinstance(other, WorkflowTask):
            return (
                self.workflow.name == other.workflow.name
                and self.runner.cron == other.runner.cron
            )
        return NotImplemented
