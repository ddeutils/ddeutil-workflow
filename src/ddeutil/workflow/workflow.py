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
import logging
import time
from concurrent.futures import (
    Future,
    ThreadPoolExecutor,
    as_completed,
)
from datetime import datetime, timedelta
from heapq import heappush
from queue import Queue
from textwrap import dedent
from typing import Optional

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
    has_template,
    param2template,
)

P = ParamSpec("P")
logger = get_logger("ddeutil.workflow")

# NOTE: Adjust logging level on the schedule package.
logging.getLogger("schedule").setLevel(logging.INFO)


__all__: TupleStr = ("Workflow",)


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
        runner: CronRunner,
        params: DictData,
        queue: list[datetime],
        *,
        waiting_sec: int = 60,
        sleep_interval: int = 15,
        log: type[Log] = None,
    ) -> Result:
        """Start running workflow with the on schedule in period of 30 minutes.
        That mean it will still running at background 30 minutes until the
        schedule matching with its time.

            This method allow workflow use log object to save the execution
        result to log destination like file log to local `/logs` directory.

            I will add sleep with 0.15 seconds on every step that interact with
        the queue object.

        :param runner: A CronRunner instance.
        :param params: A workflow parameter that pass to execute method.
        :param queue: A list of release time that already running.
        :param waiting_sec: A second period value that allow workflow execute.
        :param sleep_interval: A second value that want to waiting until time
            to execute.
        :param log: A log class that want to save the execution result.

        :rtype: Result
        """
        log: type[Log] = log or FileLog
        logger.debug(
            f"({self.run_id}) [CORE]: {self.name!r}: {runner.cron} : run with "
            f"queue id: {id(queue)}"
        )

        # NOTE: get next schedule time that generate from now.
        next_time: datetime = runner.date

        # NOTE: While-loop to getting next until it does not logger.
        while log.is_pointed(self.name, next_time) or (next_time in queue):
            next_time: datetime = runner.next

        # NOTE: Heap-push this next running time to log queue list.
        heappush(queue, next_time)
        time.sleep(0.15)

        # VALIDATE: Check the different time between the next schedule time and
        #   now that less than waiting period (second unit).
        if get_diff_sec(next_time, tz=runner.tz) > waiting_sec:
            logger.debug(
                f"({self.run_id}) [CORE]: {self.name!r} : {runner.cron} : "
                f"Does not closely >> {next_time:%Y-%m-%d %H:%M:%S}"
            )

            # NOTE: Remove next datetime from queue.
            queue.remove(next_time)

            time.sleep(0.15)
            return Result(
                status=0,
                context={
                    "params": params,
                    "release": {
                        "status": "skipped",
                        "cron": str(runner.cron),
                        "runner": runner,
                    },
                },
            )

        logger.debug(
            f"({self.run_id}) [CORE]: {self.name!r} : {runner.cron} : "
            f"Closely to run >> {next_time:%Y-%m-%d %H:%M:%S}"
        )

        # NOTE: Release when the time is nearly to schedule time.
        while (duration := get_diff_sec(next_time, tz=runner.tz)) > (
            sleep_interval + 5
        ):  # pragma: no cov
            logger.debug(
                f"({self.run_id}) [CORE]: {self.name!r} : {runner.cron} : "
                f"Sleep until: {duration}"
            )
            time.sleep(sleep_interval)

        time.sleep(0.15)

        # NOTE: Release parameter that use to change if params has templating.
        release_params: DictData = {"release": {"logical_date": next_time}}

        # WARNING: Re-create workflow object that use new running workflow ID.
        workflow: Self = self.get_running_id(run_id=self.new_run_id)
        rs: Result = workflow.execute(
            params=param2template(params, release_params),
        )
        logger.debug(
            f"({workflow.run_id}) [CORE]: {self.name!r} : {runner.cron} : "
            f"End release {next_time:%Y-%m-%d %H:%M:%S}"
        )

        # NOTE: Delete a copied workflow instance for saving memory.
        del workflow

        rs.set_parent_run_id(self.run_id)
        rs_log: Log = log.model_validate(
            {
                "name": self.name,
                "on": str(runner.cron),
                "release": next_time,
                "context": rs.context,
                "parent_run_id": rs.run_id,
                "run_id": rs.run_id,
            }
        )

        # NOTE: Saving execution result to destination of the input log object.
        rs_log.save(excluded=None)

        # NOTE: Remove queue.
        queue.remove(next_time)

        future_running_time: datetime = runner.next
        logger.debug(
            f"({rs.run_id}) [CORE]: {self.name!r} : {runner.cron} : "
            f"Next release {future_running_time:%Y-%m-%d %H:%M:%S}"
        )

        time.sleep(0.15)
        return Result(
            status=0,
            context={
                "params": params,
                "release": {
                    "status": "run",
                    "cron": str(runner.cron),
                    "runner": runner,
                },
            },
        )

    def poke(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        params: DictData | None = None,
        *,
        log: Log | None = None,
    ) -> list[Result]:
        """Poke workflow with the ``on`` field with threading executor pool for
        executing with all its schedules that was set on the `on` value.
        This method will observe its schedule that nearing to run with the
        ``self.release()`` method.

        :param start_date: A start datetime object.
        :param end_date: A end datetime object.
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
            logger.info(
                f"({self.run_id}) [POKING]: {self.name!r} does not have any "
                f"schedule to run."
            )
            return []

        params: DictData = params or {}
        queue: list[datetime] = []
        results: list[Result] = []

        start_date: datetime = start_date or datetime.now(tz=config.tz).replace(
            second=0, microsecond=0
        ) + timedelta(seconds=1)
        end_date: datetime = end_date or start_date + timedelta(days=1)

        if end_date <= start_date:
            raise WorkflowException(
                "end_date of poking should not less or equal than start date."
            )

        runners: list[CronRunner] = [
            runner
            for on in self.on
            if (runner := on.next(start_date)).date <= end_date
        ]

        with ThreadPoolExecutor(
            max_workers=config.max_poking_pool_worker,
            thread_name_prefix="workflow_poking_",
        ) as executor:

            futures: list[Future] = []

            # NOTE: For-loop the on values that exists in this workflow
            #   object.
            for runner in runners:

                futures.append(
                    executor.submit(
                        self.release,
                        runner=runner,
                        params=params,
                        log=log,
                        queue=queue,
                    )
                )

                # NOTE: Delay release date because it run so fast and making
                #   queue object can not handle release date that will
                #   duplicate by the cron runner object.
                delay(second=0.15)

            # WARNING: This poking method does not allow to use fail-fast
            #   logic to catching parallel execution result.
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
