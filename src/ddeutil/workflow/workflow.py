# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Workflow Core Module.

This module contains the core workflow orchestration functionality, including
the Workflow model, release management, and workflow execution strategies.

The workflow system implements timeout strategy at the workflow execution layer
because the main purpose is to use Workflow as an orchestrator for complex
job execution scenarios.

Classes:
    Workflow: Main workflow orchestration class
    ReleaseType: Enumeration for different release types

Constants:
    NORMAL: Normal release execution
    RERUN: Re-execution of failed workflows
    EVENT: Event-triggered execution
    FORCE: Force execution regardless of conditions
"""
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
from threading import Event as ThreadEvent
from typing import Any, Optional, Union

from pydantic import BaseModel, Field
from pydantic.functional_validators import field_validator, model_validator
from typing_extensions import Self

from .__types import DictData
from .audits import Audit, get_audit_model
from .conf import YamlParser, dynamic
from .errors import WorkflowCancelError, WorkflowError, WorkflowTimeoutError
from .event import Event
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
    catch,
    get_status_from_error,
    validate_statuses,
)
from .reusables import has_template, param2template
from .traces import TraceManager, get_trace
from .utils import (
    UTC,
    gen_id,
    get_dt_now,
    replace_sec,
)


class ReleaseType(str, Enum):
    """Release type enumeration for workflow execution modes.

    This enum defines the different types of workflow releases that can be
    triggered, each with specific behavior and use cases.

    Attributes:
        NORMAL: Standard workflow release execution
        RERUN: Re-execution of previously failed workflow
        EVENT: Event-triggered workflow execution
        FORCE: Forced execution bypassing normal conditions
    """

    NORMAL = "normal"
    RERUN = "rerun"
    EVENT = "event"
    FORCE = "force"


NORMAL = ReleaseType.NORMAL
RERUN = ReleaseType.RERUN
EVENT = ReleaseType.EVENT
FORCE = ReleaseType.FORCE


class Workflow(BaseModel):
    """Main workflow orchestration model for job and schedule management.

    The Workflow class is the core component of the workflow orchestration system.
    It manages job execution, scheduling via cron expressions, parameter handling,
    and provides comprehensive execution capabilities for complex workflows.

    This class extends Pydantic BaseModel to provide robust data validation and
    serialization while maintaining lightweight performance characteristics.

    Attributes:
        extras (dict): Extra parameters for overriding configuration values
        name (str): Unique workflow identifier
        desc (str, optional): Workflow description supporting markdown content
        params (dict[str, Param]): Parameter definitions for the workflow
        on (list[Crontab]): Schedule definitions using cron expressions
        jobs (dict[str, Job]): Collection of jobs within this workflow

    Example:
        Create and execute a workflow:

        ```python
        workflow = Workflow.from_conf('my-workflow')
        result = workflow.execute({
            'param1': 'value1',
            'param2': 'value2'
        })
        ```

    Note:
        Workflows can be executed immediately or scheduled for background
        execution using the cron-like scheduling system.
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
    on: Event = Field(
        default_factory=Event,
        description="An events for this workflow.",
    )
    jobs: dict[str, Job] = Field(
        default_factory=dict,
        description="A mapping of job ID and job model that already loaded.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="A list of tag that use for simple grouping workflow.",
    )
    created_at: datetime = Field(
        default_factory=get_dt_now,
        description=(
            "A created datetime of this workflow template when loading from "
            "file."
        ),
    )
    updated_dt: datetime = Field(
        default_factory=get_dt_now,
        description=(
            "A updated datetime of this workflow template when loading from "
            "file."
        ),
    )

    @classmethod
    def from_conf(
        cls,
        name: str,
        *,
        path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> Self:
        """Create Workflow instance from configuration file.

        Loads workflow configuration from YAML files and creates a validated
        Workflow instance. The configuration loader searches for workflow
        definitions in the specified path or default configuration directories.

        Args:
            name: Workflow name to load from configuration
            path: Optional custom configuration path to search
            extras: Additional parameters to override configuration values

        Returns:
            Self: Validated Workflow instance loaded from configuration

        Raises:
            ValueError: If workflow type doesn't match or configuration invalid
            FileNotFoundError: If workflow configuration file not found

        Example:
            ```python
            # Load from default config path
            workflow = Workflow.from_conf('data-pipeline')

            # Load with custom path and extras
            workflow = Workflow.from_conf(
                'data-pipeline',
                path=Path('./custom-configs'),
                extras={'environment': 'production'}
            )
            ```
        """
        load: YamlParser = YamlParser(name, path=path, extras=extras, obj=cls)
        data: DictData = copy.deepcopy(load.data)
        data["name"] = name

        if extras:
            data["extras"] = extras

        return cls.model_validate(obj=data)

    @field_validator(
        "params",
        mode="before",
        json_schema_input_type=Union[dict[str, Param], dict[str, str]],
    )
    def __prepare_params(cls, data: Any) -> Any:
        """Prepare the params key in the data model before validating."""
        if isinstance(data, dict):
            data = {
                k: ({"type": v} if isinstance(v, str) else v)
                for k, v in data.items()
            }
        return data

    @field_validator("desc", mode="after")
    def __dedent_desc__(cls, data: str) -> str:
        """Prepare description string that was created on a template.

        Args:
            data: A description string value that want to dedent.

        Returns:
            str: The de-dented description string.
        """
        return dedent(data.lstrip("\n"))

    @field_validator("created_at", "updated_dt", mode="after")
    def __convert_tz__(cls, dt: datetime) -> datetime:
        """Replace timezone of datetime type to no timezone."""
        return dt.replace(tzinfo=None)

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

    def detail(self) -> DictData:  # pragma: no cov
        """Return the detail of this workflow for generate markdown."""
        return self.model_dump(by_alias=True)

    def md(self, author: Optional[str] = None) -> str:  # pragma: no cov
        """Generate the markdown template."""

        def align_newline(value: str) -> str:
            return value.rstrip("\n").replace("\n", "\n                ")

        info: str = (
            f"| Author: {author or 'nobody'} "
            f"| created_at: `{self.created_at:%Y-%m-%d %H:%M:%S}` "
            f"| updated_at: `{self.updated_dt:%Y-%m-%d %H:%M:%S}` |\n"
            f"| --- | --- | --- |"
        )
        jobs: str = ""
        for job in self.jobs:
            job_model: Job = self.jobs[job]
            jobs += f"### {job}\n{job_model.desc or ''}\n"
            stags: str = ""
            for stage_model in job_model.stages:
                stags += (
                    f"#### {stage_model.name}\n\n"
                    f"Stage ID: {stage_model.id or ''}\n"
                    f"Stage Model: {stage_model.__class__.__name__}\n\n"
                )
            jobs += f"{stags}\n"
        return dedent(
            f"""
                # Workflow: {self.name}\n
                {align_newline(info)}\n
                {align_newline(self.desc)}\n
                ## Parameters\n
                | name | type | default | description |
                | --- | --- | --- | : --- : |

                ## Jobs\n
                {align_newline(jobs)}
                """.lstrip(
                "\n"
            )
        )

    def job(self, name: str) -> Job:
        """Return the workflow's Job model that getting by an input job's name
        or job's ID. This method will pass an extra parameter from this model
        to the returned Job model.

        Args:
            name: A job name or ID that want to get from a mapping of
                job models.

        Returns:
            Job: A job model that exists on this workflow by input name.

        Raises:
            ValueError: If a name or ID does not exist on the jobs field.
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

        Args:
            params: A parameter data that receive from workflow
                execute method.

        Returns:
            DictData: The parameter value that validate with its parameter fields and
                adding jobs key to this parameter.

        Raises:
            WorkflowError: If parameter value that want to validate does
                not include the necessary parameter that had required flag.
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

        Args:
            dt (datetime): A datetime object that want to validate.

        Returns:
            datetime: The validated release datetime.
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)

        release: datetime = replace_sec(dt.astimezone(UTC))

        # NOTE: Return itself if schedule event does not set.
        if not self.on.schedule:
            return release

        for on in self.on.schedule:
            if release == on.cronjob.schedule(release, tz=UTC).next:
                return release
        raise WorkflowError(
            "Release datetime does not support for this workflow"
        )

    def release(
        self,
        release: datetime,
        params: DictData,
        *,
        run_id: Optional[str] = None,
        runs_metadata: Optional[DictData] = None,
        release_type: ReleaseType = NORMAL,
        override_log_name: Optional[str] = None,
        timeout: int = 600,
        audit_excluded: Optional[list[str]] = None,
        audit: type[Audit] = None,
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

        Args:
            release (datetime): A release datetime.
            params: A workflow parameter that pass to execute method.
            release_type:
            run_id: (str) A workflow running ID.
            runs_metadata: (DictData)
            audit: An audit class that want to save the execution result.
            override_log_name: (str) An override logging name that use
                instead the workflow name.
            timeout: (int) A workflow execution time out in second unit.
            audit_excluded: (list[str]) A list of key that want to exclude
                from the audit data.

        Returns:
            Result: return result object that pass context data from the execute
                method.
        """
        name: str = override_log_name or self.name

        # NOTE: Generate the parent running ID with not None value.
        if run_id:
            parent_run_id: str = run_id
            run_id: str = gen_id(name, unique=True)
        else:
            run_id: str = gen_id(name, unique=True)
            parent_run_id: str = run_id

        context: DictData = {"status": WAIT}
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        release: datetime = self.validate_release(dt=release)
        trace.info(f"[RELEASE]: Start {name!r} : {release:%Y-%m-%d %H:%M:%S}")
        values: DictData = param2template(
            params,
            params={
                "release": {
                    "logical_date": release,
                    "execute_date": get_dt_now(),
                    "run_id": run_id,
                    "runs_metadata": runs_metadata or {},
                }
            },
            extras=self.extras,
        )
        rs: Result = self.execute(
            params=values,
            run_id=parent_run_id,
            timeout=timeout,
        )
        catch(context, status=rs.status, updated=rs.context)
        trace.info(f"[RELEASE]: End {name!r} : {release:%Y-%m-%d %H:%M:%S}")
        trace.debug(f"[RELEASE]: Writing audit: {name!r}.")
        (
            (audit or get_audit_model(extras=self.extras))(
                name=name,
                release=release,
                type=release_type,
                context=context,
                parent_run_id=parent_run_id,
                run_id=run_id,
                extras=self.extras,
                runs_metadata=(
                    (runs_metadata or {})
                    | rs.info
                    | {
                        "timeout": timeout,
                        "original_name": self.name,
                        "audit_excluded": audit_excluded,
                    }
                ),
            ).save(excluded=audit_excluded)
        )
        return Result(
            run_id=run_id,
            parent_run_id=parent_run_id,
            status=rs.status,
            context=catch(
                context,
                status=rs.status,
                updated={
                    "params": params,
                    "release": {
                        "type": release_type,
                        "logical_date": release,
                    },
                    **{"jobs": context.pop("jobs", {})},
                    **(context["errors"] if "errors" in context else {}),
                },
            ),
            extras=self.extras,
        )

    def execute_job(
        self,
        job: Job,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[ThreadEvent] = None,
    ) -> tuple[Status, DictData]:
        """Job execution with passing dynamic parameters from the main workflow
        execution to the target job object via job's ID.

            This execution is the minimum level of execution of this workflow
        model. It different with `self.execute` because this method run only
        one job and return with context of this job data.

            This method do not raise any error, and it will handle all exception
        from the job execution.

        Args:
            job: (Job) A job model that want to execute.
            run_id: A running stage ID.
            context: A context data.
            parent_run_id: A parent running ID. (Default is None)
            event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        Returns:
            tuple[Status, DictData]: The pair of status and result context data.
        """
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        if event and event.is_set():
            error_msg: str = (
                "Job execution was canceled because the event was set "
                "before start job execution."
            )
            return CANCEL, catch(
                context=context,
                status=CANCEL,
                updated={
                    "errors": WorkflowCancelError(error_msg).to_dict(),
                },
            )

        trace.info(f"[WORKFLOW]: Execute Job: {job.id!r}")
        result: Result = job.execute(
            params=context,
            run_id=parent_run_id,
            event=event,
        )
        job.set_outputs(result.context, to=context)

        if result.status == FAILED:
            error_msg: str = f"Job execution, {job.id!r}, was failed."
            return FAILED, catch(
                context=context,
                status=FAILED,
                updated={
                    "errors": WorkflowError(error_msg).to_dict(),
                },
            )

        elif result.status == CANCEL:
            error_msg: str = (
                f"Job execution, {job.id!r}, was canceled from the event after "
                f"end job execution."
            )
            return CANCEL, catch(
                context=context,
                status=CANCEL,
                updated={
                    "errors": WorkflowCancelError(error_msg).to_dict(),
                },
            )

        return result.status, catch(context, status=result.status)

    def execute(
        self,
        params: DictData,
        *,
        run_id: Optional[str] = None,
        event: Optional[ThreadEvent] = None,
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
        parent_run_id: Optional[str] = run_id
        run_id: str = gen_id(self.name, extras=self.extras)
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        context: DictData = self.parameterize(params)
        event: ThreadEvent = event or ThreadEvent()
        max_job_parallel: int = dynamic(
            "max_job_parallel", f=max_job_parallel, extras=self.extras
        )
        trace.info(
            f"[WORKFLOW]: Execute: {self.name!r} ("
            f"{'parallel' if max_job_parallel > 1 else 'sequential'} jobs)"
        )
        if not self.jobs:
            trace.warning(f"[WORKFLOW]: {self.name!r} does not set jobs")
            return Result(
                run_id=run_id,
                parent_run_id=parent_run_id,
                status=SUCCESS,
                context=catch(context, status=SUCCESS),
                info={"execution_time": time.monotonic() - ts},
                extras=self.extras,
            )

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
        catch(context, status=WAIT)
        if event and event.is_set():
            return Result(
                run_id=run_id,
                parent_run_id=parent_run_id,
                status=CANCEL,
                context=catch(
                    context,
                    status=CANCEL,
                    updated={
                        "errors": WorkflowCancelError(
                            "Execution was canceled from the event was set "
                            "before workflow execution."
                        ).to_dict(),
                    },
                ),
                info={"execution_time": time.monotonic() - ts},
                extras=self.extras,
            )

        with ThreadPoolExecutor(max_job_parallel, "wf") as executor:
            futures: list[Future] = []

            # NOTE: Start with smaller sleep time
            backoff_sleep: float = 0.01

            # NOTE: Track consecutive wait states
            consecutive_waits: int = 0

            while not job_queue.empty() and (
                not_timeout_flag := ((time.monotonic() - ts) < timeout)
            ):
                job_id: str = job_queue.get()
                job: Job = self.job(name=job_id)
                if (check := job.check_needs(context["jobs"])) == WAIT:
                    job_queue.task_done()
                    job_queue.put(job_id)
                    consecutive_waits += 1
                    # Exponential backoff up to 0.15s max
                    backoff_sleep = min(backoff_sleep * 1.5, 0.15)
                    time.sleep(backoff_sleep)
                    continue

                # Reset backoff when we can proceed
                consecutive_waits = 0
                backoff_sleep = 0.01

                if check == FAILED:  # pragma: no cov
                    return Result(
                        run_id=run_id,
                        parent_run_id=parent_run_id,
                        status=FAILED,
                        context=catch(
                            context,
                            status=FAILED,
                            updated={
                                "status": FAILED,
                                "errors": WorkflowError(
                                    f"Validate job trigger rule was failed "
                                    f"with {job.trigger_rule.value!r}."
                                ).to_dict(),
                            },
                        ),
                        info={"execution_time": time.monotonic() - ts},
                        extras=self.extras,
                    )
                elif check == SKIP:  # pragma: no cov
                    trace.info(
                        f"[JOB]: Skip job: {job_id!r} from trigger rule."
                    )
                    job.set_outputs(output={"status": SKIP}, to=context)
                    job_queue.task_done()
                    skip_count += 1
                    continue

                # IMPORTANT: Start execution with parallel mode.
                if max_job_parallel > 1:
                    futures.append(
                        executor.submit(
                            self.execute_job,
                            job=job,
                            run_id=run_id,
                            context=context,
                            parent_run_id=parent_run_id,
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
                            run_id=run_id,
                            context=context,
                            parent_run_id=parent_run_id,
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
                # NOTE: The release future can not track a cancelled status
                #   because it only has one future.
                elif future.cancelled():  # pragma: no cov
                    sequence_statuses.append(CANCEL)
                    job_queue.put(job_id)
                elif future.running() or "state=pending" in str(future):
                    futures.insert(0, future)
                    job_queue.put(job_id)
                else:  # pragma: no cov
                    job_queue.put(job_id)
                    futures.insert(0, future)
                    trace.warning(
                        f"[WORKFLOW]: ... Execution non-threading not "
                        f"handle: {future}."
                    )

                job_queue.task_done()

            if not_timeout_flag:
                job_queue.join()
                for total, future in enumerate(as_completed(futures), start=0):
                    try:
                        statuses[total], _ = future.result()
                    except (WorkflowError, Exception) as e:
                        statuses[total] = get_status_from_error(e)

                # NOTE: Update skipped status from the job trigger.
                for i in range(skip_count):
                    statuses[total + 1 + i] = SKIP

                # NOTE: Update status from none-parallel job execution.
                for i, s in enumerate(sequence_statuses, start=0):
                    statuses[total + 1 + skip_count + i] = s

                st: Status = validate_statuses(statuses)
                return Result(
                    run_id=run_id,
                    parent_run_id=parent_run_id,
                    status=st,
                    context=catch(context, status=st),
                    info={"execution_time": time.monotonic() - ts},
                    extras=self.extras,
                )

            event.set()
            for future in futures:
                future.cancel()

            trace.error(
                f"[WORKFLOW]: {self.name!r} was timeout because it use exec "
                f"time more than {timeout} seconds."
            )

            time.sleep(0.0025)

        return Result(
            run_id=run_id,
            parent_run_id=parent_run_id,
            status=FAILED,
            context=catch(
                context,
                status=FAILED,
                updated={
                    "errors": WorkflowTimeoutError(
                        f"{self.name!r} was timeout because it use exec time "
                        f"more than {timeout} seconds."
                    ).to_dict(),
                },
            ),
            info={"execution_time": time.monotonic() - ts},
            extras=self.extras,
        )

    def rerun(
        self,
        context: DictData,
        *,
        run_id: Optional[str] = None,
        event: Optional[ThreadEvent] = None,
        timeout: float = 3600,
        max_job_parallel: int = 2,
    ) -> Result:  # pragma: no cov
        """Re-Execute workflow with passing the error context data.

        :param context: A context result that get the failed status.
        :param run_id: (Optional[str]) A workflow running ID.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.
        :param timeout: (float) A workflow execution time out in second unit
            that use for limit time of execution and waiting job dependency.
            This value does not force stop the task that still running more than
            this limit time. (Default: 60 * 60 seconds)
        :param max_job_parallel: (int) The maximum workers that use for job
            execution in `ThreadPoolExecutor` object. (Default: 2 workers)

        Returns
            Result: Return Result object that create from execution context with
                return mode.
        """
        ts: float = time.monotonic()
        parent_run_id: str = run_id
        run_id: str = gen_id(self.name, extras=self.extras)
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        if context["status"] == SUCCESS:
            trace.info(
                "[WORKFLOW]: Does not rerun because it already executed with "
                "success status."
            )
            return Result.from_trace(trace).catch(
                status=SUCCESS,
                context=catch(context=context, status=SUCCESS),
            )

        err: dict[str, str] = context.get("errors", {})
        trace.info(f"[WORKFLOW]: Previous error: {err}")

        event: ThreadEvent = event or ThreadEvent()
        max_job_parallel: int = dynamic(
            "max_job_parallel", f=max_job_parallel, extras=self.extras
        )
        trace.info(
            f"[WORKFLOW]: Execute: {self.name!r} ("
            f"{'parallel' if max_job_parallel > 1 else 'sequential'} jobs)"
        )
        if not self.jobs:
            trace.warning(f"[WORKFLOW]: {self.name!r} does not set jobs")
            return Result.from_trace(trace).catch(
                status=SUCCESS,
                context=catch(context=context, status=SUCCESS),
            )

        # NOTE: Prepare the new context variable for rerun process.
        jobs: DictData = context.get("jobs")
        context: DictData = {
            "params": context["params"].copy(),
            "jobs": {j: jobs[j] for j in jobs if jobs[j]["status"] == SUCCESS},
        }

        total_job: int = 0
        job_queue: Queue = Queue()
        for job_id in self.jobs:

            if job_id in context["jobs"]:
                continue

            job_queue.put(job_id)
            total_job += 1

        if total_job == 0:
            trace.warning(
                "[WORKFLOW]: It does not have job to rerun. it will change "
                "status to skip."
            )
            return Result.from_trace(trace).catch(
                status=SKIP,
                context=catch(context=context, status=SKIP),
            )

        not_timeout_flag: bool = True
        statuses: list[Status] = [WAIT] * total_job
        skip_count: int = 0
        sequence_statuses: list[Status] = []
        timeout: float = dynamic(
            "max_job_exec_timeout", f=timeout, extras=self.extras
        )

        catch(context, status=WAIT)
        if event and event.is_set():
            return Result.from_trace(trace).catch(
                status=CANCEL,
                context=catch(
                    context,
                    status=CANCEL,
                    updated={
                        "errors": WorkflowCancelError(
                            "Execution was canceled from the event was set "
                            "before workflow execution."
                        ).to_dict(),
                    },
                ),
            )

        with ThreadPoolExecutor(max_job_parallel, "wf") as executor:
            futures: list[Future] = []
            backoff_sleep = 0.01
            consecutive_waits = 0

            while not job_queue.empty() and (
                not_timeout_flag := ((time.monotonic() - ts) < timeout)
            ):
                job_id: str = job_queue.get()
                job: Job = self.job(name=job_id)
                if (check := job.check_needs(context["jobs"])) == WAIT:
                    job_queue.task_done()
                    job_queue.put(job_id)
                    consecutive_waits += 1

                    # NOTE: Exponential backoff up to 0.15s max.
                    backoff_sleep = min(backoff_sleep * 1.5, 0.15)
                    time.sleep(backoff_sleep)
                    continue

                # NOTE: Reset backoff when we can proceed
                consecutive_waits = 0
                backoff_sleep = 0.01

                if check == FAILED:  # pragma: no cov
                    return Result.from_trace(trace).catch(
                        status=FAILED,
                        context=catch(
                            context,
                            status=FAILED,
                            updated={
                                "status": FAILED,
                                "errors": WorkflowError(
                                    f"Validate job trigger rule was failed "
                                    f"with {job.trigger_rule.value!r}."
                                ).to_dict(),
                            },
                        ),
                    )
                elif check == SKIP:  # pragma: no cov
                    trace.info(
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
                            run_id=run_id,
                            context=context,
                            parent_run_id=parent_run_id,
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
                            run_id=run_id,
                            context=context,
                            parent_run_id=parent_run_id,
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
                    trace.warning(
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

                st: Status = validate_statuses(statuses)
                return Result.from_trace(trace).catch(
                    status=st,
                    context=catch(context, status=st),
                )

            event.set()
            for future in futures:
                future.cancel()

            trace.error(
                f"[WORKFLOW]: {self.name!r} was timeout because it use exec "
                f"time more than {timeout} seconds."
            )

            time.sleep(0.0025)

        return Result.from_trace(trace).catch(
            status=FAILED,
            context=catch(
                context,
                status=FAILED,
                updated={
                    "errors": WorkflowTimeoutError(
                        f"{self.name!r} was timeout because it use exec time "
                        f"more than {timeout} seconds."
                    ).to_dict(),
                },
            ),
        )
