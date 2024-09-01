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
from concurrent.futures import (
    Future,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
)
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
from heapq import heappush
from queue import Queue
from textwrap import dedent
from threading import Thread
from typing import Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic.functional_validators import field_validator, model_validator
from typing_extensions import Self

try:
    from schedule import CancelJob
except ImportError:
    CancelJob = None

from .__types import DictData
from .cron import CronRunner
from .exceptions import JobException, PipelineException, WorkflowException
from .job import Job
from .log import FileLog, Log, get_logger
from .on import On
from .utils import (
    Loader,
    Param,
    Result,
    batch,
    delay,
    gen_id,
    get_diff_sec,
    has_template,
    param2template,
)

load_dotenv()
logger = get_logger("ddeutil.workflow")
logging.getLogger("schedule").setLevel(logging.INFO)


__all__ = (
    "Pipeline",
    "PipelineSchedule",
    "PipelineTask",
    "Schedule",
    "workflow",
    "workflow_task",
)


class Pipeline(BaseModel):
    """Pipeline Model this is the main future of this project because it use to
    be workflow data for running everywhere that you want or using it to
    scheduler task in background. It use lightweight coding line from Pydantic
    Model and enhance execute method on it.
    """

    name: str = Field(description="A pipeline name.")
    desc: Optional[str] = Field(
        default=None,
        description=(
            "A pipeline description that can be string of markdown content."
        ),
    )
    params: dict[str, Param] = Field(
        default_factory=dict,
        description="A parameters that want to use on this pipeline.",
    )
    on: list[On] = Field(
        default_factory=list,
        description="A list of On instance for this pipeline schedule.",
    )
    jobs: dict[str, Job] = Field(
        default_factory=dict,
        description="A mapping of job ID and job model that already loaded.",
    )
    run_id: Optional[str] = Field(
        default=None,
        description="A running pipeline ID.",
        repr=False,
        exclude=True,
    )

    @property
    def new_run_id(self) -> str:
        """Running ID of this pipeline that always generate new unique value."""
        return gen_id(self.name, unique=True)

    @classmethod
    def from_loader(
        cls,
        name: str,
        externals: DictData | None = None,
    ) -> Self:
        """Create Pipeline instance from the Loader object that only receive
        an input pipeline name. The loader object will use this pipeline name to
        searching configuration data of this pipeline model in conf path.

        :param name: A pipeline name that want to pass to Loader object.
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
    def __bypass_on(cls, data: DictData, externals: DictData | None = None):
        """Bypass the on data to loaded config data."""
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
    def __prepare_params(cls, values: DictData) -> DictData:
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
    def ___prepare_desc(cls, value: str) -> str:
        """Prepare description string that was created on a template."""
        return dedent(value)

    @model_validator(mode="after")
    def __validate_jobs_need_and_prepare_running_id(self):
        """Validate each need job in any jobs should exists."""
        for job in self.jobs:
            if not_exist := [
                need for need in self.jobs[job].needs if need not in self.jobs
            ]:
                raise PipelineException(
                    f"This needed jobs: {not_exist} do not exist in this "
                    f"pipeline, {self.name!r}"
                )

            # NOTE: update a job id with its job id from pipeline template
            self.jobs[job].id = job

        if self.run_id is None:
            self.run_id = self.new_run_id

        # VALIDATE: Validate pipeline name should not dynamic with params
        #   template.
        if has_template(self.name):
            raise ValueError(
                f"Pipeline name should not has any template, please check, "
                f"{self.name!r}."
            )

        return self

    def get_running_id(self, run_id: str) -> Self:
        """Return Pipeline model object that changing pipeline running ID with
        an input running ID.

        :param run_id: A replace pipeline running ID.
        :rtype: Self
        """
        return self.model_copy(update={"run_id": run_id})

    def job(self, name: str) -> Job:
        """Return Job model that exists on this pipeline.

        :param name: A job name that want to get from a mapping of job models.
        :type name: str

        :rtype: Job
        :returns: A job model that exists on this pipeline by input name.
        """
        if name not in self.jobs:
            raise ValueError(
                f"A Job {name!r} does not exists in this pipeline, "
                f"{self.name!r}"
            )
        return self.jobs[name]

    def parameterize(self, params: DictData) -> DictData:
        """Prepare parameters before passing to execution process. This method
        will create jobs key to params mapping that will keep any result from
        job execution.

        :param params: A parameter mapping that receive from pipeline execution.
        :rtype: DictData
        """
        # VALIDATE: Incoming params should have keys that set on this pipeline.
        if check_key := tuple(
            f"{k!r}"
            for k in self.params
            if (k not in params and self.params[k].required)
        ):
            raise PipelineException(
                f"Required Param on this pipeline setting does not set: "
                f"{', '.join(check_key)}."
            )

        # NOTE: mapping type of param before adding it to params variable.
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
        """Start running pipeline with the on schedule in period of 30 minutes.
        That mean it will still running at background 30 minutes until the
        schedule matching with its time.

            This method allow pipeline use log object to save the execution
        result to log destination like file log to local `/logs` directory.

        :param on: An on schedule value.
        :param params: A pipeline parameter that pass to execute method.
        :param queue: A list of release time that already running.
        :param waiting_sec: A second period value that allow pipeline execute.
        :param sleep_interval: A second value that want to waiting until time
            to execute.
        :param log: A log object that want to save execution result.
        :rtype: Result
        """
        log: Log = log or FileLog
        tz: ZoneInfo = ZoneInfo(os.getenv("WORKFLOW_CORE_TIMEZONE", "UTC"))
        gen: CronRunner = on.generate(
            datetime.now(tz=tz).replace(second=0, microsecond=0)
            + timedelta(seconds=1)
        )
        cron_tz: ZoneInfo = gen.tz

        # NOTE: get next schedule time that generate from now.
        next_time: datetime = gen.next

        # NOTE: get next utils it does not logger.
        while log.is_pointed(self.name, next_time, queue=queue):
            next_time: datetime = gen.next

        # NOTE: push this next running time to log queue
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
                    "poking": {"skipped": [str(on.cronjob)], "run": []},
                },
            )

        logger.debug(
            f"({self.run_id}) [CORE]: {self.name!r} : {on.cronjob} : "
            f"Closely to run >> {next_time:%Y-%m-%d %H:%M:%S}"
        )

        # NOTE: Release when the time is nearly to schedule time.
        while (duration := get_diff_sec(next_time, tz=cron_tz)) > (
            sleep_interval + 5
        ):
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

        # WARNING: Re-create pipeline object that use new running pipeline
        #   ID.
        runner: Self = self.get_running_id(run_id=self.new_run_id)
        rs: Result = runner.execute(
            params=param2template(params, release_params),
        )
        logger.debug(
            f"({runner.run_id}) [CORE]: {self.name!r} : {on.cronjob} : "
            f"End release {next_time:%Y-%m-%d %H:%M:%S}"
        )

        # NOTE: Delete a copied pipeline instance for saving memory.
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
                "poking": {"skipped": [], "run": [str(on.cronjob)]},
            },
        )

    def poke(
        self,
        params: DictData | None = None,
        *,
        log: Log | None = None,
    ) -> list[Result]:
        """Poke pipeline with threading executor pool for executing with all its
        schedules that was set on the `on` value. This method will observe its
        schedule that nearing to run with the ``self.release()`` method.

        :param params: A parameters that want to pass to the release method.
        :param log: A log object that want to use on this poking process.
        :rtype: list[Result]
        """
        logger.info(
            f"({self.run_id}) [POKING]: Start Poking: {self.name!r} ..."
        )

        # NOTE: If this pipeline does not set the on schedule, it will return
        #   empty result.
        if len(self.on) == 0:
            return []

        params: DictData = params or {}
        queue: list[datetime] = []
        results: list[Result] = []

        wk: int = int(os.getenv("WORKFLOW_CORE_MAX_PIPELINE_POKING") or "4")
        with ThreadPoolExecutor(max_workers=wk) as executor:
            # TODO: If I want to run infinite loop.
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
                delay()

            # WARNING: This poking method does not allow to use fail-fast logic
            #   to catching parallel execution result.
            for future in as_completed(futures):
                results.append(future.result(timeout=60))

        if len(queue) > 0:
            logger.error(
                f"({self.run_id}) [POKING]: Log Queue does empty when poking "
                f"process was finishing."
            )

        return results

    def execute_job(
        self,
        job: str,
        params: DictData,
    ) -> Result:
        """Job Executor that use on pipeline executor.

        :param job: A job ID that want to execute.
        :param params: A params that was parameterized from pipeline execution.
        :rtype: Result
        """
        # VALIDATE: check a job ID that exists in this pipeline or not.
        if job not in self.jobs:
            raise PipelineException(
                f"The job ID: {job} does not exists on {self.name!r} pipeline."
            )
        try:
            logger.info(f"({self.run_id}) [PIPELINE]: Start execute: {job!r}")

            # IMPORTANT:
            #   Change any job running IDs to this pipeline running ID.
            job_obj: Job = self.jobs[job].get_running_id(self.run_id)
            j_rs: Result = job_obj.execute(params=params)

        except JobException as err:
            raise PipelineException(f"{job}: JobException: {err}") from None

        return Result(
            status=j_rs.status,
            context={job: job_obj.set_outputs(j_rs.context)},
        )

    def execute(
        self,
        params: DictData | None = None,
        *,
        timeout: int = 60,
    ) -> Result:
        """Execute pipeline with passing dynamic parameters to any jobs that
        included in the pipeline.

        :param params: An input parameters that use on pipeline execution that
            will parameterize before using it.
        :param timeout: A pipeline execution time out in second unit that use
            for limit time of execution and waiting job dependency.
        :rtype: Result

        See Also:
        ---

            The result of execution process for each jobs and stages on this
        pipeline will keeping in dict which able to catch out with all jobs and
        stages by dot annotation.

            For example, when I want to use the output from previous stage, I
        can access it with syntax:

            ... ${job-name}.stages.${stage-id}.outputs.${key}

        """
        logger.info(f"({self.run_id}) [CORE]: Start Execute: {self.name!r} ...")
        params: DictData = params or {}
        ts: float = time.monotonic()

        # NOTE: It should not do anything if it does not have job.
        if not self.jobs:
            logger.warning(
                f"({self.run_id}) [PIPELINE]: This pipeline: {self.name!r} "
                f"does not have any jobs"
            )
            return Result(status=0, context=params)

        # NOTE: Create a job queue that keep the job that want to running after
        #   it dependency condition.
        jq: Queue = Queue()
        for job_id in self.jobs:
            jq.put(job_id)

        # NOTE: Create result context that will pass this context to any
        #   execution dependency.
        context: DictData = self.parameterize(params)
        try:
            worker: int = int(os.getenv("WORKFLOW_CORE_MAX_JOB_PARALLEL", "2"))
            (
                self.__exec_non_threading(context, ts, jq, timeout=timeout)
                if worker == 1
                else self.__exec_threading(
                    context, ts, jq, worker=worker, timeout=timeout
                )
            )
            return Result(status=0, context=context)
        except PipelineException as err:
            context.update(
                {"error_message": f"{err.__class__.__name__}: {err}"}
            )
            return Result(status=1, context=context)

    def __exec_threading(
        self,
        context: DictData,
        ts: float,
        job_queue: Queue,
        *,
        worker: int = 2,
        timeout: int = 600,
    ) -> DictData:
        """Pipeline threading execution.

        :param context: A context pipeline data that want to downstream passing.
        :param ts: A start timestamp that use for checking execute time should
            timeout.
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
                    job_queue.put(job_id)
                    time.sleep(0.25)
                    continue

                futures.append(
                    executor.submit(
                        self.execute_job,
                        job_id,
                        params=copy.deepcopy(context),
                    ),
                )
                job_queue.task_done()

            # NOTE: Wait for all items to finish processing
            job_queue.join()

            for future in as_completed(futures):
                if err := future.exception():
                    logger.error(f"{err}")
                    raise PipelineException(f"{err}")

                # NOTE: Update job result to pipeline result.
                context["jobs"].update(future.result(timeout=20).conext)

        if not_time_out_flag:
            return context

        # NOTE: Raise timeout error.
        logger.warning(
            f"({self.run_id}) [PIPELINE]: Execution of pipeline, {self.name!r} "
            f", was timeout"
        )
        raise PipelineException(
            f"Execution of pipeline: {self.name} was timeout"
        )

    def __exec_non_threading(
        self,
        context: DictData,
        ts: float,
        job_queue: Queue,
        *,
        timeout: int = 600,
    ) -> DictData:
        """Pipeline non-threading execution that use sequential job running
        and waiting previous run successful.

        :param context: A context pipeline data that want to downstream passing.
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

            # NOTE:
            if any(need not in context["jobs"] for need in job.needs):
                job_queue.put(job_id)
                time.sleep(0.25)
                continue

            # NOTE: Start job execution.
            job_rs = self.execute_job(job_id, params=copy.deepcopy(context))
            context["jobs"].update(job_rs.context)
            job_queue.task_done()

        # NOTE: Wait for all items to finish processing
        job_queue.join()

        if not_time_out_flag:
            return context

        # NOTE: Raise timeout error.
        logger.warning(
            f"({self.run_id}) [PIPELINE]: Execution of pipeline was timeout"
        )
        raise PipelineException(
            f"Execution of pipeline: {self.name} was timeout"
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
        *,
        externals: DictData | None = None,
    ) -> list[PipelineTask]:
        """Generate Task from the current datetime.

        :param start_date: A start date that get from the workflow schedule.
        :param queue: A mapping of name and list of datetime for queue.
        :param running: A mapping of name and list of datetime for running.
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
                logger.exception(err)
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
                logger.exception(err)
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
    params: DictData = field(compare=False, hash=False)
    queue: list[datetime] = field(compare=False, hash=False)
    running: list[datetime] = field(compare=False, hash=False)

    @catch_exceptions_method(cancel_on_failure=True)
    def release(self, log: Log | None = None) -> None:
        """Pipeline release, it will use with the same logic of
        `pipeline.release` method.

        :param log: A log object.
        """
        tz: ZoneInfo = ZoneInfo(os.getenv("WORKFLOW_CORE_TIMEZONE", "UTC"))
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
        while log.is_pointed(
            pipeline.name, next_time, queue=self.running[pipeline.name]
        ):
            next_time: datetime = gen.next

        logger.debug(
            f"({pipeline.run_id}) [CORE]: {pipeline.name!r} : {on.cronjob} : "
            f"{next_time:%Y-%m-%d %H:%M:%S}"
        )
        heappush(self.running[pipeline.name], next_time)

        if get_diff_sec(next_time, tz=cron_tz) > 55:
            logger.debug(
                f"({pipeline.run_id}) [CORE]: {pipeline.name!r} : {on.cronjob} "
                f": Does not closely >> {next_time:%Y-%m-%d %H:%M:%S}"
            )

            # NOTE: Add this next running datetime that not in period to queue
            #   and remove it to running.
            self.running[pipeline.name].remove(next_time)
            heappush(self.queue[pipeline.name], next_time)

            time.sleep(0.2)
            return

        logger.debug(
            f"({pipeline.run_id}) [CORE]: {pipeline.name!r} : {on.cronjob} : "
            f"Closely to run >> {next_time:%Y-%m-%d %H:%M:%S}"
        )

        # NOTE: Release when the time is nearly to schedule time.
        while (duration := get_diff_sec(next_time, tz=tz)) > (15 + 5):
            logger.debug(
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
        logger.debug(
            f"({runner.run_id}) [CORE]: {pipeline.name!r} : {on.cronjob} : "
            f"End release - {next_time:%Y-%m-%d %H:%M:%S}"
        )

        del runner

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
        logger.debug(f"[CORE]: {'-' * 100}")

    def __eq__(self, other):
        if isinstance(other, PipelineTask):
            return (
                self.pipeline.name == other.pipeline.name
                and self.on.cronjob == other.on.cronjob
            )


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
    tz: ZoneInfo = ZoneInfo(os.getenv("WORKFLOW_CORE_TIMEZONE", "UTC"))
    start_date: datetime = datetime.now(tz=tz)
    start_date_minute: datetime = start_date.replace(second=0, microsecond=0)

    if start_date > stop.replace(tzinfo=tz):
        logger.info("[WORKFLOW]: Stop this schedule with datetime stopper.")
        while len(threads) > 0:
            logger.warning(
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
        logger.debug(
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
            logger.debug(
                f"[WORKFLOW]: Skip schedule "
                f"{current_running_time:%Y-%m-%d %H:%M:%S} "
                f"for : {task.pipeline.name!r} : {task.on.cronjob}"
            )
            continue
        elif len(task.queue[task.pipeline.name]) == 0:
            logger.warning(
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

    logger.debug(f"[WORKFLOW]: {'=' * 100}")


def workflow_long_running_task(threads: dict[str, Thread]) -> None:
    """Workflow schedule for monitoring long running thread from the schedule
    control.

    :param threads: A mapping of Thread object and its name.
    :rtype: None
    """
    logger.debug(
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
    try:
        from schedule import Scheduler
    except ImportError:
        raise ImportError(
            "Should install schedule package before use this module."
        ) from None

    tz: ZoneInfo = ZoneInfo(os.getenv("WORKFLOW_CORE_TIMEZONE", "UTC"))
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
            sch.tasks(
                start_date_waiting, wf_queue, wf_running, externals=externals
            ),
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
    logger.info(f"[WORKFLOW]: Start schedule: {schedules}")
    while True:
        schedule.run_pending()
        time.sleep(1)
        if not schedule.get_jobs("control"):
            schedule.clear("monitor")
            logger.warning(
                f"[WORKFLOW]: Pipeline release thread: {thread_releases}"
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
                Loader.finds(Schedule, excluded=excluded),
                n=int(os.getenv("WORKFLOW_APP_SCHEDULE_PER_PROCESS") or "100"),
            )
        ]

        results: list[str] = []
        for future in as_completed(futures):
            if err := future.exception():
                logger.error(str(err))
                raise WorkflowException(str(err)) from err
            results.extend(future.result(timeout=1))
        return results


if __name__ == "__main__":
    workflow_rs: list[str] = workflow()
    logger.info(f"[WORKFLOW]: Application run success: {workflow_rs}")
