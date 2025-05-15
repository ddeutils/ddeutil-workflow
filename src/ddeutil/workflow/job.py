# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Job model that use for store Stage models and node parameter that use for
running these stages. The job model handle the lineage of stages and location of
execution that mean you can define `runs-on` field with the Self-Hosted mode
for execute on target machine instead of the current local machine.

    This module include Strategy model that use on the job `strategy` field for
making matrix values before execution parallelism stage execution.

    The Job model does not implement `handler_execute` same as Stage model
because the job should raise only `JobError` class from the execution
method.
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
from typing import Annotated, Any, Literal, Optional, Union

from ddeutil.core import freeze_args
from pydantic import BaseModel, Discriminator, Field, SecretStr, Tag
from pydantic.functional_validators import field_validator, model_validator
from typing_extensions import Self

from .__types import DictData, DictStr, Matrix, StrOrNone
from .errors import JobError, to_dict
from .result import CANCEL, FAILED, SKIP, SUCCESS, WAIT, Result, Status
from .reusables import has_template, param2template
from .stages import Stage
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
    """Strategy model that will combine a matrix together for running the
    special job with combination of matrix data.

        This model does not be the part of job only because you can use it to
    any model object. The objective of this model is generating metrix result
    that comming from combination logic with any matrix values for running it
    with parallelism.

        [1, 2, 3] x [a, b] --> [1a], [1b], [2a], [2b], [3a], [3b]

    Data Validate:
        >>> strategy = {
        ...     'max-parallel': 1,
        ...     'fail-fast': False,
        ...     'matrix': {
        ...         'first': [1, 2, 3],
        ...         'second': ['foo', 'bar'],
        ...     },
        ...     'include': [{'first': 4, 'second': 'foo'}],
        ...     'exclude': [{'first': 1, 'second': 'bar'}],
        ... }
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

        :rtype: bool
        """
        return len(self.matrix) > 0

    def make(self) -> list[DictStr]:
        """Return List of product of matrix values that already filter with
        exclude and add include.

        :rtype: list[DictStr]
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
    DOCKER = "docker"


class BaseRunsOn(BaseModel):  # pragma: no cov
    """Base Runs-On Model for generate runs-on types via inherit this model
    object and override execute method.
    """

    type: RunsOn = Field(description="A runs-on type.")
    args: DictData = Field(
        default_factory=dict,
        alias="with",
        description=(
            "An argument that pass to the runs-on execution function. This "
            "args will override by this child-model with specific args model."
        ),
    )


class OnLocal(BaseRunsOn):  # pragma: no cov
    """Runs-on local."""

    type: Literal[RunsOn.LOCAL] = Field(
        default=RunsOn.LOCAL, validate_default=True
    )


class SelfHostedArgs(BaseModel):
    """Self-Hosted arguments."""

    host: str = Field(description="A host URL of the target self-hosted.")


class OnSelfHosted(BaseRunsOn):  # pragma: no cov
    """Runs-on self-hosted."""

    type: Literal[RunsOn.SELF_HOSTED] = Field(
        default=RunsOn.SELF_HOSTED, validate_default=True
    )
    args: SelfHostedArgs = Field(alias="with")


class AzBatchArgs(BaseModel):
    batch_account_name: str
    batch_account_key: SecretStr
    batch_account_url: str
    storage_account_name: str
    storage_account_key: SecretStr


class OnAzBatch(BaseRunsOn):  # pragma: no cov

    type: Literal[RunsOn.AZ_BATCH] = Field(
        default=RunsOn.AZ_BATCH, validate_default=True
    )
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

    type: Literal[RunsOn.DOCKER] = Field(
        default=RunsOn.DOCKER, validate_default=True
    )
    args: DockerArgs = Field(alias="with", default_factory=DockerArgs)


def get_discriminator_runs_on(model: dict[str, Any]) -> RunsOn:
    """Get discriminator of the RunsOn models."""
    t = model.get("type")
    return RunsOn(t) if t else RunsOn.LOCAL


RunsOnModel = Annotated[
    Union[
        Annotated[OnSelfHosted, Tag(RunsOn.SELF_HOSTED)],
        Annotated[OnDocker, Tag(RunsOn.DOCKER)],
        Annotated[OnLocal, Tag(RunsOn.LOCAL)],
    ],
    Discriminator(get_discriminator_runs_on),
]


class Job(BaseModel):
    """Job Pydantic model object (short descripte: a group of stages).

        This job model allow you to use for-loop that call matrix strategy. If
    you pass matrix mapping, and it is able to generate, you will see it running
    with loop of matrix values.

    Data Validate:
        >>> job = {
        ...     "runs-on": {"type": "local"},
        ...     "strategy": {
        ...         "max-parallel": 1,
        ...         "matrix": {
        ...             "first": [1, 2, 3],
        ...             "second": ['foo', 'bar'],
        ...         },
        ...     },
        ...     "needs": [],
        ...     "stages": [
        ...         {
        ...             "name": "Some stage",
        ...             "run": "print('Hello World')",
        ...         },
        ...     ],
        ... }
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
        for stage in value:
            name: str = stage.iden
            if name in rs:
                raise ValueError(
                    f"Stage name, {name!r}, should not be duplicate."
                )
            rs.append(name)
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

    def check_needs(
        self, jobs: dict[str, DictData]
    ) -> Status:  # pragma: no cov
        """Return trigger status from checking job's need trigger rule logic was
        valid. The return status should be SUCCESS, FAILED, WAIT, or SKIP.

        :param jobs: (dict[str, DictData]) A mapping of job ID and its context
            data that return from execution process.

        :raise NotImplementedError: If the job trigger rule out of scope.

        :rtype: Status
        """
        if not self.needs:
            return SUCCESS

        def make_return(result: bool) -> Status:
            return SUCCESS if result else FAILED

        need_exist: dict[str, Any] = {
            need: jobs[need] for need in self.needs if need in jobs
        }
        if len(need_exist) != len(self.needs):
            return WAIT
        elif all(need_exist[job].get("skipped", False) for job in need_exist):
            return SKIP
        elif self.trigger_rule == Rule.ALL_DONE:
            return SUCCESS
        elif self.trigger_rule == Rule.ALL_SUCCESS:
            rs = all(
                (
                    "errors" not in need_exist[job]
                    and not need_exist[job].get("skipped", False)
                )
                for job in need_exist
            )
        elif self.trigger_rule == Rule.ALL_FAILED:
            rs = all("errors" in need_exist[job] for job in need_exist)
        elif self.trigger_rule == Rule.ONE_SUCCESS:
            rs = sum(
                (
                    "errors" not in need_exist[job]
                    and not need_exist[job].get("skipped", False)
                )
                for job in need_exist
            ) + 1 == len(self.needs)
        elif self.trigger_rule == Rule.ONE_FAILED:
            rs = sum("errors" in need_exist[job] for job in need_exist) == 1
        elif self.trigger_rule == Rule.NONE_SKIPPED:
            rs = all(
                not need_exist[job].get("skipped", False) for job in need_exist
            )
        elif self.trigger_rule == Rule.NONE_FAILED:
            rs = all("errors" not in need_exist[job] for job in need_exist)
        else:  # pragma: no cov
            return FAILED
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

        :param output: (DictData) A result data context that want to extract
            and transfer to the `strategies` key in receive context.
        :param to: (DictData) A received context data.
        :param job_id: (StrOrNone) A job ID if the `id` field does not set.

        :rtype: DictData
        """
        if "jobs" not in to:
            to["jobs"] = {}

        if self.id is None and job_id is None:
            raise JobError(
                "This job do not set the ID before setting execution output."
            )

        _id: str = self.id or job_id
        output: DictData = output.copy()
        errors: DictData = (
            {"errors": output.pop("errors", {})} if "errors" in output else {}
        )
        skipping: dict[str, bool] = (
            {"skipped": output.pop("skipped", False)}
            if "skipped" in output
            else {}
        )

        if self.strategy.is_set():
            to["jobs"][_id] = {"strategies": output, **skipping, **errors}
        elif len(k := output.keys()) > 1:  # pragma: no cov
            raise JobError(
                "Strategy output from execution return more than one ID while "
                "this job does not set strategy."
            )
        else:
            _output: DictData = {} if len(k) == 0 else output[list(k)[0]]
            _output.pop("matrix", {})
            to["jobs"][_id] = {**_output, **skipping, **errors}
        return to

    def execute(
        self,
        params: DictData,
        *,
        run_id: StrOrNone = None,
        parent_run_id: StrOrNone = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Job execution with passing dynamic parameters from the workflow
        execution. It will generate matrix values at the first step and run
        multithread on this metrics to the `stages` field of this job.

            This method be execution routing for call dynamic execution function
        with specific target `runs-on` value.

        :param params: (DictData) A parameter data.
        :param run_id: (str) A job running ID.
        :param parent_run_id: (str) A parent running ID.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :rtype: Result
        """
        result: Result = Result.construct_with_rs_or_id(
            run_id=run_id,
            parent_run_id=parent_run_id,
            id_logic=(self.id or "EMPTY"),
            extras=self.extras,
        )

        result.trace.info(
            f"[JOB]: Execute "
            f"{''.join(self.runs_on.type.value.split('_')).title()}: "
            f"{self.id!r}"
        )
        if self.runs_on.type == RunsOn.LOCAL:
            return local_execute(
                self,
                params,
                run_id=run_id,
                parent_run_id=parent_run_id,
                event=event,
            )
        elif self.runs_on.type == RunsOn.SELF_HOSTED:  # pragma: no cov
            pass
        elif self.runs_on.type == RunsOn.DOCKER:  # pragma: no cov
            docker_execution(
                self,
                params,
                run_id=run_id,
                parent_run_id=parent_run_id,
                event=event,
            )

        result.trace.error(
            f"[JOB]: Execute not support runs-on: {self.runs_on.type.value!r} "
            f"yet."
        )
        return result.catch(
            status=FAILED,
            context={
                "errors": JobError(
                    f"Execute runs-on type: {self.runs_on.type.value!r} does "
                    f"not support yet."
                ).to_dict(),
            },
        )


