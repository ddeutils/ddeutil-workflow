# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Job Execution Module.

This module contains the Job model and related components for managing stage
execution, execution strategies, and job orchestration within workflows.

The Job model serves as a container for Stage models and handles the execution
lifecycle, dependency management, and output coordination. It supports various
execution environments through the runs-on configuration.

Key Features:
    - Stage execution orchestration
    - Matrix strategy for parameterized execution
    - Multi-environment support (local, self-hosted, Docker, Azure Batch)
    - Dependency management via job needs
    - Conditional execution support
    - Parallel execution capabilities

Classes:
    Job: Main job execution container
    Strategy: Matrix strategy for parameterized execution
    Rule: Trigger rules for job execution
    RunsOn: Execution environment enumeration
    BaseRunsOn: Base class for execution environments

Note:
    Jobs raise JobError on execution failures, providing consistent error
    handling across the workflow system.
"""
from __future__ import annotations

import copy
import time
from collections.abc import Iterator
from concurrent.futures import (
    FIRST_EXCEPTION,
    CancelledError,
    Future,
    ThreadPoolExecutor,
    as_completed,
    wait,
)
from enum import Enum
from functools import lru_cache
from textwrap import dedent
from threading import Event
from typing import Annotated, Any, Optional, Union

from ddeutil.core import freeze_args
from pydantic import BaseModel, Discriminator, Field, SecretStr, Tag
from pydantic.functional_serializers import field_serializer
from pydantic.functional_validators import field_validator, model_validator
from typing_extensions import Self

from .__types import DictData, DictStr, Matrix, StrOrNone
from .errors import JobCancelError, JobError, to_dict
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
from .stages import Stage
from .traces import TraceManager, get_trace
from .utils import cross_product, filter_func, gen_id

MatrixFilter = list[dict[str, Union[str, int]]]


@freeze_args
@lru_cache
def make(
    matrix: Matrix,
    include: MatrixFilter,
    exclude: MatrixFilter,
) -> list[DictStr]:
    """Make a list of product of matrix values that already filter with
    exclude matrix and add specific matrix with include.

        This function use the `lru_cache` decorator function increase
    performance for duplicate matrix value scenario.

    :param matrix: (Matrix) A matrix values that want to cross product to
        possible parallelism values.
    :param include: A list of additional matrix that want to adds-in.
    :param exclude: A list of exclude matrix that want to filter-out.

    :rtype: list[DictStr]
    """
    # NOTE: If it does not set matrix, it will return list of an empty dict.
    if len(matrix) == 0:
        return [{}]

    # NOTE: Remove matrix that exists on the excluded.
    final: list[DictStr] = []
    for r in cross_product(matrix=matrix):
        if any(
            all(r[k] == v for k, v in exclude.items()) for exclude in exclude
        ):
            continue
        final.append(r)

    # NOTE: If it is empty matrix and include, it will return list of an
    #   empty dict.
    if len(final) == 0 and not include:
        return [{}]

    # NOTE: Add include to generated matrix with exclude list.
    add: list[DictStr] = []
    for inc in include:
        # VALIDATE:
        #   Validate any key in include list should be a subset of someone
        #   in matrix.
        if all(not (set(inc.keys()) <= set(m.keys())) for m in final):
            raise ValueError(
                "Include should have the keys that equal to all final matrix."
            )

        # VALIDATE:
        #   Validate value of include should not duplicate with generated
        #   matrix. So, it will skip if this value already exists.
        if any(
            all(inc.get(k) == v for k, v in m.items()) for m in [*final, *add]
        ):
            continue

        add.append(inc)

    final.extend(add)
    return final


class Strategy(BaseModel):
    """Matrix strategy model for parameterized job execution.

    The Strategy model generates combinations of matrix values to enable
    parallel execution of jobs with different parameter sets. It supports
    cross-product generation, inclusion of specific combinations, and
    exclusion of unwanted combinations.

    This model can be used independently or as part of job configuration
    to create multiple execution contexts from a single job definition.

    Matrix Combination Logic:
        [1, 2, 3] × [a, b] → [1a], [1b], [2a], [2b], [3a], [3b]

    Attributes:
        fail_fast (bool): Cancel remaining executions on first failure
        max_parallel (int): Maximum concurrent executions (1-9)
        matrix (dict): Base matrix values for cross-product generation
        include (list): Additional specific combinations to include
        exclude (list): Specific combinations to exclude from results

    Example:
        ```python
        strategy = Strategy(
            max_parallel=2,
            fail_fast=True,
            matrix={
                'python_version': ['3.9', '3.10', '3.11'],
                'os': ['ubuntu', 'windows']
            },
            include=[{'python_version': '3.12', 'os': 'ubuntu'}],
            exclude=[{'python_version': '3.9', 'os': 'windows'}]
        )

        combinations = strategy.make()  # Returns list of parameter dicts
        ```
    """

    fail_fast: bool = Field(
        default=False,
        description=(
            "A fail-fast flag that use to cancel strategy execution when it "
            "has some execution was failed."
        ),
        alias="fail-fast",
    )
    max_parallel: int = Field(
        default=1,
        gt=0,
        lt=10,
        description=(
            "The maximum number of executor thread pool that want to run "
            "parallel. This value should gather than 0 and less than 10."
        ),
        alias="max-parallel",
    )
    matrix: Matrix = Field(
        default_factory=dict,
        description=(
            "A matrix values that want to cross product to possible strategies."
        ),
    )
    include: MatrixFilter = Field(
        default_factory=list,
        description="A list of additional matrix that want to adds-in.",
    )
    exclude: MatrixFilter = Field(
        default_factory=list,
        description="A list of exclude matrix that want to filter-out.",
    )

    def is_set(self) -> bool:
        """Return True if this strategy was set from yaml template.

        Returns:
            bool: True if matrix has been configured, False otherwise.
        """
        return len(self.matrix) > 0

    def make(self) -> list[DictStr]:
        """Return List of product of matrix values that already filter with
        exclude and add include.

        Returns:
            list[DictStr]: List of parameter combinations from matrix strategy.
        """
        return make(self.matrix, self.include, self.exclude)


class Rule(str, Enum):
    """Rule enum object for assign trigger option."""

    ALL_SUCCESS = "all_success"
    ALL_FAILED = "all_failed"
    ALL_DONE = "all_done"
    ONE_FAILED = "one_failed"
    ONE_SUCCESS = "one_success"
    NONE_FAILED = "none_failed"
    NONE_SKIPPED = "none_skipped"


class RunsOn(str, Enum):
    """Runs-On enum object."""

    LOCAL = "local"
    SELF_HOSTED = "self_hosted"
    AZ_BATCH = "azure_batch"
    AWS_BATCH = "aws_batch"
    GCP_BATCH = "gcp_batch"
    CLOUD_BATCH = "cloud_batch"
    DOCKER = "docker"
    CONTAINER = "container"


# Import constants for backward compatibility
LOCAL = RunsOn.LOCAL
SELF_HOSTED = RunsOn.SELF_HOSTED
AZ_BATCH = RunsOn.AZ_BATCH
AWS_BATCH = RunsOn.AWS_BATCH
GCP_BATCH = RunsOn.GCP_BATCH
CLOUD_BATCH = RunsOn.CLOUD_BATCH
DOCKER = RunsOn.DOCKER
CONTAINER = RunsOn.CONTAINER


class BaseRunsOn(BaseModel):  # pragma: no cov
    """Base Runs-On Model for generate runs-on types via inherit this model
    object and override execute method.
    """

    type: RunsOn = LOCAL
    args: DictData = Field(
        default_factory=dict,
        description=(
            "An argument that pass to the runs-on execution function. This "
            "args will override by this child-model with specific args model."
        ),
        alias="with",
    )


class OnLocal(BaseRunsOn):  # pragma: no cov
    """Runs-on local."""


class SelfHostedArgs(BaseModel):
    """Self-Hosted arguments."""

    host: str = Field(description="A host URL of the target self-hosted.")
    token: SecretStr = Field(description="An API or Access token.")


class OnSelfHosted(BaseRunsOn):  # pragma: no cov
    """Runs-on self-hosted."""

    type: RunsOn = SELF_HOSTED
    args: SelfHostedArgs = Field(alias="with")


class AzBatchArgs(BaseModel):
    """Azure Batch arguments."""

    batch_account_name: str
    batch_account_key: SecretStr
    batch_account_url: str
    storage_account_name: str
    storage_account_key: SecretStr


class OnAzBatch(BaseRunsOn):  # pragma: no cov

    type: RunsOn = AZ_BATCH
    args: AzBatchArgs = Field(alias="with")


class DockerArgs(BaseModel):
    image: str = Field(
        default="ubuntu-latest",
        description=(
            "An image that want to run like `ubuntu-22.04`, `windows-latest`, "
            ", `ubuntu-24.04-arm`, or `macos-14`"
        ),
    )
    env: DictData = Field(default_factory=dict)
    volume: DictData = Field(default_factory=dict)


class OnDocker(BaseRunsOn):  # pragma: no cov
    """Runs-on Docker container."""

    type: RunsOn = DOCKER
    args: DockerArgs = Field(default_factory=DockerArgs, alias="with")


class ContainerArgs(BaseModel):
    """Container arguments."""

    image: str = Field(description="Docker image to use")
    container_name: Optional[str] = Field(
        default=None, description="Container name"
    )
    volumes: Optional[list[dict[str, str]]] = Field(
        default=None, description="Volume mounts"
    )
    environment: Optional[dict[str, str]] = Field(
        default=None, description="Environment variables"
    )
    network: Optional[dict[str, Any]] = Field(
        default=None, description="Network configuration"
    )
    resources: Optional[dict[str, Any]] = Field(
        default=None, description="Resource limits"
    )
    working_dir: Optional[str] = Field(
        default="/app", description="Working directory"
    )
    user: Optional[str] = Field(default=None, description="User to run as")
    command: Optional[str] = Field(
        default=None, description="Override default command"
    )
    timeout: int = Field(
        default=3600, description="Execution timeout in seconds"
    )
    remove: bool = Field(
        default=True, description="Remove container after execution"
    )
    docker_host: Optional[str] = Field(
        default=None, description="Docker host URL"
    )


class OnContainer(BaseRunsOn):  # pragma: no cov
    """Runs-on Container."""

    type: RunsOn = CONTAINER
    args: ContainerArgs = Field(default_factory=ContainerArgs, alias="with")


class AWSBatchArgs(BaseModel):
    """AWS Batch arguments."""

    job_queue_arn: str = Field(description="AWS Batch job queue ARN")
    s3_bucket: str = Field(description="S3 bucket for file storage")
    region_name: str = Field(default="us-east-1", description="AWS region")
    aws_access_key_id: Optional[str] = Field(
        default=None, description="AWS access key ID"
    )
    aws_secret_access_key: Optional[str] = Field(
        default=None, description="AWS secret access key"
    )
    aws_session_token: Optional[str] = Field(
        default=None, description="AWS session token"
    )


class OnAWSBatch(BaseRunsOn):  # pragma: no cov
    """Runs-on AWS Batch."""

    type: RunsOn = AWS_BATCH
    args: AWSBatchArgs = Field(alias="with")


class GCPBatchArgs(BaseModel):
    """Google Cloud Batch arguments."""

    project_id: str = Field(description="Google Cloud project ID")
    region: str = Field(description="Google Cloud region")
    gcs_bucket: str = Field(description="Google Cloud Storage bucket")
    credentials_path: Optional[str] = Field(
        default=None, description="Path to service account credentials"
    )
    machine_type: str = Field(
        default="e2-standard-4", description="Machine type"
    )
    max_parallel_tasks: int = Field(
        default=1, description="Maximum parallel tasks"
    )


class OnGCPBatch(BaseRunsOn):  # pragma: no cov
    """Runs-on Google Cloud Batch."""

    type: RunsOn = GCP_BATCH
    args: GCPBatchArgs = Field(alias="with")


def get_discriminator_runs_on(model: dict[str, Any]) -> RunsOn:
    """Get discriminator of the RunsOn models."""
    t: str = model.get("type")
    return RunsOn(t) if t else LOCAL


RunsOnModel = Annotated[
    Union[
        Annotated[OnSelfHosted, Tag(SELF_HOSTED)],
        Annotated[OnDocker, Tag(DOCKER)],
        Annotated[OnLocal, Tag(LOCAL)],
        Annotated[OnContainer, Tag(CONTAINER)],
        Annotated[OnAWSBatch, Tag(AWS_BATCH)],
        Annotated[OnGCPBatch, Tag(GCP_BATCH)],
    ],
    Discriminator(get_discriminator_runs_on),
]


class Job(BaseModel):
    """Job execution container for stage orchestration.

    The Job model represents a logical unit of work containing multiple stages
    that execute sequentially. Jobs support matrix strategies for parameterized
    execution, dependency management, conditional execution, and multienvironment
    deployment.

    Jobs are the primary execution units within workflows, providing:
    - Stage lifecycle management
    - Execution environment abstraction
    - Matrix strategy support for parallel execution
    - Dependency resolution via job needs
    - Output coordination between stages

    Attributes:
        id (str, optional): Unique job identifier within workflow
        desc (str, optional): Job description in Markdown format
        runs_on (RunsOnModel): Execution environment configuration
        condition (str, optional): Conditional execution expression
        stages (list[Stage]): Ordered list of stages to execute
        trigger_rule (Rule): Rule for handling job dependencies
        needs (list[str]): List of prerequisite job IDs
        strategy (Strategy): Matrix strategy for parameterized execution
        extras (dict): Additional configuration parameters

    Example:
        ```python
        job = Job(
            id="data-processing",
            desc="Process daily data files",
            runs_on=OnLocal(),
            stages=[
                EmptyStage(name="Start", echo="Processing started"),
                PyStage(name="Process", run="process_data()"),
                EmptyStage(name="Complete", echo="Processing finished")
            ],
            strategy=Strategy(
                matrix={'env': ['dev', 'prod']},
                max_parallel=2
            )
        )
        ```
    """

    id: StrOrNone = Field(
        default=None,
        description=(
            "A job ID that was set from Workflow model after initialize step. "
            "If this model create standalone, it will be None."
        ),
    )
    desc: StrOrNone = Field(
        default=None,
        description="A job description that can be markdown syntax.",
    )
    runs_on: RunsOnModel = Field(
        default_factory=OnLocal,
        description="A target node for this job to use for execution.",
        alias="runs-on",
    )
    condition: StrOrNone = Field(
        default=None,
        description="A job condition statement to allow job executable.",
        alias="if",
    )
    stages: list[Stage] = Field(
        default_factory=list,
        description="A list of Stage model of this job.",
    )
    trigger_rule: Rule = Field(
        default=Rule.ALL_SUCCESS,
        validate_default=True,
        description=(
            "A trigger rule of tracking needed jobs if feature will use when "
            "the `raise_error` did not set from job and stage executions."
        ),
        alias="trigger-rule",
    )
    needs: list[str] = Field(
        default_factory=list,
        description="A list of the job that want to run before this job model.",
    )
    strategy: Strategy = Field(
        default_factory=Strategy,
        description="A strategy matrix that want to generate.",
    )
    extras: DictData = Field(
        default_factory=dict,
        description="An extra override config values.",
    )

    @field_validator("desc", mode="after")
    def ___prepare_desc__(cls, value: str) -> str:
        """Prepare description string that was created on a template.

        :rtype: str
        """
        return dedent(value.lstrip("\n"))

    @field_validator("stages", mode="after")
    def __validate_stage_id__(cls, value: list[Stage]) -> list[Stage]:
        """Validate stage ID of each stage in the `stages` field should not be
        duplicate.

        :rtype: list[Stage]
        """
        # VALIDATE: Validate stage id should not duplicate.
        rs: list[str] = []
        rs_raise: list[str] = []
        for stage in value:
            name: str = stage.iden
            if name in rs:
                rs_raise.append(name)
                continue
            rs.append(name)

        if rs_raise:
            raise ValueError(
                f"Stage name, {', '.join(repr(s) for s in rs_raise)}, should "
                f"not be duplicate."
            )
        return value

    @model_validator(mode="after")
    def __validate_job_id__(self) -> Self:
        """Validate job id should not dynamic with params template.

        :rtype: Self
        """
        if has_template(self.id):
            raise ValueError(
                f"Job ID, {self.id!r}, should not has any template."
            )

        return self

    @field_serializer("runs_on")
    def __serialize_runs_on(self, value: RunsOnModel) -> DictData:
        """Serialize the runs_on field."""
        return value.model_dump(by_alias=True)

    def stage(self, stage_id: str) -> Stage:
        """Return stage instance that exists in this job via passing an input
        stage ID.

        :raise ValueError: If an input stage ID does not found on this job.

        :param stage_id: A stage ID that want to extract from this job.
        :rtype: Stage
        """
        for stage in self.stages:
            if stage_id == (stage.id or ""):
                if self.extras:
                    stage.extras = self.extras
                return stage
        raise ValueError(f"Stage {stage_id!r} does not exists in this job.")

    def check_needs(self, jobs: dict[str, DictData]) -> Status:
        """Return trigger status from checking job's need trigger rule logic was
        valid. The return status should be `SUCCESS`, `FAILED`, `WAIT`, or
        `SKIP` status.

        :param jobs: (dict[str, DictData]) A mapping of job ID and its context
            data that return from execution process.

        :raise NotImplementedError: If the job trigger rule out of scope.

        :rtype: Status
        """
        if not self.needs:
            return SUCCESS

        def make_return(result: bool) -> Status:
            return SUCCESS if result else FAILED

        # NOTE: Filter all job result context only needed in this job.
        need_exist: dict[str, Any] = {
            need: jobs[need] or {"status": SUCCESS}
            for need in self.needs
            if need in jobs
        }

        # NOTE: Return WAIT status if result context not complete, or it has any
        #   waiting status.
        if len(need_exist) < len(self.needs) or any(
            need_exist[job].get("status", SUCCESS) == WAIT for job in need_exist
        ):
            return WAIT

        # NOTE: Return SKIP status if all status are SKIP.
        elif all(
            need_exist[job].get("status", SUCCESS) == SKIP for job in need_exist
        ):
            return SKIP

        # NOTE: Return CANCEL status if any status is CANCEL.
        elif any(
            need_exist[job].get("status", SUCCESS) == CANCEL
            for job in need_exist
        ):
            return CANCEL

        # NOTE: Return SUCCESS if all status not be WAIT or all SKIP.
        elif self.trigger_rule == Rule.ALL_DONE:
            return SUCCESS

        elif self.trigger_rule == Rule.ALL_SUCCESS:
            rs = all(
                (
                    "errors" not in need_exist[job]
                    and need_exist[job].get("status", SUCCESS) == SUCCESS
                )
                for job in need_exist
            )
        elif self.trigger_rule == Rule.ALL_FAILED:
            rs = all(
                (
                    "errors" in need_exist[job]
                    or need_exist[job].get("status", SUCCESS) == FAILED
                )
                for job in need_exist
            )

        elif self.trigger_rule == Rule.ONE_SUCCESS:
            rs = (
                sum(
                    (
                        "errors" not in need_exist[job]
                        and need_exist[job].get("status", SUCCESS) == SUCCESS
                    )
                    for job in need_exist
                )
                == 1
            )

        elif self.trigger_rule == Rule.ONE_FAILED:
            rs = (
                sum(
                    (
                        "errors" in need_exist[job]
                        or need_exist[job].get("status", SUCCESS) == FAILED
                    )
                    for job in need_exist
                )
                == 1
            )

        elif self.trigger_rule == Rule.NONE_SKIPPED:
            rs = all(
                need_exist[job].get("status", SUCCESS) != SKIP
                for job in need_exist
            )

        elif self.trigger_rule == Rule.NONE_FAILED:
            rs = all(
                (
                    "errors" not in need_exist[job]
                    and need_exist[job].get("status", SUCCESS) != FAILED
                )
                for job in need_exist
            )

        else:  # pragma: no cov
            raise NotImplementedError(
                f"Trigger rule {self.trigger_rule} does not implement on this "
                f"`check_needs` method yet."
            )
        return make_return(rs)

    def is_skipped(self, params: DictData) -> bool:
        """Return true if condition of this job do not correct. This process
        use build-in eval function to execute the if-condition.

        :param params: (DictData) A parameter value that want to pass to condition
            template.

        :raise JobError: When it has any error raise from the eval
            condition statement.
        :raise JobError: When return type of the eval condition statement
            does not return with boolean type.

        :rtype: bool
        """
        if self.condition is None:
            return False

        try:
            # WARNING: The eval build-in function is very dangerous. So, it
            #   should use the `re` module to validate eval-string before
            #   running.
            rs: bool = eval(
                param2template(self.condition, params, extras=self.extras),
                globals() | params,
                {},
            )
            if not isinstance(rs, bool):
                raise TypeError("Return type of condition does not be boolean")
            return not rs
        except Exception as e:
            raise JobError(f"{e.__class__.__name__}: {e}") from e

    def set_outputs(
        self,
        output: DictData,
        to: DictData,
        *,
        job_id: StrOrNone = None,
        **kwargs,
    ) -> DictData:
        """Set an outputs from execution result context to the received context
        with a `to` input parameter. The result context from job strategy
        execution will be set with `strategies` key in this job ID key.

            For example of setting output method, If you receive execute output
        and want to set on the `to` like;

            ... (i)   output: {
                        'strategy-01': 'foo',
                        'strategy-02': 'bar',
                        'skipped': True,
                    }
            ... (ii)  to: {'jobs': {}}

        The result of the `to` argument will be;

            ... (iii) to: {
                        'jobs': {
                            '<job-id>': {
                                'strategies': {
                                    'strategy-01': 'foo',
                                    'strategy-02': 'bar',
                                },
                                'skipped': True,
                            }
                        }
                    }

            The keys that will set to the received context is `strategies`,
        `errors`, and `skipped` keys. The `errors` and `skipped` keys will
        extract from the result context if it exists. If it does not found, it
        will not set on the received context.

        :raise JobError: If the job's ID does not set and the setting
            default job ID flag does not set.

        Args:
            output: (DictData) A result data context that want to extract
                and transfer to the `strategies` key in receive context.
            to: (DictData) A received context data.
            job_id: (StrOrNone) A job ID if the `id` field does not set.
            kwargs: Any values that want to add to the target context.

        Returns:
            DictData: Return updated the target context with a result context.
        """
        if "jobs" not in to:
            to["jobs"] = {}

        if self.id is None and job_id is None:
            raise JobError(
                "This job do not set the ID before setting execution output."
            )

        _id: str = self.id or job_id
        output: DictData = copy.deepcopy(output)
        errors: DictData = (
            {"errors": output.pop("errors")} if "errors" in output else {}
        )
        status: dict[str, Status] = (
            {"status": output.pop("status")} if "status" in output else {}
        )
        kwargs: DictData = kwargs or {}
        if self.strategy.is_set():
            to["jobs"][_id] = {"strategies": output} | errors | status | kwargs
        elif len(k := output.keys()) > 1:  # pragma: no cov
            raise JobError(
                "Strategy output from execution return more than one ID while "
                "this job does not set strategy."
            )
        else:
            _output: DictData = {} if len(k) == 0 else output[list(k)[0]]
            _output.pop("matrix", {})
            to["jobs"][_id] = _output | errors | status | kwargs
        return to

    def get_outputs(
        self,
        output: DictData,
        *,
        job_id: StrOrNone = None,
    ) -> DictData:
        """Get the outputs from jobs data. It will get this job ID or passing
        custom ID from the job outputs mapping.

        :param output: (DictData) A job outputs data that want to extract
        :param job_id: (StrOrNone) A job ID if the `id` field does not set.

        :rtype: DictData
        """
        _id: str = self.id or job_id
        if self.strategy.is_set():
            return output.get("jobs", {}).get(_id, {}).get("strategies", {})
        else:
            return output.get("jobs", {}).get(_id, {})

    def execute(
        self,
        params: DictData,
        *,
        run_id: StrOrNone = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Job execution with passing dynamic parameters from the workflow
        execution. It will generate matrix values at the first step and run
        multithread on this metrics to the `stages` field of this job.

            This method be execution routing for call dynamic execution function
        with specific target `runs-on` value.

        Args
            params: (DictData) A parameter context that also pass from the
                workflow execute method.
            run_id: (str) An execution running ID.
            event: (Event) An Event manager instance that use to cancel this
                execution if it forces stopped by parent execution.

        Returns
            Result: Return Result object that create from execution context.
        """
        ts: float = time.monotonic()
        parent_run_id: str = run_id
        run_id: str = gen_id((self.id or "EMPTY"), unique=True)
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        trace.info(
            f"[JOB]: Routing for "
            f"{''.join(self.runs_on.type.value.split('_')).title()}: "
            f"{self.id!r}"
        )

        if self.runs_on.type == LOCAL:
            return local_execute(
                self,
                params,
                run_id=parent_run_id,
                event=event,
            ).make_info({"execution_time": time.monotonic() - ts})
        elif self.runs_on.type == SELF_HOSTED:  # pragma: no cov
            pass
        elif self.runs_on.type == AZ_BATCH:  # pragma: no cov
            from .plugins.providers.az import azure_batch_execute

            return azure_batch_execute(
                self,
                params,
                run_id=parent_run_id,
                event=event,
            ).make_info({"execution_time": time.monotonic() - ts})
        elif self.runs_on.type == DOCKER:  # pragma: no cov
            return docker_execution(
                self,
                params,
                run_id=parent_run_id,
                event=event,
            ).make_info({"execution_time": time.monotonic() - ts})
        elif self.runs_on.type == CONTAINER:  # pragma: no cov
            from .plugins.providers.container import container_execute

            return container_execute(
                self,
                params,
                run_id=parent_run_id,
                event=event,
            ).make_info({"execution_time": time.monotonic() - ts})
        elif self.runs_on.type == AWS_BATCH:  # pragma: no cov
            from .plugins.providers.aws import aws_batch_execute

            return aws_batch_execute(
                self,
                params,
                run_id=parent_run_id,
                event=event,
            ).make_info({"execution_time": time.monotonic() - ts})
        elif self.runs_on.type == GCP_BATCH:  # pragma: no cov
            from .plugins.providers.gcs import gcp_batch_execute

            return gcp_batch_execute(
                self,
                params,
                run_id=parent_run_id,
                event=event,
            ).make_info({"execution_time": time.monotonic() - ts})

        trace.error(
            f"[JOB]: Execution not support runs-on: {self.runs_on.type.value!r} "
            f"yet."
        )
        return Result(
            status=FAILED,
            run_id=run_id,
            parent_run_id=parent_run_id,
            context={
                "status": FAILED,
                "errors": JobError(
                    f"Execute runs-on type: {self.runs_on.type.value!r} does "
                    f"not support yet."
                ).to_dict(),
            },
            info={"execution_time": time.monotonic() - ts},
            extras=self.extras,
        )


