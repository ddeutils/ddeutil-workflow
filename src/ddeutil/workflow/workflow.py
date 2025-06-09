# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Workflow module is the core module of this package. It keeps Release,
ReleaseQueue, and Workflow models.

    This package implement timeout strategy on the workflow execution layer only
because the main propose of this package is using Workflow to be orchestrator.
"""
from __future__ import annotations

import copy
import time
from concurrent.futures import (
    Future,
    ThreadPoolExecutor,
    as_completed,
)
from datetime import datetime
from enum import Enum
from pathlib import Path
from queue import Queue
from textwrap import dedent
from threading import Event
from typing import Any, Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from pydantic.functional_validators import field_validator, model_validator
from typing_extensions import Self

from . import get_status_from_error
from .__types import DictData
from .audits import Audit, get_audit
from .conf import YamlParser, dynamic
from .errors import WorkflowCancelError, WorkflowError, WorkflowTimeoutError
from .event import Crontab
from .job import Job
from .params import Param
from .result import (
    CANCEL,
    FAILED,
    SKIP,
    SUCCESS,
    WAIT,
    Result,
    Status,
    validate_statuses,
)
from .reusables import has_template, param2template
from .utils import (
    gen_id,
    replace_sec,
)


class ReleaseType(str, Enum):
    """Release Type Enum."""

    NORMAL = "normal"
    RERUN = "rerun"
    EVENT = "event"
    FORCE = "force"


NORMAL = ReleaseType.NORMAL
RERUN = ReleaseType.RERUN
EVENT = ReleaseType.EVENT
FORCE = ReleaseType.FORCE


class Workflow(BaseModel):
    """Workflow model that use to keep the `Job` and `Crontab` models.

        This is the main future of this project because it uses to be workflow
    data for running everywhere that you want or using it to scheduler task in
    background. It uses lightweight coding line from Pydantic Model and enhance
    execute method on it.
    """

    extras: DictData = Field(
        default_factory=dict,
        description="An extra parameters that want to override config values.",
    )

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
    on: list[Crontab] = Field(
        default_factory=list,
        description="A list of Crontab instance for this workflow schedule.",
    )
    jobs: dict[str, Job] = Field(
        default_factory=dict,
        description="A mapping of job ID and job model that already loaded.",
    )

    @classmethod
    def from_conf(
        cls,
        name: str,
        *,
        path: Optional[Path] = None,
        extras: DictData | None = None,
    ) -> Self:
        """Create Workflow instance from the Loader object that only receive
        an input workflow name. The loader object will use this workflow name to
        searching configuration data of this workflow model in conf path.

        :param name: (str) A workflow name that want to pass to Loader object.
        :param path: (Path) An override config path.
        :param extras: (DictData) An extra parameters that want to override core
            config values.

        :raise ValueError: If the type does not match with current object.

        :rtype: Self
        """
        load: YamlParser = YamlParser(name, path=path, extras=extras)

        # NOTE: Validate the config type match with current connection model
        if load.type != cls.__name__:
            raise ValueError(f"Type {load.type} does not match with {cls}")

        data: DictData = copy.deepcopy(load.data)
        data["name"] = name

        if extras:
            data["extras"] = extras

        cls.__bypass_on__(data, path=load.path, extras=extras)
        return cls.model_validate(obj=data)

    @classmethod
    def __bypass_on__(
        cls,
        data: DictData,
        path: Path,
        extras: DictData | None = None,
    ) -> DictData:
        """Bypass the on data to loaded config data.

        :param data: (DictData) A data to construct to this Workflow model.
        :param path: (Path) A config path.
        :param extras: (DictData) An extra parameters that want to override core
            config values.

        :rtype: DictData
        """
        if on := data.pop("on", []):
            if isinstance(on, str):
                on: list[str] = [on]
            if any(not isinstance(i, (dict, str)) for i in on):
                raise TypeError("The `on` key should be list of str or dict")

            # NOTE: Pass on value to SimLoad and keep on model object to the on
            #   field.
            data["on"] = [
                (
                    YamlParser(n, path=path, extras=extras).data
                    if isinstance(n, str)
                    else n
                )
                for n in on
            ]
        return data

    @model_validator(mode="before")
    def __prepare_model_before__(cls, data: Any) -> Any:
        """Prepare the params key in the data model before validating."""
        if isinstance(data, dict) and (params := data.pop("params", {})):
            data["params"] = {
                p: (
                    {"type": params[p]}
                    if isinstance(params[p], str)
                    else params[p]
                )
                for p in params
            }
        return data

    @field_validator("desc", mode="after")
    def __dedent_desc__(cls, value: str) -> str:
        """Prepare description string that was created on a template.

        :param value: A description string value that want to dedent.
        :rtype: str
        """
        return dedent(value.lstrip("\n"))

    @field_validator("on", mode="after")
    def __on_no_dup_and_reach_limit__(
        cls,
        value: list[Crontab],
    ) -> list[Crontab]:
        """Validate the on fields should not contain duplicate values and if it
        contains the every minute value more than one value, it will remove to
        only one value.

        :raise ValueError: If it has some duplicate value.

        :param value: A list of on object.

        :rtype: list[Crontab]
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
        set_tz: set[str] = {on.tz for on in value}
        if len(set_tz) > 1:
            raise ValueError(
                f"The on fields should not contain multiple timezone, "
                f"{list(set_tz)}."
            )

        if len(set_ons) > 10:
            raise ValueError(
                "The number of the on should not more than 10 crontabs."
            )
        return value

    @model_validator(mode="after")
    def __validate_jobs_need__(self) -> Self:
        """Validate each need job in any jobs should exist.

        :raise WorkflowError: If it has not exists need value in this
            workflow job.
        :raise ValueError: If the workflow name has template value.

        :rtype: Self
        """
        for job in self.jobs:
            if not_exist := [
                need for need in self.jobs[job].needs if need not in self.jobs
            ]:
                raise WorkflowError(
                    f"The needed jobs: {not_exist} do not found in "
                    f"{self.name!r}."
                )

            # NOTE: Copy the job model and set job ID to the job model.
            job_model = self.jobs[job].model_copy()
            job_model.id = job
            self.jobs[job] = job_model

        # VALIDATE: Validate workflow name should not dynamic with params
        #   template.
        if has_template(self.name):
            raise ValueError(
                f"Workflow name should not has any template, please check, "
                f"{self.name!r}."
            )

        return self

    def job(self, name: str) -> Job:
        """Return the workflow's Job model that getting by an input job's name
        or job's ID. This method will pass an extra parameter from this model
        to the returned Job model.

        :param name: (str) A job name or ID that want to get from a mapping of
            job models.

        :raise ValueError: If a name or ID does not exist on the jobs field.

        :rtype: Job
        :return: A job model that exists on this workflow by input name.
        """
        if name not in self.jobs:
            raise ValueError(
                f"A Job {name!r} does not exists in this workflow, "
                f"{self.name!r}"
            )
        job: Job = self.jobs[name]
        if self.extras:
            job.extras = self.extras
        return job

    def parameterize(self, params: DictData) -> DictData:
        """Prepare a passing parameters before use it in execution process.
        This method will validate keys of an incoming params with this object
        necessary params field and then create a jobs key to result mapping
        that will keep any execution result from its job.

            ... {
            ...     "params": <an-incoming-params>,
            ...     "jobs": {}
            ... }

        :param params: (DictData) A parameter data that receive from workflow
            execute method.

        :raise WorkflowError: If parameter value that want to validate does
            not include the necessary parameter that had required flag.

        :rtype: DictData
        :return: The parameter value that validate with its parameter fields and
            adding jobs key to this parameter.
        """
        # VALIDATE: Incoming params should have keys that set on this workflow.
        check_key: list[str] = [
            f"{k!r}"
            for k in self.params
            if (k not in params and self.params[k].required)
        ]
        if check_key:
            raise WorkflowError(
                f"Required Param on this workflow setting does not set: "
                f"{', '.join(check_key)}."
            )

        # NOTE: Mapping type of param before adding it to the `params` key.
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

    def validate_release(self, dt: datetime) -> datetime:
        """Validate the release datetime that should was replaced second and
        millisecond to 0 and replaced timezone to None before checking it match
        with the set `on` field.

        :param dt: (datetime) A datetime object that want to validate.

        :rtype: datetime
        """
        release: datetime = replace_sec(dt.replace(tzinfo=None))
        if not self.on:
            return release

        for on in self.on:
            if release == on.cronjob.schedule(release).next:
                return release
        raise WorkflowError(
            "Release datetime does not support for this workflow"
        )

    def release(
        self,
        release: datetime,
        params: DictData,
        *,
        release_type: ReleaseType = NORMAL,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        audit: type[Audit] = None,
        override_log_name: Optional[str] = None,
        result: Optional[Result] = None,
        timeout: int = 600,
        excluded: Optional[list[str]] = None,
    ) -> Result:
        """Release the workflow which is executes workflow with writing audit
        log tracking. The method is overriding parameter with the release
        templating that include logical date (release date), execution date,
        or running id to the params.

            This method allow workflow use audit object to save the execution
        result to audit destination like file audit to the local `./logs` path.

        Steps:
            - Initialize Release and validate ReleaseQueue.
            - Create release data for pass to parameter templating function.
            - Execute this workflow with mapping release data to its parameters.
            - Writing result audit

        :param release: (datetime) A release datetime.
        :param params: A workflow parameter that pass to execute method.
        :param release_type:
        :param run_id: (str) A workflow running ID.
        :param parent_run_id: (str) A parent workflow running ID.
        :param audit: An audit class that want to save the execution result.
        :param override_log_name: (str) An override logging name that use
            instead the workflow name.
        :param result: (Result) A result object for keeping context and status
            data.
        :param timeout: (int) A workflow execution time out in second unit.
        :param excluded: (list[str]) A list of key that want to exclude from
            audit data.

        :rtype: Result
        """
        audit: type[Audit] = audit or get_audit(extras=self.extras)
        name: str = override_log_name or self.name
        result: Result = Result.construct_with_rs_or_id(
            result,
            run_id=run_id,
            parent_run_id=parent_run_id,
            id_logic=name,
            extras=self.extras,
        )
        release: datetime = self.validate_release(dt=release)
        result.trace.info(
            f"[RELEASE]: Start {name!r} : {release:%Y-%m-%d %H:%M:%S}"
        )
        tz: ZoneInfo = dynamic("tz", extras=self.extras)
        values: DictData = param2template(
            params,
            params={
                "release": {
                    "logical_date": release,
                    "execute_date": datetime.now(tz=tz),
                    "run_id": result.run_id,
                }
            },
            extras=self.extras,
        )
        rs: Result = self.execute(
            params=values,
            parent_run_id=result.run_id,
            timeout=timeout,
        )
        result.catch(status=rs.status, context=rs.context)
        result.trace.info(
            f"[RELEASE]: End {name!r} : {release:%Y-%m-%d %H:%M:%S}"
        )
        result.trace.debug(f"[RELEASE]: Writing audit: {name!r}.")
        (
            audit(
                name=name,
                release=release,
                type=release_type,
                context=result.context,
                parent_run_id=result.parent_run_id,
                run_id=result.run_id,
                execution_time=result.alive_time(),
                extras=self.extras,
            ).save(excluded=excluded)
        )
        return result.catch(
            status=rs.status,
            context={
                "params": params,
                "release": {
                    "type": release_type,
                    "logical_date": release,
                },
                **{"jobs": result.context.pop("jobs", {})},
                **(
                    result.context["errors"]
                    if "errors" in result.context
                    else {}
                ),
            },
        )

    def execute_job(
        self,
        job: Job,
        params: DictData,
        *,
        result: Optional[Result] = None,
        event: Optional[Event] = None,
    ) -> tuple[Status, Result]:
        """Job execution with passing dynamic parameters from the main workflow
        execution to the target job object via job's ID.

            This execution is the minimum level of execution of this workflow
        model. It different with `self.execute` because this method run only
        one job and return with context of this job data.

            This method do not raise any error, and it will handle all exception
        from the job execution.

        :param job: (Job) A job model that want to execute.
        :param params: (DictData) A parameter data.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :rtype: tuple[Status, Result]
        """
        result: Result = result or Result(run_id=gen_id(self.name, unique=True))

        if event and event.is_set():
            error_msg: str = (
                "Job execution was canceled because the event was set "
                "before start job execution."
            )
            return CANCEL, result.catch(
                status=CANCEL,
                context={
                    "errors": WorkflowCancelError(error_msg).to_dict(),
                },
            )

        result.trace.info(f"[WORKFLOW]: Execute Job: {job.id!r}")
        rs: Result = job.execute(
            params=params,
            run_id=result.run_id,
            parent_run_id=result.parent_run_id,
            event=event,
        )
        job.set_outputs(rs.context, to=params)

        if rs.status == FAILED:
            error_msg: str = f"Job execution, {job.id!r}, was failed."
            return FAILED, result.catch(
                status=FAILED,
                context={
                    "errors": WorkflowError(error_msg).to_dict(),
                    **params,
                },
            )

        elif rs.status == CANCEL:
            error_msg: str = (
                f"Job execution, {job.id!r}, was canceled from the event after "
                f"end job execution."
            )
            return CANCEL, result.catch(
                status=CANCEL,
                context={
                    "errors": WorkflowCancelError(error_msg).to_dict(),
                    **params,
                },
            )

        return rs.status, result.catch(status=rs.status, context=params)

    def execute(
        self,
        params: DictData,
        *,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
        timeout: float = 3600,
        max_job_parallel: int = 2,
    ) -> Result:
        """Execute workflow with passing a dynamic parameters to all jobs that
        included in this workflow model with `jobs` field.

            The result of execution process for each job and stages on this
        workflow will keep in dict which able to catch out with all jobs and
        stages by dot annotation.

            For example with non-strategy job, when I want to use the output
        from previous stage, I can access it with syntax:

        ... ${job-id}.stages.${stage-id}.outputs.${key}
        ... ${job-id}.stages.${stage-id}.errors.${key}

            But example for strategy job:

        ... ${job-id}.strategies.${strategy-id}.stages.${stage-id}.outputs.${key}
        ... ${job-id}.strategies.${strategy-id}.stages.${stage-id}.errors.${key}

            This method already handle all exception class that can raise from
        the job execution. It will warp that error and keep it in the key `errors`
        at the result context.


            Execution   --> Ok      --> Result
                                        |-status: CANCEL
                                        ╰-context:
                                            ╰-errors:
                                                |-name: ...
                                                ╰-message: ...

                        --> Ok      --> Result
                                        |-status: FAILED
                                        ╰-context:
                                            ╰-errors:
                                                |-name: ...
                                                ╰-message: ...

                        --> Ok      --> Result
                                        ╰-status: SKIP

                        --> Ok      --> Result
                                        ╰-status: SUCCESS

        :param params: A parameter data that will parameterize before execution.
        :param run_id: (Optional[str]) A workflow running ID.
        :param parent_run_id: (Optional[str]) A parent workflow running ID.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.
        :param timeout: (float) A workflow execution time out in second unit
            that use for limit time of execution and waiting job dependency.
            This value does not force stop the task that still running more than
            this limit time. (Default: 60 * 60 seconds)
        :param max_job_parallel: (int) The maximum workers that use for job
            execution in `ThreadPoolExecutor` object. (Default: 2 workers)

        :rtype: Result
        """
        ts: float = time.monotonic()
        result: Result = Result.construct_with_rs_or_id(
            run_id=run_id,
            parent_run_id=parent_run_id,
            id_logic=self.name,
            extras=self.extras,
        )
        context: DictData = self.parameterize(params)
        event: Event = event or Event()
        max_job_parallel: int = dynamic(
            "max_job_parallel", f=max_job_parallel, extras=self.extras
        )
        result.trace.info(
            f"[WORKFLOW]: Execute: {self.name!r} ("
            f"{'parallel' if max_job_parallel > 1 else 'sequential'} jobs)"
        )
        if not self.jobs:
            result.trace.warning(f"[WORKFLOW]: {self.name!r} does not set jobs")
            return result.catch(status=SUCCESS, context=context)

        job_queue: Queue = Queue()
        for job_id in self.jobs:
            job_queue.put(job_id)

        not_timeout_flag: bool = True
        total_job: int = len(self.jobs)
        statuses: list[Status] = [WAIT] * total_job
        skip_count: int = 0
        sequence_statuses: list[Status] = []
        timeout: float = dynamic(
            "max_job_exec_timeout", f=timeout, extras=self.extras
        )
        result.catch(status=WAIT, context=context)
        if event and event.is_set():
            return result.catch(
                status=CANCEL,
                context={
                    "errors": WorkflowCancelError(
                        "Execution was canceled from the event was set before "
                        "workflow execution."
                    ).to_dict(),
                },
            )

        with ThreadPoolExecutor(max_job_parallel, "wf") as executor:
            futures: list[Future] = []

            while not job_queue.empty() and (
                not_timeout_flag := ((time.monotonic() - ts) < timeout)
            ):
                job_id: str = job_queue.get()
                job: Job = self.job(name=job_id)
                if (check := job.check_needs(context["jobs"])) == WAIT:
                    job_queue.task_done()
                    job_queue.put(job_id)
                    time.sleep(0.15)
                    continue
                elif check == FAILED:  # pragma: no cov
                    return result.catch(
                        status=FAILED,
                        context={
                            "status": FAILED,
                            "errors": WorkflowError(
                                f"Validate job trigger rule was failed with "
                                f"{job.trigger_rule.value!r}."
                            ).to_dict(),
                        },
                    )
                elif check == SKIP:  # pragma: no cov
                    result.trace.info(
                        f"[JOB]: Skip job: {job_id!r} from trigger rule."
                    )
                    job.set_outputs(output={"status": SKIP}, to=context)
                    job_queue.task_done()
                    skip_count += 1
                    continue

                if max_job_parallel > 1:
                    futures.append(
                        executor.submit(
                            self.execute_job,
                            job=job,
                            params=context,
                            result=result,
                            event=event,
                        ),
                    )
                    job_queue.task_done()
                    continue

                if len(futures) < 1:
                    futures.append(
                        executor.submit(
                            self.execute_job,
                            job=job,
                            params=context,
                            result=result,
                            event=event,
                        )
                    )
                elif (future := futures.pop(0)).done():
                    if e := future.exception():
                        sequence_statuses.append(get_status_from_error(e))
                    else:
                        st, _ = future.result()
                        sequence_statuses.append(st)
                    job_queue.put(job_id)
                elif future.cancelled():
                    sequence_statuses.append(CANCEL)
                    job_queue.put(job_id)
                elif future.running() or "state=pending" in str(future):
                    futures.insert(0, future)
                    job_queue.put(job_id)
                else:  # pragma: no cov
                    job_queue.put(job_id)
                    futures.insert(0, future)
                    result.trace.warning(
                        f"[WORKFLOW]: ... Execution non-threading not "
                        f"handle: {future}."
                    )

                job_queue.task_done()

            if not_timeout_flag:
                job_queue.join()
                for total, future in enumerate(as_completed(futures), start=0):
                    try:
                        statuses[total], _ = future.result()
                    except WorkflowError as e:
                        statuses[total] = get_status_from_error(e)

                # NOTE: Update skipped status from the job trigger.
                for i in range(skip_count):
                    statuses[total + 1 + i] = SKIP

                # NOTE: Update status from none-parallel job execution.
                for i, s in enumerate(sequence_statuses, start=0):
                    statuses[total + 1 + skip_count + i] = s

                return result.catch(
                    status=validate_statuses(statuses), context=context
                )

            event.set()
            for future in futures:
                future.cancel()

            result.trace.error(
                f"[WORKFLOW]: {self.name!r} was timeout because it use exec "
                f"time more than {timeout} seconds."
            )

            time.sleep(0.0025)

        return result.catch(
            status=FAILED,
            context={
                "errors": WorkflowTimeoutError(
                    f"{self.name!r} was timeout because it use exec time more "
                    f"than {timeout} seconds."
                ).to_dict(),
            },
        )

    def rerun(
        self,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
        timeout: float = 3600,
        max_job_parallel: int = 2,
    ) -> Result:
        """Re-Execute workflow with passing the error context data.

        :param context: A context result that get the failed status.
        :param parent_run_id: (Optional[str]) A parent workflow running ID.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.
        :param timeout: (float) A workflow execution time out in second unit
            that use for limit time of execution and waiting job dependency.
            This value does not force stop the task that still running more than
            this limit time. (Default: 60 * 60 seconds)
        :param max_job_parallel: (int) The maximum workers that use for job
            execution in `ThreadPoolExecutor` object. (Default: 2 workers)

        :rtype: Result
        """
        ts: float = time.monotonic()

        result: Result = Result.construct_with_rs_or_id(
            parent_run_id=parent_run_id,
            id_logic=self.name,
            extras=self.extras,
        )
        if context["status"] == SUCCESS:
            result.trace.info(
                "[WORKFLOW]: Does not rerun because it already executed with "
                "success status."
            )
            return result.catch(status=SUCCESS, context=context)

        err = context["errors"]
        result.trace.info(f"[WORKFLOW]: Previous error: {err}")

        event: Event = event or Event()
        max_job_parallel: int = dynamic(
            "max_job_parallel", f=max_job_parallel, extras=self.extras
        )
        result.trace.info(
            f"[WORKFLOW]: Execute: {self.name!r} ("
            f"{'parallel' if max_job_parallel > 1 else 'sequential'} jobs)"
        )
        if not self.jobs:
            result.trace.warning(f"[WORKFLOW]: {self.name!r} does not set jobs")
            return result.catch(status=SUCCESS, context=context)

        job_queue: Queue = Queue()
        for job_id in self.jobs:
            job_queue.put(job_id)

        not_timeout_flag: bool = True
        total_job: int = len(self.jobs)
        statuses: list[Status] = [WAIT] * total_job
        skip_count: int = 0
        sequence_statuses: list[Status] = []
        timeout: float = dynamic(
            "max_job_exec_timeout", f=timeout, extras=self.extras
        )

        # NOTE: Prepare the new context for rerun process.
        jobs: DictData = context.get("jobs")
        new_context: DictData = {
            "params": context["params"].copy(),
            "jobs": {j: jobs[j] for j in jobs if jobs[j]["status"] == SUCCESS},
        }

        result.catch(status=WAIT, context=new_context)
        if event and event.is_set():
            return result.catch(
                status=CANCEL,
                context={
                    "errors": WorkflowCancelError(
                        "Execution was canceled from the event was set before "
                        "workflow execution."
                    ).to_dict(),
                },
            )

        with ThreadPoolExecutor(max_job_parallel, "wf") as executor:
            futures: list[Future] = []

            while not job_queue.empty() and (
                not_timeout_flag := ((time.monotonic() - ts) < timeout)
            ):
                job_id: str = job_queue.get()
                job: Job = self.job(name=job_id)
                if (check := job.check_needs(new_context["jobs"])) == WAIT:
                    job_queue.task_done()
                    job_queue.put(job_id)
                    time.sleep(0.15)
                    continue
                elif check == FAILED:  # pragma: no cov
                    return result.catch(
                        status=FAILED,
                        context={
                            "status": FAILED,
                            "errors": WorkflowError(
                                f"Validate job trigger rule was failed with "
                                f"{job.trigger_rule.value!r}."
                            ).to_dict(),
                        },
                    )
                elif check == SKIP:  # pragma: no cov
                    result.trace.info(
                        f"[JOB]: Skip job: {job_id!r} from trigger rule."
                    )
                    job.set_outputs(output={"status": SKIP}, to=new_context)
                    job_queue.task_done()
                    skip_count += 1
                    continue

                if max_job_parallel > 1:
                    futures.append(
                        executor.submit(
                            self.execute_job,
                            job=job,
                            params=new_context,
                            result=result,
                            event=event,
                        ),
                    )
                    job_queue.task_done()
                    continue

                if len(futures) < 1:
                    futures.append(
                        executor.submit(
                            self.execute_job,
                            job=job,
                            params=new_context,
                            result=result,
                            event=event,
                        )
                    )
                elif (future := futures.pop(0)).done():
                    if e := future.exception():
                        sequence_statuses.append(get_status_from_error(e))
                    else:
                        st, _ = future.result()
                        sequence_statuses.append(st)
                    job_queue.put(job_id)
                elif future.cancelled():
                    sequence_statuses.append(CANCEL)
                    job_queue.put(job_id)
                elif future.running() or "state=pending" in str(future):
                    futures.insert(0, future)
                    job_queue.put(job_id)
                else:  # pragma: no cov
                    job_queue.put(job_id)
                    futures.insert(0, future)
                    result.trace.warning(
                        f"[WORKFLOW]: ... Execution non-threading not "
                        f"handle: {future}."
                    )

                job_queue.task_done()

            if not_timeout_flag:
                job_queue.join()
                for total, future in enumerate(as_completed(futures), start=0):
                    try:
                        statuses[total], _ = future.result()
                    except WorkflowError as e:
                        statuses[total] = get_status_from_error(e)

                # NOTE: Update skipped status from the job trigger.
                for i in range(skip_count):
                    statuses[total + 1 + i] = SKIP

                # NOTE: Update status from none-parallel job execution.
                for i, s in enumerate(sequence_statuses, start=0):
                    statuses[total + 1 + skip_count + i] = s

                return result.catch(
                    status=validate_statuses(statuses), context=new_context
                )

            event.set()
            for future in futures:
                future.cancel()

            result.trace.error(
                f"[WORKFLOW]: {self.name!r} was timeout because it use exec "
                f"time more than {timeout} seconds."
            )

            time.sleep(0.0025)

        return result.catch(
            status=FAILED,
            context={
                "errors": WorkflowTimeoutError(
                    f"{self.name!r} was timeout because it use exec time more "
                    f"than {timeout} seconds."
                ).to_dict(),
            },
        )