def local_execute_strategy(
    job: Job,
    strategy: DictData,
    params: DictData,
    *,
    result: Optional[Result] = None,
    event: Optional[Event] = None,
) -> Result:
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
    :param result: (Result) A Result instance for return context and status.
    :param event: (Event) An Event manager instance that use to cancel this
        execution if it forces stopped by parent execution.

    :raise JobError: If event was set.
    :raise JobError: If stage execution raise any error as `StageError`.
    :raise JobError: If the result from execution has `FAILED` status.

    :rtype: Result
    """
    result: Result = result or Result(
        run_id=gen_id(job.id or "EMPTY", unique=True),
        extras=job.extras,
    )
    if strategy:
        strategy_id: str = gen_id(strategy)
        result.trace.info(f"[JOB]: Execute Strategy: {strategy_id!r}")
        result.trace.info(f"[JOB]: ... matrix: {strategy!r}")
    else:
        strategy_id: str = "EMPTY"

    context: DictData = copy.deepcopy(params)
    context.update({"matrix": strategy, "stages": {}})
    for stage in job.stages:

        if job.extras:
            stage.extras = job.extras

        if stage.is_skipped(params=context):
            result.trace.info(f"[JOB]: Skip Stage: {stage.iden!r}")
            stage.set_outputs(output={"skipped": True}, to=context)
            continue

        if event and event.is_set():
            error_msg: str = "Job strategy was canceled because event was set."
            result.catch(
                status=CANCEL,
                context={
                    strategy_id: {
                        "matrix": strategy,
                        "stages": filter_func(context.pop("stages", {})),
                        "errors": JobError(error_msg).to_dict(),
                    },
                },
            )
            raise JobError(error_msg, refs=strategy_id)

        result.trace.info(f"[JOB]: Execute Stage: {stage.iden!r}")
        rs: Result = stage.handler_execute(
            params=context,
            run_id=result.run_id,
            parent_run_id=result.parent_run_id,
            event=event,
        )
        stage.set_outputs(rs.context, to=context)

        if rs.status == FAILED:
            error_msg: str = (
                f"Strategy break because stage, {stage.iden!r}, return "
                f"`FAILED` status."
            )
            result.catch(
                status=FAILED,
                context={
                    strategy_id: {
                        "matrix": strategy,
                        "stages": filter_func(context.pop("stages", {})),
                        "errors": JobError(error_msg).to_dict(),
                    },
                },
            )
            raise JobError(error_msg, refs=strategy_id)

    return result.catch(
        status=SUCCESS,
        context={
            strategy_id: {
                "matrix": strategy,
                "stages": filter_func(context.pop("stages", {})),
            },
        },
    )


def local_execute(
    job: Job,
    params: DictData,
    *,
    run_id: StrOrNone = None,
    parent_run_id: StrOrNone = None,
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
    :param parent_run_id: (str) A parent workflow running ID.
    :param event: (Event) An Event manager instance that use to cancel this
        execution if it forces stopped by parent execution.

    :rtype: Result
    """
    result: Result = Result.construct_with_rs_or_id(
        run_id=run_id,
        parent_run_id=parent_run_id,
        id_logic=(job.id or "EMPTY"),
        extras=job.extras,
    )

    event: Event = event or Event()
    fail_fast_flag: bool = job.strategy.fail_fast
    ls: str = "Fail-Fast" if fail_fast_flag else "All-Completed"
    workers: int = job.strategy.max_parallel
    result.trace.info(
        f"[JOB]: Execute {ls}: {job.id!r} with {workers} "
        f"worker{'s' if workers > 1 else ''}."
    )

    if event and event.is_set():
        return result.catch(
            status=CANCEL,
            context={
                "errors": JobError(
                    "Job was canceled from event that had set before "
                    "local job execution."
                ).to_dict()
            },
        )

    with ThreadPoolExecutor(
        max_workers=workers, thread_name_prefix="job_strategy_exec_"
    ) as executor:

        futures: list[Future] = [
            executor.submit(
                local_execute_strategy,
                job=job,
                strategy=strategy,
                params=params,
                result=result,
                event=event,
            )
            for strategy in job.strategy.make()
        ]

        context: DictData = {}
        status: Status = SUCCESS

        if not fail_fast_flag:
            done: Iterator[Future] = as_completed(futures)
        else:
            done, not_done = wait(futures, return_when=FIRST_EXCEPTION)
            if len(list(done)) != len(futures):
                result.trace.warning(
                    "[JOB]: Handler Fail-Fast: Got exception and set event."
                )
                event.set()
                for future in not_done:
                    future.cancel()
                time.sleep(0.075)

            nd: str = (
                (
                    f", {len(not_done)} strateg"
                    f"{'ies' if len(not_done) > 1 else 'y'} not run!!!"
                )
                if not_done
                else ""
            )
            result.trace.debug(f"[JOB]: ... Job was set Fail-Fast{nd}")
            done: Iterator[Future] = as_completed(futures)

        for future in done:
            try:
                future.result()
            except JobError as e:
                status = FAILED
                result.trace.error(
                    f"[JOB]: {ls} Error Handler:||{e.__class__.__name__}:||{e}"
                )
                if "errors" in context:
                    context["errors"][e.refs] = e.to_dict()
                else:
                    context["errors"] = e.to_dict(with_refs=True)
            except CancelledError:
                pass
    return result.catch(status=status, context=context)