def mark_errors(context: DictData, error: JobError) -> None:
    """Make the errors context result with the refs value depends on the nested
    execute func.

    :param context: (DictData) A context data.
    :param error: (JobError) A stage exception object.
    """
    if "errors" in context:
        context["errors"][error.refs] = error.to_dict()
    else:
        context["errors"] = error.to_dict(with_refs=True)


def pop_stages(context: DictData) -> DictData:
    return filter_func(context.pop("stages", {}))


def local_execute_strategy(
    job: Job,
    strategy: DictData,
    params: DictData,
    run_id: str,
    context: DictData,
    *,
    parent_run_id: Optional[str] = None,
    event: Optional[Event] = None,
) -> tuple[Status, DictData]:
    """Local strategy execution with passing dynamic parameters from the
    job execution and strategy matrix.

        This execution is the minimum level of job execution.
    It different with `self.execute` because this method run only one
    strategy and return with context of this strategy data.

        The result of this execution will return result with strategy ID
    that generated from the `gen_id` function with an input strategy value.
    For each stage that execution with this strategy metrix, it will use the
    `set_outputs` method for reconstruct result context data.

    :param job: (Job) A job model that want to execute.
    :param strategy: (DictData) A strategy metrix value. This value will pass
        to the `matrix` key for templating in context data.
    :param params: (DictData) A parameter data.
    :param run_id: (str)
        :param context: (DictData)
        :param parent_run_id: (str | None)
    :param event: (Event) An Event manager instance that use to cancel this
        execution if it forces stopped by parent execution.

    :raise JobError: If event was set.
    :raise JobError: If stage execution raise any error as `StageError`.
    :raise JobError: If the result from execution has `FAILED` status.

    :rtype: tuple[Status, DictData]
    """
    trace: TraceManager = get_trace(
        run_id, parent_run_id=parent_run_id, extras=job.extras
    )
    if strategy:
        strategy_id: str = gen_id(strategy)
        trace.info(f"[JOB]: Execute Strategy: {strategy_id!r}")
        trace.info(f"[JOB]: ... matrix: {strategy!r}")
    else:
        strategy_id: str = "EMPTY"

    current_context: DictData = copy.deepcopy(params)
    current_context.update({"matrix": strategy, "stages": {}})
    total_stage: int = len(job.stages)
    skips: list[bool] = [False] * total_stage
    for i, stage in enumerate(job.stages, start=0):

        if job.extras:
            stage.extras = job.extras

        if event and event.is_set():
            error_msg: str = (
                "Strategy execution was canceled from the event before "
                "start stage execution."
            )
            catch(
                context=context,
                status=CANCEL,
                updated={
                    strategy_id: {
                        "status": CANCEL,
                        "matrix": strategy,
                        "stages": pop_stages(current_context),
                        "errors": JobCancelError(error_msg).to_dict(),
                    },
                },
            )
            raise JobCancelError(error_msg, refs=strategy_id)

        trace.info(f"[JOB]: Execute Stage: {stage.iden!r}")
        rs: Result = stage.execute(
            params=current_context,
            run_id=parent_run_id,
            event=event,
        )
        stage.set_outputs(rs.context, to=current_context)

        if rs.status == SKIP:
            skips[i] = True
            continue

        if rs.status == FAILED:
            error_msg: str = (
                f"Strategy execution was break because its nested-stage, "
                f"{stage.iden!r}, failed."
            )
            catch(
                context=context,
                status=FAILED,
                updated={
                    strategy_id: {
                        "status": FAILED,
                        "matrix": strategy,
                        "stages": pop_stages(current_context),
                        "errors": JobError(error_msg).to_dict(),
                    },
                },
            )
            raise JobError(error_msg, refs=strategy_id)

        elif rs.status == CANCEL:
            error_msg: str = (
                "Strategy execution was canceled from the event after "
                "end stage execution."
            )
            catch(
                context=context,
                status=CANCEL,
                updated={
                    strategy_id: {
                        "status": CANCEL,
                        "matrix": strategy,
                        "stages": pop_stages(current_context),
                        "errors": JobCancelError(error_msg).to_dict(),
                    },
                },
            )
            raise JobCancelError(error_msg, refs=strategy_id)

    status: Status = SKIP if sum(skips) == total_stage else SUCCESS
    catch(
        context=context,
        status=status,
        updated={
            strategy_id: {
                "status": status,
                "matrix": strategy,
                "stages": pop_stages(current_context),
            },
        },
    )
    return status, context


