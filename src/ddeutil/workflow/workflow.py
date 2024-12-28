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
from functools import total_ordering
from heapq import heappop, heappush
from queue import Queue
from textwrap import dedent
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.dataclasses import dataclass
from pydantic.functional_validators import field_validator, model_validator
from typing_extensions import Self

from .__cron import CronJob, CronRunner
from .__types import DictData, TupleStr
from .conf import FileLog, Loader, Log, config, get_logger
from .exceptions import JobException, WorkflowException
from .job import Job
from .on import On
from .utils import (
    Param,
    Result,
    cut_id,
    delay,
    gen_id,
    get_diff_sec,
    get_dt_now,
    has_template,
    param2template,
)

logger = get_logger("ddeutil.workflow")

__all__: TupleStr = (
    "Workflow",
    "WorkflowRelease",
    "WorkflowQueue",
    "WorkflowTaskData",
)


@total_ordering
@dataclass(config=ConfigDict(arbitrary_types_allowed=True))
class WorkflowRelease:
    """Workflow release Pydantic dataclass object."""

    date: datetime
    offset: float
    end_date: datetime
    runner: CronRunner
    type: str

    def __repr__(self) -> str:
        return repr(f"{self.date:%Y-%m-%d %H:%M:%S}")

    def __str__(self) -> str:
        return f"{self.date:%Y-%m-%d %H:%M:%S}"

    @classmethod
    def from_dt(cls, dt: datetime) -> Self:
        """Construct WorkflowRelease via datetime object only.

        :param dt: A datetime object.

        :rtype: Self
        """
        return cls(
            date=dt,
            offset=0,
            end_date=dt + timedelta(days=1),
            runner=CronJob("* * * * *").schedule(dt.replace(tzinfo=config.tz)),
            type="manual",
        )

    def __eq__(self, other: WorkflowRelease | datetime) -> bool:
        """Override equal property that will compare only the same type or
        datetime.
        """
        if isinstance(other, self.__class__):
            return self.date == other.date
        elif isinstance(other, datetime):
            return self.date == other
        return NotImplemented

    def __lt__(self, other: WorkflowRelease | datetime) -> bool:
        """Override equal property that will compare only the same type or
        datetime.
        """
        if isinstance(other, self.__class__):
            return self.date < other.date
        elif isinstance(other, datetime):
            return self.date < other
        return NotImplemented


@dataclass
class WorkflowQueue:
    """Workflow Queue object that is management of WorkflowRelease objects."""

    queue: list[WorkflowRelease] = field(default_factory=list)
    running: list[WorkflowRelease] = field(default_factory=list)
    complete: list[WorkflowRelease] = field(default_factory=list)

    @classmethod
    def from_list(
        cls, queue: list[datetime] | list[WorkflowRelease] | None
    ) -> Self:
        """Construct WorkflowQueue object from an input queue value that passing
        with list of datetime or list of WorkflowRelease.

        :raise TypeError: If the type of an input queue does not valid.

        :rtype: Self
        """
        if queue is None:
            return cls()
        elif isinstance(queue, list):

            if all(isinstance(q, datetime) for q in queue):
                return cls(queue=[WorkflowRelease.from_dt(q) for q in queue])

            elif all(isinstance(q, WorkflowRelease) for q in queue):
                return cls(queue=queue)

        raise TypeError(
            "Type of the queue does not valid with WorkflowQueue "
            "or list of datetime or list of WorkflowRelease."
        )

    @property
    def is_queued(self) -> bool:
        """Return True if it has workflow release object in the queue.

        :rtype: bool
        """
        return len(self.queue) > 0

    def check_queue(self, value: WorkflowRelease) -> bool:
        """Check a WorkflowRelease value already exists in list of tracking
        queues.

        :param value: A WorkflowRelease object that want to check it already in
            queues.

        :rtype: bool
        """
        return (
            (value in self.queue)
            or (value in self.running)
            or (value in self.complete)
        )

    def push_queue(self, value: WorkflowRelease) -> Self:
        """Push data to the queue."""
        heappush(self.queue, value)
        return self

    def push_running(self, value: WorkflowRelease) -> Self:
        """Push data to the running."""
        heappush(self.running, value)
        return self

    def remove_running(self, value: WorkflowRelease) -> Self:
        """Remove data on the running if it exists."""
        if value in self.running:
            self.running.remove(value)