def self_hosted_execute(
    job: Job,
    params: DictData,
    *,
    run_id: StrOrNone = None,
    parent_run_id: StrOrNone = None,
    event: Optional[Event] = None,
) -> Result:  # pragma: no cov
    """Self-Hosted job execution with passing dynamic parameters from the
    workflow execution or itself execution. It will make request to the
    self-hosted host url.

    :param job: (Job) A job model that want to execute.
    :param params: (DictData) A parameter data.
    :param run_id: (str) A job running ID.
    :param parent_run_id: (str) A parent workflow running ID.
    :param event: (Event) An Event manager instance that use to cancel this
        execution if it forces stopped by parent execution.

    :rtype: Result
    """
    result: Result = Result.construct_with_rs_or_id(
        run_id=run_id,
        parent_run_id=parent_run_id,
        id_logic=(job.id or "EMPTY"),
        extras=job.extras,
    )

    if event and event.is_set():
        return result.catch(
            status=CANCEL,
            context={
                "errors": JobError(
                    "Job was canceled from event that had set before start "
                    "self-hosted execution."
                ).to_dict()
            },
        )

    import requests

    try:
        resp = requests.post(
            job.runs_on.args.host,
            headers={"Auth": f"Barer {job.runs_on.args.token}"},
            data={
                "job": job.model_dump(),
                "params": params,
                "result": result.__dict__,
            },
        )
    except requests.exceptions.RequestException as e:
        return result.catch(status=FAILED, context={"errors": to_dict(e)})

    if resp.status_code != 200:
        raise JobError(
            f"Job execution error from request to self-hosted: "
            f"{job.runs_on.args.host!r}"
        )

    return result.catch(status=SUCCESS)


