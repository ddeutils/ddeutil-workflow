# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""
The main schedule running is ``workflow_runner`` function that trigger the
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
    """Workflow release data dataclass object."""

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
        return cls(
            date=dt,
            offset=0,
            end_date=dt + timedelta(days=1),
            runner=CronJob("* * * * *").schedule(dt.replace(tzinfo=config.tz)),
            type="manual",
        )

    def __eq__(self, other: WorkflowRelease | datetime) -> bool:
        if isinstance(other, self.__class__):
            return self.date == other.date
        elif isinstance(other, datetime):
            return self.date == other
        return NotImplemented

    def __lt__(self, other: WorkflowRelease | datetime) -> bool:
        if isinstance(other, self.__class__):
            return self.date < other.date
        elif isinstance(other, datetime):
            return self.date < other
        return NotImplemented


@dataclass
class WorkflowQueue:
    """Workflow Queue object."""

    queue: list[WorkflowRelease] = field(default_factory=list)
    running: list[WorkflowRelease] = field(default_factory=list)
    complete: list[WorkflowRelease] = field(default_factory=list)

    @property
    def is_queued(self) -> bool:
        """Return True if it has data in the queue."""
        return len(self.queue) > 0

    def check_queue(self, data: WorkflowRelease) -> bool:
        """Check a WorkflowRelease value already exists in list of tracking
        queues.

        :param data:
        """
        return (
            (data in self.queue)
            or (data in self.running)
            or (data in self.complete)
        )

    def push_queue(self, data: WorkflowRelease) -> Self:
        heappush(self.queue, data)
        return self

    def push_running(self, data: WorkflowRelease) -> Self:
        heappush(self.running, data)
        return self

    def remove_running(self, data: WorkflowRelease) -> Self:
        if data in self.running:
            self.running.remove(data)