class Workflow(BaseModel):
    """Workflow Pydantic model.

        This is the main future of this project because it use to be workflow
    data for running everywhere that you want or using it to scheduler task in
    background. It use lightweight coding line from Pydantic Model and enhance
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
        if loader.type != cls:
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
        # NOTE: Prepare params type if it passing with only type value.
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
        contain the every minute value more than one value, it will remove to
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
        #         "If it has every minute cronjob on value, it should has only "
        #         "one value in the on field."
        #     )

        if len(set_ons) > config.max_on_per_workflow:
            raise ValueError(
                f"The number of the on should not more than "
                f"{config.max_on_per_workflow} crontab."
            )
        return value

    @model_validator(mode="after")
    def __validate_jobs_need__(self) -> Self:
        """Validate each need job in any jobs should exists.

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
        release: datetime | WorkflowRelease,
        params: DictData,
        *,
        run_id: str | None = None,
        log: type[Log] = None,
        queue: (
            WorkflowQueue | list[datetime] | list[WorkflowRelease] | None
        ) = None,
    ) -> Result:
        """Release the workflow execution with overriding parameter with the
        release templating that include logical date (release date), execution
        date, or running id to the params.

            This method allow workflow use log object to save the execution
        result to log destination like file log to the local `/logs` directory.

        :param release: A release datetime or WorkflowRelease object.
        :param params: A workflow parameter that pass to execute method.
        :param queue: A list of release time that already queue.
        :param run_id: A workflow running ID for this release.
        :param log: A log class that want to save the execution result.
        :param queue: A WorkflowQueue object.

        :rtype: Result
        """
        log: type[Log] = log or FileLog
        run_id: str = run_id or gen_id(self.name, unique=True)
        rs_release: Result = Result(run_id=run_id)

        # VALIDATE: Change queue value to WorkflowQueue object.
        if queue is None or isinstance(queue, list):
            queue: WorkflowQueue = WorkflowQueue.from_list(queue)

        # VALIDATE: Change release value to WorkflowRelease object.
        if isinstance(release, datetime):
            release: WorkflowRelease = WorkflowRelease.from_dt(release)

        logger.debug(
            f"({cut_id(run_id)}) [RELEASE]: {self.name!r} : Start release - "
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
            f"({cut_id(run_id)}) [RELEASE]: {self.name!r} : End release - "
            f"{release.date:%Y-%m-%d %H:%M:%S}"
        )

        rs.set_parent_run_id(run_id)
        rs_log: Log = log.model_validate(
            {
                "name": self.name,
                "release": release.date,
                "type": release.type,
                "context": rs.context,
                "parent_run_id": rs.parent_run_id,
                "run_id": rs.run_id,
            }
        )

        # NOTE: Saving execution result to destination of the input log object.
        rs_log.save(excluded=None)

        # NOTE: Remove this release from running.
        queue.remove_running(release)
        heappush(queue.complete, release)

        return rs_release.catch(
            status=0,
            context={
                "params": params,
                "release": {"status": "success", "logical_date": release.date},
                "outputs": rs.context,
            },
        )

    def queue_poking(
        self,
        offset: float,
        end_date: datetime,
        queue: WorkflowQueue,
        log: type[Log],
        *,
        force_run: bool = False,
    ) -> WorkflowQueue:
        """Generate queue of datetime from the cron runner that initialize from
        the on field. with offset value.

        :param offset: A offset in second unit for time travel.
        :param end_date: An end datetime object.
        :param queue: A workflow queue object.
        :param log: A log class that want to making log object.
        :param force_run: A flag that allow to release workflow if the log with
            that release was pointed.

        :rtype: WorkflowQueue
        """
        for on in self.on:

            runner: CronRunner = on.next(
                get_dt_now(tz=config.tz, offset=offset).replace(microsecond=0)
            )

            # NOTE: Skip this runner date if it more than the end date.
            if runner.date > end_date:
                continue

            workflow_release = WorkflowRelease(
                date=runner.date,
                offset=offset,
                end_date=end_date,
                runner=runner,
                type="poking",
            )

            while queue.check_queue(workflow_release) or (
                log.is_pointed(name=self.name, release=workflow_release.date)
                and not force_run
            ):
                workflow_release = WorkflowRelease(
                    date=runner.next,
                    offset=offset,
                    end_date=end_date,
                    runner=runner,
                    type="poking",
                )

            if runner.date > end_date:
                continue

            # NOTE: Push the WorkflowRelease object to queue.
            queue.push_queue(workflow_release)

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
        log: type[Log] = log or FileLog
        run_id: str = run_id or gen_id(self.name, unique=True)

        # NOTE: If this workflow does not set the on schedule, it will return
        #   empty result.
        if len(self.on) == 0:
            logger.info(
                f"({cut_id(run_id)}) [POKING]: {self.name!r} does not have any "
                f"schedule to run."
            )
            return []

        if periods <= 0:
            raise WorkflowException(
                "The period of poking should be int and grater or equal than 1."
            )

        # NOTE: Create start_date and offset variables.
        current_date: datetime = datetime.now(tz=config.tz)

        if start_date and start_date <= current_date:
            start_date = start_date.replace(tzinfo=config.tz)
            offset: float = (current_date - start_date).total_seconds()
        else:
            start_date: datetime = current_date
            offset: float = 0

        # NOTE: End date is use to stop generate queue with an input periods
        #   value.
        end_date: datetime = start_date + timedelta(minutes=periods)

        logger.info(
            f"({cut_id(run_id)}) [POKING]: Start Poking: {self.name!r} from "
            f"{start_date:%Y-%m-%d %H:%M:%S} to {end_date:%Y-%m-%d %H:%M:%S}"
        )

        params: DictData = {} if params is None else params
        wf_queue: WorkflowQueue = WorkflowQueue()
        results: list[Result] = []
        futures: list[Future] = []

        # NOTE: Make queue to the workflow queue object.
        self.queue_poking(
            offset,
            end_date=end_date,
            queue=wf_queue,
            log=log,
            force_run=force_run,
        )
        if not wf_queue.is_queued:
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

            while wf_queue.is_queued:

                # NOTE: Pop the latest WorkflowRelease object from queue.
                release: WorkflowRelease = heappop(wf_queue.queue)

                if (
                    release.date - get_dt_now(tz=config.tz, offset=offset)
                ).total_seconds() > 60:
                    logger.debug(
                        f"({cut_id(run_id)}) [POKING]: Wait because the latest "
                        f"release has diff time more than 60 seconds ..."
                    )
                    heappush(wf_queue.queue, release)
                    delay(60)

                    # WARNING: I already call queue poking again because issue
                    #   about the every minute crontab.
                    self.queue_poking(
                        offset,
                        end_date,
                        queue=wf_queue,
                        log=log,
                        force_run=force_run,
                    )
                    continue

                # NOTE: Push the latest WorkflowRelease to the running queue.
                wf_queue.push_running(release)

                futures.append(
                    executor.submit(
                        self.release,
                        release=release,
                        params=params,
                        log=log,
                        queue=wf_queue,
                    )
                )

                self.queue_poking(
                    offset,
                    end_date,
                    queue=wf_queue,
                    log=log,
                    force_run=force_run,
                )

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
            if it get exception from job execution.

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

            The result of execution process for each jobs and stages on this
        workflow will keeping in dict which able to catch out with all jobs and
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
            for limit time of execution and waiting job dependency.
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

        # NOTE: Create a job queue that keep the job that want to running after
        #   it dependency condition.
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
            timeout.
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
            timeout.
        :param timeout: A second value unit that bounding running time.

        :rtype: DictData
        """
        not_timeout_flag: bool = True
        timeout: int = timeout or config.max_job_exec_timeout
        logger.debug(
            f"({cut_id(run_id)}) [WORKFLOW]: Run {self.name} with "
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
            #   before release. This job execution process will running until
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
class WorkflowTaskData:
    """Workflow task Pydantic dataclass object that use to keep mapping data and
    workflow model for passing to the multithreading task.

        This dataclass object is mapping 1-to-1 with workflow and cron runner
    objects.
    """

    alias: str
    workflow: Workflow
    runner: CronRunner
    params: DictData

    def release(
        self,
        queue: dict[str, list[datetime]],
        log: Log | None = None,
        run_id: str | None = None,
        *,
        waiting_sec: int = 60,
        sleep_interval: int = 15,
    ) -> None:  # pragma: no cov
        """Workflow task release that use the same logic of `workflow.release`
        method.

        :param queue:
        :param log: A log object for saving result logging from workflow
            execution process.
        :param run_id: A workflow running ID for this release.
        :param waiting_sec: A second period value that allow workflow execute.
        :param sleep_interval: A second value that want to waiting until time
            to execute.
        """
        log: Log = log or FileLog
        run_id: str = run_id or gen_id(self.workflow.name, unique=True)
        runner: CronRunner = self.runner

        # NOTE: get next schedule time that generate from now.
        next_time: datetime = runner.date

        # NOTE: get next utils it does not running.
        while log.is_pointed(self.workflow.name, next_time) or (
            next_time in queue[self.alias]
        ):
            next_time: datetime = runner.next

        logger.debug(
            f"({cut_id(run_id)}) [CORE]: {self.workflow.name!r} : "
            f"{runner.cron} : {next_time:%Y-%m-%d %H:%M:%S}"
        )
        heappush(queue[self.alias], next_time)
        start_sec: float = time.monotonic()

        if get_diff_sec(next_time, tz=runner.tz) > waiting_sec:
            logger.debug(
                f"({cut_id(run_id)}) [WORKFLOW]: {self.workflow.name!r} : "
                f"{runner.cron} "
                f": Does not closely >> {next_time:%Y-%m-%d %H:%M:%S}"
            )

            # NOTE: Add this next running datetime that not in period to queue
            #   and remove it to running.
            queue[self.alias].remove(next_time)

            time.sleep(0.2)
            return

        logger.debug(
            f"({cut_id(run_id)}) [CORE]: {self.workflow.name!r} : "
            f"{runner.cron} : Closely to run >> {next_time:%Y-%m-%d %H:%M:%S}"
        )

        # NOTE: Release when the time is nearly to schedule time.
        while (duration := get_diff_sec(next_time, tz=config.tz)) > (
            sleep_interval + 5
        ):
            logger.debug(
                f"({cut_id(run_id)}) [CORE]: {self.workflow.name!r} : "
                f"{runner.cron} : Sleep until: {duration}"
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

        # WARNING: Re-create workflow object that use new running workflow ID.
        rs: Result = self.workflow.execute(
            params=param2template(self.params, release_params),
        )
        logger.debug(
            f"({cut_id(run_id)}) [CORE]: {self.workflow.name!r} : "
            f"{runner.cron} : End release - {next_time:%Y-%m-%d %H:%M:%S}"
        )

        # NOTE: Set parent ID on this result.
        rs.set_parent_run_id(run_id)

        # NOTE: Save result to log object saving.
        rs_log: Log = log.model_validate(
            {
                "name": self.workflow.name,
                "type": "schedule",
                "release": next_time,
                "context": rs.context,
                "parent_run_id": rs.run_id,
                "run_id": rs.run_id,
            }
        )
        rs_log.save(excluded=None)

        # NOTE: Remove the current release date from the running.
        queue[self.alias].remove(next_time)
        total_sec: float = time.monotonic() - start_sec

        # IMPORTANT:
        #   Add the next running datetime to workflow task queue.
        future_running_time: datetime = runner.next

        while (
            future_running_time in queue[self.alias]
            or (future_running_time - next_time).total_seconds() < total_sec
        ):  # pragma: no cov
            future_running_time: datetime = runner.next

        # NOTE: Queue next release date.
        logger.debug(f"[CORE]: {'-' * 100}")

    def __eq__(self, other: WorkflowTaskData) -> bool:
        """Override equal property that will compare only the same type."""
        if isinstance(other, WorkflowTaskData):
            return (
                self.workflow.name == other.workflow.name
                and self.runner.cron == other.runner.cron
            )
        return NotImplemented