def local_execute(
    job: Job,
    params: DictData,
    *,
    run_id: StrOrNone = None,
    event: Optional[Event] = None,
) -> Result:
    """Local job execution with passing dynamic parameters from the workflow
    execution or directly. It will generate matrix values at the first
    step and run multithread on this metrics to the `stages` field of this job.

    Important:
        This method does not raise any `JobError` because it allows run
    parallel mode. If it raises error from strategy execution, it will catch
    that error and store it in the `errors` key with list of error.

        {
            "errors": [
                {"name": "...", "message": "..."}, ...
            ]
        }

    :param job: (Job) A job model.
    :param params: (DictData) A parameter data.
    :param run_id: (str) A job running ID.
    :param event: (Event) An Event manager instance that use to cancel this
        execution if it forces stopped by parent execution.

    :rtype: Result
    """
    ts: float = time.monotonic()
    parent_run_id: StrOrNone = run_id
    run_id: str = gen_id((job.id or "EMPTY"), unique=True)
    trace: TraceManager = get_trace(
        run_id, parent_run_id=parent_run_id, extras=job.extras
    )
    context: DictData = {"status": WAIT}
    trace.info("[JOB]: Start Local executor.")

    if job.desc:
        trace.debug(f"[JOB]: Description:||{job.desc}||")

    if job.is_skipped(params=params):
        trace.info("[JOB]: Skip because job condition was valid.")
        return Result(
            run_id=run_id,
            parent_run_id=parent_run_id,
            status=SKIP,
            context=catch(context, status=SKIP),
            info={"execution_time": time.monotonic() - ts},
            extras=job.extras,
        )

    event: Event = event or Event()
    ls: str = "Fail-Fast" if job.strategy.fail_fast else "All-Completed"
    workers: int = job.strategy.max_parallel
    strategies: list[DictStr] = job.strategy.make()
    len_strategy: int = len(strategies)
    trace.info(
        f"[JOB]: ... Mode {ls}: {job.id!r} with {workers} "
        f"worker{'s' if workers > 1 else ''}."
    )

    if event and event.is_set():
        return Result(
            run_id=run_id,
            parent_run_id=parent_run_id,
            status=CANCEL,
            context=catch(
                context,
                status=CANCEL,
                updated={
                    "errors": JobCancelError(
                        "Execution was canceled from the event before start "
                        "local job execution."
                    ).to_dict()
                },
            ),
            info={"execution_time": time.monotonic() - ts},
            extras=job.extras,
        )

    with ThreadPoolExecutor(workers, "jb_stg") as executor:
        futures: list[Future] = [
            executor.submit(
                local_execute_strategy,
                job=job,
                strategy=strategy,
                params=params,
                run_id=run_id,
                context=context,
                parent_run_id=parent_run_id,
                event=event,
            )
            for strategy in strategies
        ]

        errors: DictData = {}
        statuses: list[Status] = [WAIT] * len_strategy
        fail_fast: bool = False

        if not job.strategy.fail_fast:
            done: Iterator[Future] = as_completed(futures)
        else:
            done, not_done = wait(futures, return_when=FIRST_EXCEPTION)
            if len(list(done)) != len(futures):
                trace.warning(
                    "[JOB]: Set the event for stop pending job-execution."
                )
                event.set()
                for future in not_done:
                    future.cancel()

                time.sleep(0.01)
                nd: str = (
                    (
                        f", {len(not_done)} strateg"
                        f"{'ies' if len(not_done) > 1 else 'y'} not run!!!"
                    )
                    if not_done
                    else ""
                )
                trace.debug(f"[JOB]: ... Job was set Fail-Fast{nd}")
                done: Iterator[Future] = as_completed(futures)
                fail_fast: bool = True

        for i, future in enumerate(done, start=0):
            try:
                statuses[i], _ = future.result()
            except JobError as e:
                statuses[i] = get_status_from_error(e)
                trace.error(
                    f"[JOB]: {ls} Handler:||{e.__class__.__name__}: {e}"
                )
                mark_errors(errors, e)
            except CancelledError:
                pass

    status: Status = validate_statuses(statuses)

    # NOTE: Prepare status because it does not cancel from parent event but
    #   cancel from failed item execution.
    if fail_fast and status == CANCEL:
        status = FAILED

    return Result(
        run_id=run_id,
        parent_run_id=parent_run_id,
        status=status,
        context=catch(context, status=status, updated=errors),
        info={"execution_time": time.monotonic() - ts},
        extras=job.extras,
    )