class Workflow(BaseModel):
    """Workflow Pydantic Model this is the main future of this project because
    it use to be workflow data for running everywhere that you want or using it
    to scheduler task in background. It use lightweight coding line from
    Pydantic Model and enhance execute method on it.
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
        """Prepare the params key."""
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
    def __on_no_dup__(cls, value: list[On]) -> list[On]:
        """Validate the on fields should not contain duplicate values and if it
        contain every minute value, it should has only one on value."""
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
        return value

    @model_validator(mode="after")
    def __validate_jobs_need__(self) -> Self:
        """Validate each need job in any jobs should exists.

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
        run_id: str | None = None,
        *,
        log: type[Log] = None,
        queue: WorkflowQueue | list[datetime] | None = None,
    ) -> Result:
        """Release the workflow execution with overriding parameter with the
        release templating that include logical date (release date), execution
        date, or running id to the params.

            This method allow workflow use log object to save the execution
        result to log destination like file log to local `/logs` directory.

            I will add sleep with 0.15 seconds on every step that interact with
        the queue object.

        :param release: A release datetime.
        :param params: A workflow parameter that pass to execute method.
        :param queue: A list of release time that already queue.
        :param run_id: A workflow running ID for this release.
        :param log: A log class that want to save the execution result.
        :param queue: A WorkflowQueue object.

        :rtype: Result
        """
        log: type[Log] = log or FileLog
        run_id: str = run_id or gen_id(self.name, unique=True)

        # VALIDATE: Change queue value to WorkflowQueue object.
        if queue is None:
            queue: WorkflowQueue = WorkflowQueue()
        elif isinstance(queue, list):
            queue: WorkflowQueue = WorkflowQueue(queue=queue)

        # VALIDATE: Change release value to WorkflowRelease object.
        if isinstance(release, datetime):
            release: WorkflowRelease = WorkflowRelease.from_dt(release)

        logger.debug(
            f"({run_id}) [RELEASE]: {self.name!r} : "
            f"Closely to run >> {release.date:%Y-%m-%d %H:%M:%S}"
        )

        # NOTE: Release parameter that use to change if params has templating.
        release_params: DictData = {
            "release": {
                "logical_date": release.date,
                "execute_date": datetime.now(tz=config.tz),
                "run_id": run_id,
                "timezone": config.tz,
            }
        }

        # WARNING: Re-create workflow object that use new running workflow ID.
        rs: Result = self.execute(
            params=param2template(params, release_params),
            run_id=run_id,
        )
        logger.debug(
            f"({run_id}) [RELEASE]: {self.name!r} : "
            f"End release {release.date:%Y-%m-%d %H:%M:%S}"
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

        return Result(
            status=0,
            context={
                "params": params,
                "release": {
                    "status": "success",
                    "logical_date": release.date,
                },
            },
            run_id=run_id,
        )

    def queue_poking(
        self,
        offset: float,
        end_date: datetime,
        queue: WorkflowQueue,
        log: type[Log],
    ) -> WorkflowQueue:
        """Generate queue of datetime from the cron runner that initialize from
        the on field. with offset value.

        :param offset:
        :param end_date:
        :param queue:
        :param log:
        """
        for on in self.on:

            runner: CronRunner = on.next(
                get_dt_now(tz=config.tz, offset=offset).replace(microsecond=0)
            )

            if runner.date > end_date:
                continue

            workflow_release = WorkflowRelease(
                date=runner.date,
                offset=offset,
                end_date=end_date,
                runner=runner,
                type="poking",
            )

            while queue.check_queue(data=workflow_release) or (
                log.is_pointed(name=self.name, release=workflow_release.date)
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

            queue.push_queue(workflow_release)
        return queue

    def poke(
        self,
        start_date: datetime | None = None,
        params: DictData | None = None,
        run_id: str | None = None,
        periods: int = 1,
        *,
        log: Log | None = None,
    ) -> list[Result]:
        """Poke workflow with the ``on`` field with threading executor pool for
        executing with all its schedules that was set on the `on` value.
        This method will observe its schedule that nearing to run with the
        ``self.release()`` method.

        :param start_date: A start datetime object.
        :param params: A parameters that want to pass to the release method.
        :param run_id: A workflow running ID for this poke.
        :param periods: A periods of minutes value to running poke.
        :param log: A log object that want to use on this poking process.

        :rtype: list[Result]
        """
        # NOTE: If this workflow does not set the on schedule, it will return
        #   empty result.
        if len(self.on) == 0:
            logger.info(
                f"({run_id}) [POKING]: {self.name!r} does not have any "
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

        end_date: datetime = start_date + timedelta(minutes=periods)

        log: type[Log] = log or FileLog
        run_id: str = run_id or gen_id(self.name, unique=True)
        logger.info(
            f"({run_id}) [POKING]: Start Poking: {self.name!r} from "
            f"{start_date:%Y-%m-%d %H:%M:%S} to {end_date:%Y-%m-%d %H:%M:%S}"
        )

        params: DictData = params or {}
        workflow_queue: WorkflowQueue = WorkflowQueue()
        results: list[Result] = []
        futures: list[Future] = []

        self.queue_poking(
            offset, end_date=end_date, queue=workflow_queue, log=log
        )

        if len(workflow_queue.queue) == 0:
            logger.info(
                f"({run_id}) [POKING]: {self.name!r} does not have any "
                f"queue to run."
            )
            return []

        with ThreadPoolExecutor(
            max_workers=config.max_poking_pool_worker,
            thread_name_prefix="workflow_poking_",
        ) as executor:

            while workflow_queue.is_queued:

                wf_release: WorkflowRelease = heappop(workflow_queue.queue)
                if (
                    wf_release.date - get_dt_now(tz=config.tz, offset=offset)
                ).total_seconds() > 60:
                    logger.debug(
                        f"({run_id}) [POKING]: Waiting because the latest "
                        f"release has diff time more than 60 seconds "
                    )
                    heappush(workflow_queue.queue, wf_release)
                    delay(60)
                    self.queue_poking(
                        offset, end_date, queue=workflow_queue, log=log
                    )
                    continue

                # NOTE: Push the workflow release to running queue
                workflow_queue.push_running(wf_release)

                futures.append(
                    executor.submit(
                        self.release,
                        release=wf_release,
                        params=params,
                        log=log,
                        queue=workflow_queue,
                    )
                )

                self.queue_poking(
                    offset, end_date, queue=workflow_queue, log=log
                )

            # WARNING: This poking method does not allow to use fail-fast
            #   logic to catching parallel execution result.
            for future in as_completed(futures):
                rs: Result = future.result(timeout=60)
                results.append(rs.set_parent_run_id(run_id))

        while len(workflow_queue.running) > 0:  # pragma: no cov
            logger.warning(
                f"({run_id}) [POKING]: Running does empty when poking "
                f"process was finishing."
            )
            delay(10)

        return results

    def execute_job(
        self,
        job_id: str,
        params: DictData,
        run_id: str | None = None,
        *,
        raise_error: bool = True,
    ) -> Result:
        """Workflow Job execution with passing dynamic parameters from the
        workflow execution to the target job.

            This execution is the minimum level of execution of this workflow
        model. It different with ``self.execute`` because this method run only
        one job and return with context of this job data.

        :param job_id: A job ID that want to execute.
        :param params: A params that was parameterized from workflow execution.
        :param run_id: A workflow running ID for this job execution.
        :param raise_error: A flag that raise error instead catching to result
            if it get exception from job execution.

        :rtype: Result
        """
        run_id: str = run_id or gen_id(self.name, unique=True)

        # VALIDATE: check a job ID that exists in this workflow or not.
        if job_id not in self.jobs:
            raise WorkflowException(
                f"The job ID: {job_id} does not exists in {self.name!r} "
                f"workflow."
            )

        logger.info(f"({run_id}) [WORKFLOW]: Start execute: {job_id!r}")

        # IMPORTANT:
        #   Change any job running IDs to this workflow running ID.
        #
        try:
            job: Job = self.jobs[job_id]
            job.set_outputs(
                job.execute(params=params, run_id=run_id).context,
                to=params,
            )
        except JobException as err:
            logger.error(
                f"({run_id}) [WORKFLOW]: {err.__class__.__name__}: {err}"
            )
            if raise_error:
                raise WorkflowException(
                    f"Get job execution error {job_id}: JobException: {err}"
                ) from None
            else:
                raise NotImplementedError() from None

        return Result(status=0, context=params).set_run_id(run_id)

    def execute(
        self,
        params: DictData,
        run_id: str | None = None,
        *,
        timeout: int = 60,
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
        :type params: DictData | None
        :param run_id: A workflow running ID for this job execution.
        :type run_id: str | None
        :param timeout: A workflow execution time out in second unit that use
            for limit time of execution and waiting job dependency. Default is
            60 seconds.
        :type timeout: int

        :rtype: Result
        """
        run_id: str = run_id or gen_id(self.name, unique=True)
        logger.info(f"({run_id}) [WORKFLOW]: Start Execute: {self.name!r} ...")

        # NOTE: I use this condition because this method allow passing empty
        #   params and I do not want to create new dict object.
        ts: float = time.monotonic()
        rs: Result = Result(run_id=run_id)

        # NOTE: It should not do anything if it does not have job.
        if not self.jobs:
            logger.warning(
                f"({run_id}) [WORKFLOW]: This workflow: {self.name!r} "
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
                    worker=config.max_job_parallel,
                    timeout=timeout,
                )
        except WorkflowException as err:
            context.update(
                {
                    "error": err,
                    "error_message": f"{err.__class__.__name__}: {err}",
                },
            )
            status = 1
        return rs.catch(status=status, context=context)

    def __exec_threading(
        self,
        run_id: str,
        context: DictData,
        ts: float,
        job_queue: Queue,
        *,
        worker: int = 2,
        timeout: int = 600,
    ) -> DictData:
        """Workflow execution by threading strategy.

            If a job need dependency, it will check dependency job ID from
        context data before allow it run.

        :param context: A context workflow data that want to downstream passing.
        :param ts: A start timestamp that use for checking execute time should
            timeout.
        :param job_queue: A job queue object.
        :param timeout: A second value unit that bounding running time.
        :param worker: A number of threading executor pool size.
        :rtype: DictData
        """
        not_time_out_flag: bool = True
        logger.debug(
            f"({run_id}): [WORKFLOW]: Run {self.name} with threading job "
            f"executor"
        )

        # IMPORTANT: The job execution can run parallel and waiting by
        #   needed.
        with ThreadPoolExecutor(max_workers=worker) as executor:
            futures: list[Future] = []

            while not job_queue.empty() and (
                not_time_out_flag := ((time.monotonic() - ts) < timeout)
            ):
                job_id: str = job_queue.get()
                job: Job = self.jobs[job_id]

                if any(need not in context["jobs"] for need in job.needs):
                    job_queue.task_done()
                    job_queue.put(job_id)
                    time.sleep(0.25)
                    continue

                # NOTE: Start workflow job execution with deep copy context data
                #   before release.
                #
                #   {
                #       'params': <input-params>,
                #       'jobs': {},
                #   }
                futures.append(
                    executor.submit(
                        self.execute_job,
                        job_id,
                        params=context,
                    ),
                )

                # NOTE: Mark this job queue done.
                job_queue.task_done()

            # NOTE: Wait for all items to finish processing
            job_queue.join()

            for future in as_completed(futures, timeout=1800):
                if err := future.exception():
                    logger.error(f"({run_id}) [WORKFLOW]: {err}")
                    raise WorkflowException(f"{err}")
                try:
                    future.result(timeout=60)
                except TimeoutError as err:  # pragma: no cove
                    raise WorkflowException(
                        "Timeout when getting result from future"
                    ) from err

        if not_time_out_flag:
            return context

        # NOTE: Raise timeout error.
        logger.warning(  # pragma: no cov
            f"({run_id}) [WORKFLOW]: Execution of workflow, {self.name!r} "
            f", was timeout"
        )
        raise WorkflowException(  # pragma: no cov
            f"Execution of workflow: {self.name} was timeout"
        )

    def __exec_non_threading(
        self,
        run_id: str,
        context: DictData,
        ts: float,
        job_queue: Queue,
        *,
        timeout: int = 600,
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
        not_time_out_flag: bool = True
        logger.debug(
            f"({run_id}) [WORKFLOW]: Run {self.name} with non-threading job "
            f"executor"
        )

        while not job_queue.empty() and (
            not_time_out_flag := ((time.monotonic() - ts) < timeout)
        ):
            job_id: str = job_queue.get()
            job: Job = self.jobs[job_id]

            # NOTE: Waiting dependency job run successful before release.
            if any(need not in context["jobs"] for need in job.needs):
                job_queue.task_done()
                job_queue.put(job_id)
                time.sleep(0.05)
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

        # NOTE: Wait for all items to finish processing
        job_queue.join()

        if not_time_out_flag:
            return context

        # NOTE: Raise timeout error.
        logger.warning(  # pragma: no cov
            f"({run_id}) [WORKFLOW]: Execution of workflow was timeout"
        )
        raise WorkflowException(  # pragma: no cov
            f"Execution of workflow: {self.name} was timeout"
        )


@dataclass(config=ConfigDict(arbitrary_types_allowed=True))
class WorkflowTaskData:
    """Workflow task dataclass that use to keep mapping data and objects for
    passing in multithreading task.

        This dataclass will be 1-1 mapping with workflow and cron runner
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
            f"({run_id}) [CORE]: {self.workflow.name!r} : {runner.cron} : "
            f"{next_time:%Y-%m-%d %H:%M:%S}"
        )
        heappush(queue[self.alias], next_time)
        start_sec: float = time.monotonic()

        if get_diff_sec(next_time, tz=runner.tz) > waiting_sec:
            logger.debug(
                f"({run_id}) [WORKFLOW]: {self.workflow.name!r} : "
                f"{runner.cron} "
                f": Does not closely >> {next_time:%Y-%m-%d %H:%M:%S}"
            )

            # NOTE: Add this next running datetime that not in period to queue
            #   and remove it to running.
            queue[self.alias].remove(next_time)

            time.sleep(0.2)
            return

        logger.debug(
            f"({run_id}) [CORE]: {self.workflow.name!r} : {runner.cron} : "
            f"Closely to run >> {next_time:%Y-%m-%d %H:%M:%S}"
        )

        # NOTE: Release when the time is nearly to schedule time.
        while (duration := get_diff_sec(next_time, tz=config.tz)) > (
            sleep_interval + 5
        ):
            logger.debug(
                f"({run_id}) [CORE]: {self.workflow.name!r} : {runner.cron} "
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

        # WARNING: Re-create workflow object that use new running workflow ID.
        rs: Result = self.workflow.execute(
            params=param2template(self.params, release_params),
        )
        logger.debug(
            f"({run_id}) [CORE]: {self.workflow.name!r} : {runner.cron} : "
            f"End release - {next_time:%Y-%m-%d %H:%M:%S}"
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

    def __eq__(self, other) -> bool:
        if isinstance(other, WorkflowTaskData):
            return (
                self.workflow.name == other.workflow.name
                and self.runner.cron == other.runner.cron
            )
        return NotImplemented