def azure_batch_execute(
    job: Job,
    params: DictData,
    *,
    run_id: StrOrNone = None,
    parent_run_id: StrOrNone = None,
    event: Optional[Event] = None,
) -> Result:  # pragma: no cov
    """Azure Batch job execution that will run all job's stages on the Azure
    Batch Node and extract the result file to be returning context result.

    Steps:
        - Create a Batch account and a Batch pool.
        - Create a Batch job and add tasks to the job. Each task represents a
          command to run on a compute node.
        - Specify the command to run the Python script in the task. You can use
          the cmd /c command to run the script with the Python interpreter.
        - Upload the Python script and any required input files to Azure Storage
          Account.
        - Configure the task to download the input files from Azure Storage to
          the compute node before running the script.
        - Monitor the job and retrieve the output files from Azure Storage.

    References:
        - https://docs.azure.cn/en-us/batch/tutorial-parallel-python

    :param job:
    :param params:
    :param run_id:
    :param parent_run_id:
    :param event:

    :rtype: Result
    """
    result: Result = Result.construct_with_rs_or_id(
        run_id=run_id,
        parent_run_id=parent_run_id,
        id_logic=(job.id or "EMPTY"),
        extras=job.extras,
    )
    if event and event.is_set():
        return result.catch(
            status=CANCEL,
            context={
                "errors": JobError(
                    "Job was canceled from event that had set before start "
                    "azure-batch execution."
                ).to_dict()
            },
        )
    print(params)
    return result.catch(status=SUCCESS)


def docker_execution(
    job: Job,
    params: DictData,
    *,
    run_id: StrOrNone = None,
    parent_run_id: StrOrNone = None,
    event: Optional[Event] = None,
):  # pragma: no cov
    """Docker job execution.

    Steps:
        - Pull the image
        - Install this workflow package
        - Start push job to run to target Docker container.
    """
    result: Result = Result.construct_with_rs_or_id(
        run_id=run_id,
        parent_run_id=parent_run_id,
        id_logic=(job.id or "EMPTY"),
        extras=job.extras,
    )
    if event and event.is_set():
        return result.catch(
            status=CANCEL,
            context={
                "errors": JobError(
                    "Job Docker execution was canceled from event that "
                    "had set before start execution."
                ).to_dict()
            },
        )
    print(params)
    return result.catch(status=SUCCESS)