def self_hosted_execute(
    job: Job,
    params: DictData,
    *,
    run_id: StrOrNone = None,
    event: Optional[Event] = None,
) -> Result:  # pragma: no cov
    """Self-Hosted job execution with passing dynamic parameters from the
    workflow execution or itself execution. It will make request to the
    self-hosted host url.

    :param job: (Job) A job model that want to execute.
    :param params: (DictData) A parameter data.
    :param run_id: (str) A job running ID.
    :param event: (Event) An Event manager instance that use to cancel this
        execution if it forces stopped by parent execution.

    :rtype: Result
    """
    parent_run_id: StrOrNone = run_id
    run_id: str = gen_id((job.id or "EMPTY"), unique=True)
    trace: TraceManager = get_trace(
        run_id, parent_run_id=parent_run_id, extras=job.extras
    )
    context: DictData = {"status": WAIT}
    trace.info("[JOB]: Start self-hosted executor.")

    if event and event.is_set():
        return Result(
            run_id=run_id,
            parent_run_id=parent_run_id,
            status=CANCEL,
            context=catch(
                context,
                status=CANCEL,
                updated={
                    "errors": JobCancelError(
                        "Execution was canceled from the event before start "
                        "self-hosted execution."
                    ).to_dict()
                },
            ),
            extras=job.extras,
        )

    import requests

    try:
        resp = requests.post(
            job.runs_on.args.host,
            headers={"Auth": f"Barer {job.runs_on.args.token}"},
            data={
                "job": job.model_dump(),
                "params": params,
                "run_id": parent_run_id,
                "extras": job.extras,
            },
        )
    except requests.exceptions.RequestException as e:
        return Result(
            run_id=run_id,
            parent_run_id=parent_run_id,
            status=FAILED,
            context=catch(
                context, status=FAILED, updated={"errors": to_dict(e)}
            ),
            extras=job.extras,
        )

    if resp.status_code != 200:
        raise JobError(
            f"Job execution got error response from self-hosted: "
            f"{job.runs_on.args.host!r}"
        )

    return Result(
        run_id=run_id,
        parent_run_id=parent_run_id,
        status=SUCCESS,
        context=catch(context, status=SUCCESS),
        extras=job.extras,
    )


