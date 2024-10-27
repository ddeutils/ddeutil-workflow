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
import inspect
import logging
import time
from concurrent.futures import (
    Future,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
)
from dataclasses import field
from datetime import datetime, timedelta
from functools import wraps
from heapq import heappush
from queue import Queue
from textwrap import dedent
from threading import Thread
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass
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
from .conf import FileLog, Loader, Log, config, get_logger
from .exceptions import JobException, WorkflowException
from .job import Job
from .on import On
from .utils import (
    Param,
    Result,
    batch,
    delay,
    gen_id,
    get_diff_sec,
    has_template,
    param2template,
    queue2str,
)

P = ParamSpec("P")
logger = get_logger("ddeutil.workflow")

# NOTE: Adjust logging level on the schedule package.
logging.getLogger("schedule").setLevel(logging.INFO)


__all__: TupleStr = (
    "Workflow",
    "WorkflowTaskData",
    "Schedule",
    "ScheduleWorkflow",
    "workflow_task",
    "workflow_monitor",
    "workflow_control",
    "workflow_runner",
)


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
    run_id: Optional[str] = Field(
        default=None,
        description=(
            "A running workflow ID that is able to change after initialize."
        ),
        repr=False,
        exclude=True,
    )

    @property
    def new_run_id(self) -> str:
        """Running ID of this workflow that always generate new unique value.

        :rtype: str
        """
        return gen_id(self.name, unique=True)

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
        cls.__bypass_on(loader_data)
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

    @model_validator(mode="after")
    def __validate_jobs_need_and_prepare_running_id(self) -> Self:
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

        if self.run_id is None:
            self.run_id = self.new_run_id

        # VALIDATE: Validate workflow name should not dynamic with params
        #   template.
        if has_template(self.name):
            raise ValueError(
                f"Workflow name should not has any template, please check, "
                f"{self.name!r}."
            )

        return self

    def get_running_id(self, run_id: str) -> Self:
        """Return Workflow model object that changing workflow running ID with
        an input running ID.

        :param run_id: A replace workflow running ID.
        :rtype: Self
        """
        return self.model_copy(update={"run_id": run_id})

    def job(self, name: str) -> Job:
        """Return this workflow's job that already created on this job field.

        :param name: A job name that want to get from a mapping of job models.
        :type name: str

        :rtype: Job
        :returns: A job model that exists on this workflow by input name.
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
        :rtype: DictData
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
        on: On,
        params: DictData,
        queue: list[datetime],
        *,
        waiting_sec: int = 60,
        sleep_interval: int = 15,
        log: Log = None,
    ) -> Result:
        """Start running workflow with the on schedule in period of 30 minutes.
        That mean it will still running at background 30 minutes until the
        schedule matching with its time.

            This method allow workflow use log object to save the execution
        result to log destination like file log to local `/logs` directory.

        :param on: An on schedule value.
        :param params: A workflow parameter that pass to execute method.
        :param queue: A list of release time that already running.
        :param waiting_sec: A second period value that allow workflow execute.
        :param sleep_interval: A second value that want to waiting until time
            to execute.
        :param log: A log object that want to save execution result.
        :rtype: Result
        """
        logger.debug(
            f"({self.run_id}) [CORE]: {self.name!r}: {on.cronjob} : run with "
            f"queue id: {id(queue)}"
        )
        log: Log = log or FileLog
        gen: CronRunner = on.generate(
            datetime.now(tz=config.tz).replace(second=0, microsecond=0)
            + timedelta(seconds=1)
        )
        cron_tz: ZoneInfo = gen.tz

        # NOTE: get next schedule time that generate from now.
        next_time: datetime = gen.next

        # NOTE: While-loop to getting next until it does not logger.
        while log.is_pointed(self.name, next_time, queue=queue):
            next_time: datetime = gen.next

        # NOTE: Heap-push this next running time to log queue list.
        heappush(queue, next_time)

        # VALIDATE: Check the different time between the next schedule time and
        #   now that less than waiting period (second unit).
        if get_diff_sec(next_time, tz=cron_tz) > waiting_sec:
            logger.debug(
                f"({self.run_id}) [CORE]: {self.name!r} : {on.cronjob} : "
                f"Does not closely >> {next_time:%Y-%m-%d %H:%M:%S}"
            )

            # NOTE: Remove next datetime from queue.
            queue.remove(next_time)

            time.sleep(0.15)
            return Result(
                status=0,
                context={
                    "params": params,
                    "release": {"status": "skipped", "cron": [str(on.cronjob)]},
                },
            )

        logger.debug(
            f"({self.run_id}) [CORE]: {self.name!r} : {on.cronjob} : "
            f"Closely to run >> {next_time:%Y-%m-%d %H:%M:%S}"
        )

        # NOTE: Release when the time is nearly to schedule time.
        while (duration := get_diff_sec(next_time, tz=cron_tz)) > (
            sleep_interval + 5
        ):  # pragma: no cov
            logger.debug(
                f"({self.run_id}) [CORE]: {self.name!r} : {on.cronjob} : "
                f"Sleep until: {duration}"
            )
            time.sleep(sleep_interval)

        time.sleep(0.5)

        # NOTE: Release parameter that use to change if params has
        #   templating.
        release_params: DictData = {
            "release": {
                "logical_date": next_time,
            },
        }

        # WARNING: Re-create workflow object that use new running workflow
        #   ID.
        runner: Self = self.get_running_id(run_id=self.new_run_id)
        rs: Result = runner.execute(
            params=param2template(params, release_params),
        )
        logger.debug(
            f"({runner.run_id}) [CORE]: {self.name!r} : {on.cronjob} : "
            f"End release {next_time:%Y-%m-%d %H:%M:%S}"
        )

        # NOTE: Delete a copied workflow instance for saving memory.
        del runner

        rs.set_parent_run_id(self.run_id)
        rs_log: Log = log.model_validate(
            {
                "name": self.name,
                "on": str(on.cronjob),
                "release": next_time,
                "context": rs.context,
                "parent_run_id": rs.run_id,
                "run_id": rs.run_id,
            }
        )
        # NOTE: Saving execution result to destination of the input log object.
        rs_log.save(excluded=None)

        queue.remove(next_time)
        time.sleep(0.05)
        return Result(
            status=0,
            context={
                "params": params,
                "release": {"status": "run", "cron": [str(on.cronjob)]},
            },
        )

    def poke(
        self,
        params: DictData | None = None,
        *,
        log: Log | None = None,
    ) -> list[Result]:
        """Poke workflow with threading executor pool for executing with all its
        schedules that was set on the `on` value. This method will observe its
        schedule that nearing to run with the ``self.release()`` method.

        :param params: A parameters that want to pass to the release method.
        :param log: A log object that want to use on this poking process.
        :rtype: list[Result]
        """
        logger.info(
            f"({self.run_id}) [POKING]: Start Poking: {self.name!r} ..."
        )

        # NOTE: If this workflow does not set the on schedule, it will return
        #   empty result.
        if len(self.on) == 0:
            return []

        params: DictData = params or {}
        queue: list[datetime] = []
        results: list[Result] = []

        with ThreadPoolExecutor(
            max_workers=config.max_poking_pool_worker,
            thread_name_prefix="wf_poking_",
        ) as executor:
            futures: list[Future] = []
            for on in self.on:
                futures.append(
                    executor.submit(
                        self.release,
                        on,
                        params=params,
                        log=log,
                        queue=queue,
                    )
                )
                delay(second=0.15)

            # WARNING: This poking method does not allow to use fail-fast logic
            #   to catching parallel execution result.
            for future in as_completed(futures):
                results.append(future.result(timeout=60))

        if len(queue) > 0:  # pragma: no cov
            logger.error(
                f"({self.run_id}) [POKING]: Log Queue does empty when poking "
                f"process was finishing."
            )

        return results

    def execute_job(
        self,
        job_id: str,
        params: DictData,
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
        :param raise_error: A flag that raise error instead catching to result
            if it get exception from job execution.
        :rtype: Result
        """
        # VALIDATE: check a job ID that exists in this workflow or not.
        if job_id not in self.jobs:
            raise WorkflowException(
                f"The job ID: {job_id} does not exists in {self.name!r} "
                f"workflow."
            )

        logger.info(f"({self.run_id}) [WORKFLOW]: Start execute: {job_id!r}")

        # IMPORTANT:
        #   Change any job running IDs to this workflow running ID.
        #
        try:
            job: Job = self.jobs[job_id].get_running_id(self.run_id)
            job.set_outputs(
                job.execute(params=params).context,
                to=params,
            )
        except JobException as err:
            logger.error(
                f"({self.run_id}) [WORKFLOW]: {err.__class__.__name__}: {err}"
            )
            if raise_error:
                raise WorkflowException(
                    f"Get job execution error {job_id}: JobException: {err}"
                ) from None
            else:
                raise NotImplementedError() from None

        return Result(status=0, context=params)

    def execute(
        self,
        params: DictData | None = None,
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
        :param timeout: A workflow execution time out in second unit that use
            for limit time of execution and waiting job dependency. Default is
            60 seconds.
        :type timeout: int
        :rtype: Result
        """
        logger.info(f"({self.run_id}) [CORE]: Start Execute: {self.name!r} ...")

        # NOTE: I use this condition because this method allow passing empty
        #   params and I do not want to create new dict object.
        params: DictData = {} if params is None else params
        ts: float = time.monotonic()
        rs: Result = Result()

        # NOTE: It should not do anything if it does not have job.
        if not self.jobs:
            logger.warning(
                f"({self.run_id}) [WORKFLOW]: This workflow: {self.name!r} "
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
                    context=context,
                    ts=ts,
                    job_queue=jq,
                    timeout=timeout,
                )
            else:
                self.__exec_threading(
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
            f"({self.run_id}): [CORE]: Run {self.name} with threading job "
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
                    logger.error(f"({self.run_id}) [CORE]: {err}")
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
            f"({self.run_id}) [WORKFLOW]: Execution of workflow, {self.name!r} "
            f", was timeout"
        )
        raise WorkflowException(  # pragma: no cov
            f"Execution of workflow: {self.name} was timeout"
        )

    def __exec_non_threading(
        self,
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
            f"({self.run_id}) [CORE]: Run {self.name} with non-threading job "
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
            self.execute_job(job_id=job_id, params=context)

            # NOTE: Mark this job queue done.
            job_queue.task_done()

        # NOTE: Wait for all items to finish processing
        job_queue.join()

        if not_time_out_flag:
            return context

        # NOTE: Raise timeout error.
        logger.warning(  # pragma: no cov
            f"({self.run_id}) [WORKFLOW]: Execution of workflow was timeout"
        )
        raise WorkflowException(  # pragma: no cov
            f"Execution of workflow: {self.name} was timeout"
        )


class ScheduleWorkflow(BaseModel):
    """Schedule Workflow Pydantic model that use to keep workflow model for the
    Schedule model. it should not use Workflow model directly because on the
    schedule config it can adjust crontab value that different from the Workflow
    model.
    """

    name: str = Field(description="A workflow name.")
    on: list[On] = Field(
        default_factory=list,
        description="An override On instance value.",
    )
    params: DictData = Field(
        default_factory=dict,
        description="A parameters that want to use to workflow execution.",
    )

    @model_validator(mode="before")
    def __prepare_before__(cls, values: DictData) -> DictData:
        """Prepare incoming values before validating with model fields.

        :rtype: DictData
        """
        values["name"] = values["name"].replace(" ", "_")

        cls.__bypass_on(values)
        return values

    @classmethod
    def __bypass_on(
        cls,
        data: DictData,
        externals: DictData | None = None,
    ) -> DictData:
        """Bypass the on data to loaded config data.

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
    not equal the on value in Workflow model but it use same logic to running
    release date with crontab interval.
    """

    desc: Optional[str] = Field(
        default=None,
        description=(
            "A schedule description that can be string of markdown content."
        ),
    )
    workflows: list[ScheduleWorkflow] = Field(
        default_factory=list,
        description="A list of ScheduleWorkflow models.",
    )

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
        queue: dict[str, list[datetime]],
        running: dict[str, list[datetime]],
        *,
        externals: DictData | None = None,
    ) -> list[WorkflowTaskData]:
        """Return the list of WorkflowTaskData object from the specific input
        datetime that mapping with the on field.

        :param start_date: A start date that get from the workflow schedule.
        :param queue: A mapping of name and list of datetime for queue.
        :param running: A mapping of name and list of datetime for running.
        :param externals: An external parameters that pass to the Loader object.

        :rtype: list[WorkflowTaskData]
        """

        # NOTE: Create pair of workflow and on.
        workflow_tasks: list[WorkflowTaskData] = []
        externals: DictData = externals or {}

        for wfs in self.workflows:
            wf: Workflow = Workflow.from_loader(wfs.name, externals=externals)

            # NOTE: Create default list of release datetime.
            queue[wfs.name]: list[datetime] = []
            running[wfs.name]: list[datetime] = []

            # NOTE: Create the default on value if it does not passing on the
            #   Schedule object.
            _ons: list[On] = wf.on.copy() if len(wfs.on) == 0 else wfs.on

            for on in _ons:
                on_gen: CronRunner = on.generate(start_date)
                next_running_date = on_gen.next

                while next_running_date in queue[wfs.name]:
                    next_running_date = on_gen.next

                # NOTE: Push the next running date to queue list.
                heappush(queue[wfs.name], next_running_date)

                workflow_tasks.append(
                    WorkflowTaskData(
                        workflow=wf,
                        on=on,
                        params=wfs.params,
                        queue=queue,
                        running=running,
                    ),
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

    def decorator(func: ReturnCancelJob) -> ReturnCancelJob:
        try:
            # NOTE: Check the function that want to handle is method or not.
            if inspect.ismethod(func):  # pragma: no cov

                @wraps(func)
                def wrapper(self, *args, **kwargs):
                    return func(self, *args, **kwargs)

                return wrapper

            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper

        except Exception as err:  # pragma: no cov
            logger.exception(err)
            if cancel_on_failure:
                return CancelJob
            raise err

    return decorator


@dataclass(frozen=True)
class WorkflowTaskData:
    """Workflow task dataclass that use to keep mapping data and objects for
    passing in multithreading task.
    """

    workflow: Workflow
    on: On
    params: DictData = field(compare=False, hash=False)
    queue: dict[str, list[datetime]] = field(compare=False, hash=False)
    running: dict[str, list[datetime]] = field(compare=False, hash=False)

    @catch_exceptions(cancel_on_failure=True)
    def release(
        self,
        log: Log | None = None,
        *,
        waiting_sec: int = 60,
        sleep_interval: int = 15,
    ) -> None:  # pragma: no cov
        """Workflow release, it will use with the same logic of
        `workflow.release` method.

        :param log: A log object for saving result logging from workflow
            execution process.
        :param waiting_sec: A second period value that allow workflow execute.
        :param sleep_interval: A second value that want to waiting until time
            to execute.
        """
        log: Log = log or FileLog
        wf: Workflow = self.workflow
        on: On = self.on

        gen: CronRunner = on.generate(
            datetime.now(tz=config.tz).replace(second=0, microsecond=0)
        )
        cron_tz: ZoneInfo = gen.tz

        # NOTE: get next schedule time that generate from now.
        next_time: datetime = gen.next

        # NOTE: get next utils it does not running.
        while log.is_pointed(wf.name, next_time, queue=self.running[wf.name]):
            next_time: datetime = gen.next

        logger.debug(
            f"({wf.run_id}) [CORE]: {wf.name!r} : {on.cronjob} : "
            f"{next_time:%Y-%m-%d %H:%M:%S}"
        )
        heappush(self.running[wf.name], next_time)

        if get_diff_sec(next_time, tz=cron_tz) > waiting_sec:
            logger.debug(
                f"({wf.run_id}) [CORE]: {wf.name!r} : {on.cronjob} "
                f": Does not closely >> {next_time:%Y-%m-%d %H:%M:%S}"
            )

            # NOTE: Add this next running datetime that not in period to queue
            #   and remove it to running.
            self.running[wf.name].remove(next_time)
            heappush(self.queue[wf.name], next_time)

            time.sleep(0.2)
            return

        logger.debug(
            f"({wf.run_id}) [CORE]: {wf.name!r} : {on.cronjob} : "
            f"Closely to run >> {next_time:%Y-%m-%d %H:%M:%S}"
        )

        # NOTE: Release when the time is nearly to schedule time.
        while (duration := get_diff_sec(next_time, tz=config.tz)) > (
            sleep_interval + 5
        ):
            logger.debug(
                f"({wf.run_id}) [CORE]: {wf.name!r} : {on.cronjob} "
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

        # WARNING:
        #   Re-create workflow object that use new running workflow ID.
        #
        runner: Workflow = wf.get_running_id(run_id=wf.new_run_id)
        rs: Result = runner.execute(
            params=param2template(self.params, release_params),
        )
        logger.debug(
            f"({runner.run_id}) [CORE]: {wf.name!r} : {on.cronjob} : "
            f"End release - {next_time:%Y-%m-%d %H:%M:%S}"
        )

        del runner

        # NOTE: Set parent ID on this result.
        rs.set_parent_run_id(wf.run_id)

        # NOTE: Save result to log object saving.
        rs_log: Log = log.model_validate(
            {
                "name": wf.name,
                "on": str(on.cronjob),
                "release": next_time,
                "context": rs.context,
                "parent_run_id": rs.run_id,
                "run_id": rs.run_id,
            }
        )
        rs_log.save(excluded=None)

        # NOTE: remove this release date from running
        self.running[wf.name].remove(next_time)

        # IMPORTANT:
        #   Add the next running datetime to workflow queue
        finish_time: datetime = datetime.now(tz=cron_tz).replace(
            second=0, microsecond=0
        )
        future_running_time: datetime = gen.next
        while (
            future_running_time in self.running[wf.name]
            or future_running_time in self.queue[wf.name]
            or future_running_time < finish_time
        ):  # pragma: no cov
            future_running_time: datetime = gen.next

        heappush(self.queue[wf.name], future_running_time)
        logger.debug(f"[CORE]: {'-' * 100}")

    def __eq__(self, other) -> bool:
        if isinstance(other, WorkflowTaskData):
            return (
                self.workflow.name == other.workflow.name
                and self.on.cronjob == other.on.cronjob
            )
        return NotImplemented


@catch_exceptions(cancel_on_failure=True)  # pragma: no cov
def workflow_task(
    workflow_tasks: list[WorkflowTaskData],
    stop: datetime,
    threads: dict[str, Thread],
) -> CancelJob | None:
    """Workflow task generator that create release pair of workflow and on to
    the threading in background.

        This workflow task will start every minute at ':02' second.

    :param workflow_tasks:
    :param stop: A stop datetime object that force stop running scheduler.
    :param threads:
    :rtype: CancelJob | None
    """
    start_date: datetime = datetime.now(tz=config.tz)
    start_date_minute: datetime = start_date.replace(second=0, microsecond=0)

    if start_date > stop.replace(tzinfo=config.tz):
        logger.info("[WORKFLOW]: Stop this schedule with datetime stopper.")
        while len(threads) > 0:
            logger.warning(
                "[WORKFLOW]: Waiting workflow release thread that still "
                "running in background."
            )
            time.sleep(15)
            workflow_monitor(threads)
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
    for task in workflow_tasks:

        # NOTE: Get incoming datetime queue.
        logger.debug(
            f"[WORKFLOW]: Current queue: {task.workflow.name!r} : "
            f"{list(queue2str(task.queue[task.workflow.name]))}"
        )

        # NOTE: Create minute unit value for any scheduler datetime that
        #   checking a workflow task should run in this datetime.
        current_running_time: datetime = start_date_minute.astimezone(
            tz=ZoneInfo(task.on.tz)
        )
        if (
            len(task.queue[task.workflow.name]) > 0
            and current_running_time != task.queue[task.workflow.name][0]
        ) or (
            task.on.next(current_running_time)
            != task.queue[task.workflow.name][0]
        ):
            logger.debug(
                f"[WORKFLOW]: Skip schedule "
                f"{current_running_time:%Y-%m-%d %H:%M:%S} "
                f"for : {task.workflow.name!r} : {task.on.cronjob}"
            )
            continue
        elif len(task.queue[task.workflow.name]) == 0:
            logger.warning(
                f"[WORKFLOW]: Queue is empty for : {task.workflow.name!r} : "
                f"{task.on.cronjob}"
            )
            continue

        # NOTE: Remove this datetime from queue.
        task.queue[task.workflow.name].pop(0)

        # NOTE: Create thread name that able to tracking with observe schedule
        #   job.
        thread_name: str = (
            f"{task.workflow.name}|{str(task.on.cronjob)}|"
            f"{current_running_time:%Y%m%d%H%M}"
        )
        wf_thread: Thread = Thread(
            target=task.release,
            name=thread_name,
            daemon=True,
        )

        threads[thread_name] = wf_thread

        wf_thread.start()

        delay()

    logger.debug(f"[WORKFLOW]: {'=' * 100}")


def workflow_monitor(threads: dict[str, Thread]) -> None:  # pragma: no cov
    """Workflow schedule for monitoring long running thread from the schedule
    control.

    :param threads: A mapping of Thread object and its name.
    :rtype: None
    """
    logger.debug(
        "[MONITOR]: Start checking long running workflow release task."
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
) -> list[str]:  # pragma: no cov
    """Workflow scheduler control.

    :param schedules: A list of workflow names that want to schedule running.
    :param stop: An datetime value that use to stop running schedule.
    :param externals: An external parameters that pass to Loader.
    :rtype: list[str]
    """
    try:
        from schedule import Scheduler
    except ImportError:
        raise ImportError(
            "Should install schedule package before use this module."
        ) from None

    schedule: Scheduler = Scheduler()
    start_date: datetime = datetime.now(tz=config.tz)

    # NOTE: Design workflow queue caching.
    #   ---
    #   {"workflow-name": [<release-datetime>, <release-datetime>, ...]}
    #
    wf_queue: dict[str, list[datetime]] = {}
    wf_running: dict[str, list[datetime]] = {}
    thread_releases: dict[str, Thread] = {}

    start_date_waiting: datetime = (start_date + timedelta(minutes=1)).replace(
        second=0, microsecond=0
    )

    # NOTE: Create pair of workflow and on from schedule model.
    workflow_tasks: list[WorkflowTaskData] = []
    for name in schedules:
        sch: Schedule = Schedule.from_loader(name, externals=externals)
        workflow_tasks.extend(
            sch.tasks(
                start_date_waiting,
                queue=wf_queue,
                running=wf_running,
                externals=externals,
            ),
        )

    # NOTE: This schedule job will start every minute at :02 seconds.
    (
        schedule.every(1)
        .minutes.at(":02")
        .do(
            workflow_task,
            workflow_tasks=workflow_tasks,
            stop=(stop or (start_date + config.stop_boundary_delta)),
            threads=thread_releases,
        )
        .tag("control")
    )

    # NOTE: Checking zombie task with schedule job will start every 5 minute.
    schedule.every(5).minutes.at(":10").do(
        workflow_monitor,
        threads=thread_releases,
    ).tag("monitor")

    # NOTE: Start running schedule
    logger.info(f"[WORKFLOW]: Start schedule: {schedules}")
    while True:
        schedule.run_pending()
        time.sleep(1)
        if not schedule.get_jobs("control"):
            schedule.clear("monitor")
            logger.warning(
                f"[WORKFLOW]: Workflow release thread: {thread_releases}"
            )
            logger.warning("[WORKFLOW]: Does not have any schedule jobs !!!")
            break

    logger.warning(
        f"Queue: {[list(queue2str(wf_queue[wf])) for wf in wf_queue]}"
    )
    logger.warning(
        f"Running: {[list(queue2str(wf_running[wf])) for wf in wf_running]}"
    )
    return schedules


def workflow_runner(
    stop: datetime | None = None,
    externals: DictData | None = None,
    excluded: list[str] | None = None,
) -> list[str]:  # pragma: no cov
    """Workflow application that running multiprocessing schedule with chunk of
    workflows that exists in config path.

    :param stop: A stop datetime object that force stop running scheduler.
    :param excluded:
    :param externals:

    :rtype: list[str]

        This function will get all workflows that include on value that was
    created in config path and chuck it with application config variable
    ``WORKFLOW_APP_MAX_SCHEDULE_PER_PROCESS`` env var to multiprocess executor
    pool.

        The current workflow logic that split to process will be below diagram:

        PIPELINES ==> process 01 ==> schedule 1 minute --> thread of release
                                                           workflow task 01 01
                                                       --> thread of release
                                                           workflow task 01 02
                  ==> process 02 ==> schedule 1 minute --> thread of release
                                                           workflow task 02 01
                                                       --> thread of release
                                                           workflow task 02 02
                  ==> ...
    """
    excluded: list[str] = excluded or []

    with ProcessPoolExecutor(
        max_workers=config.max_schedule_process,
    ) as executor:
        futures: list[Future] = [
            executor.submit(
                workflow_control,
                schedules=[load[0] for load in loader],
                stop=stop,
                externals=(externals or {}),
            )
            for loader in batch(
                Loader.finds(Schedule, excluded=excluded),
                n=config.max_schedule_per_process,
            )
        ]

        results: list[str] = []
        for future in as_completed(futures):
            if err := future.exception():
                logger.error(str(err))
                raise WorkflowException(str(err)) from err
            results.extend(future.result(timeout=1))
        return results