# Azure Batch execution is now handled by the Azure Batch provider
# See src/ddeutil/workflow/plugins/providers/az.py for implementation


def docker_execution(
    job: Job,
    params: DictData,
    *,
    run_id: StrOrNone = None,
    event: Optional[Event] = None,
):  # pragma: no cov
    """Docker job execution.

    Steps:
        - Pull the image
        - Install this workflow package
        - Start push job to run to target Docker container.
    """
    parent_run_id: StrOrNone = run_id
    run_id: str = gen_id((job.id or "EMPTY"), unique=True)
    trace: TraceManager = get_trace(
        run_id, parent_run_id=parent_run_id, extras=job.extras
    )
    context: DictData = {"status": WAIT}
    trace.info("[JOB]: Start Docker executor.")

    if event and event.is_set():
        return Result(
            run_id=run_id,
            parent_run_id=parent_run_id,
            status=CANCEL,
            context=catch(
                context,
                status=CANCEL,
                updated={
                    "errors": JobCancelError(
                        "Execution was canceled from the event before start "
                        "self-hosted execution."
                    ).to_dict()
                },
            ),
            extras=job.extras,
        )
    print(params)
    return Result(
        run_id=run_id,
        parent_run_id=parent_run_id,
        status=SUCCESS,
        context=catch(context, status=SUCCESS),
        extras=job.extras,
    )
