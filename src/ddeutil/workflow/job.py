# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Job Model that use for keeping stages and node that running its stages.
The job handle the lineage of stages and location of execution of stages that
mean the job model able to define `runs-on` key that allow you to run this
job.

    This module include Strategy Model that use on the job strategy field.
"""
from __future__ import annotations

import copy
from concurrent.futures import (
    FIRST_EXCEPTION,
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
from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag
from pydantic.functional_validators import field_validator, model_validator
from typing_extensions import Self

from .__types import DictData, DictStr, Matrix, TupleStr
from .conf import config
from .exceptions import (
    JobException,
    StageException,
    UtilException,
)
from .result import Result, Status
from .stages import Stage
from .templates import has_template, param2template
from .utils import cross_product, filter_func, gen_id

MatrixFilter = list[dict[str, Union[str, int]]]


__all__: TupleStr = (
    "Strategy",
    "Job",
    "TriggerRules",
    "TriggerState",
    "RunsOn",
    "RunsOnLocal",
    "RunsOnSelfHosted",
    "RunsOnK8s",
    "make",
    "local_execute_strategy",
    "local_execute",
)


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

    :param matrix: A matrix values that want to cross product to possible
        parallelism values.
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

    # NOTE: Merge all matrix together.
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
        alias="fail-fast",
    )
    max_parallel: int = Field(
        default=1,
        gt=0,
        description=(
            "The maximum number of executor thread pool that want to run "
            "parallel"
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


class TriggerRules(str, Enum):
    """Trigger rules enum object."""

    all_success: str = "all_success"
    all_failed: str = "all_failed"
    all_done: str = "all_done"
    one_failed: str = "one_failed"
    one_success: str = "one_success"
    none_failed: str = "none_failed"
    none_skipped: str = "none_skipped"


class TriggerState(str, Enum):
    waiting: str = "waiting"
    passed: str = "passed"
    skipped: str = "skipped"
    failed: str = "failed"

    def is_waiting(self):
        return self.value == "waiting"


class RunsOnType(str, Enum):
    """Runs-On enum object."""

    LOCAL: str = "local"
    SELF_HOSTED: str = "self_hosted"
    K8S: str = "k8s"


class BaseRunsOn(BaseModel):  # pragma: no cov
    """Base Runs-On Model for generate runs-on types via inherit this model
    object and override execute method.
    """

    model_config = ConfigDict(use_enum_values=True)

    type: Literal[RunsOnType.LOCAL]
    args: DictData = Field(
        default_factory=dict,
        alias="with",
    )


class RunsOnLocal(BaseRunsOn):  # pragma: no cov
    """Runs-on local."""

    type: Literal[RunsOnType.LOCAL] = Field(default=RunsOnType.LOCAL)


class SelfHostedArgs(BaseModel):
    host: str


class RunsOnSelfHosted(BaseRunsOn):  # pragma: no cov
    """Runs-on self-hosted."""

    type: Literal[RunsOnType.SELF_HOSTED] = Field(
        default=RunsOnType.SELF_HOSTED
    )
    args: SelfHostedArgs = Field(alias="with")


class RunsOnK8s(BaseRunsOn):  # pragma: no cov
    """Runs-on Kubernetes."""

    type: Literal[RunsOnType.K8S] = Field(default=RunsOnType.K8S)


def get_discriminator_runs_on(model: dict[str, Any]) -> str:
    return model.get("type", "local")


RunsOn = Annotated[
    Union[
        Annotated[RunsOnK8s, Tag(RunsOnType.K8S)],
        Annotated[RunsOnSelfHosted, Tag(RunsOnType.SELF_HOSTED)],
        Annotated[RunsOnLocal, Tag(RunsOnType.LOCAL)],
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
        ...         ...
        ...     ],
        ... }
    """

    id: Optional[str] = Field(
        default=None,
        description=(
            "A job ID that it will add from workflow after validation process."
        ),
    )
    desc: Optional[str] = Field(
        default=None,
        description="A job description that can be string of markdown content.",
    )
    runs_on: RunsOn = Field(
        default_factory=RunsOnLocal,
        description="A target node for this job to use for execution.",
        alias="runs-on",
    )
    condition: Optional[str] = Field(
        default=None,
        description="A job condition statement to allow job executable.",
        alias="if",
    )
    stages: list[Stage] = Field(
        default_factory=list,
        description="A list of Stage of this job.",
    )
    trigger_rule: TriggerRules = Field(
        default=TriggerRules.all_success,
        description=(
            "A trigger rule of tracking needed jobs if feature will use when "
            "the `raise_error` did not set from job and stage executions."
        ),
        alias="trigger-rule",
    )
    needs: list[str] = Field(
        default_factory=list,
        description="A list of the job ID that want to run before this job.",
    )
    strategy: Strategy = Field(
        default_factory=Strategy,
        description="A strategy matrix that want to generate.",
    )

    @field_validator("desc", mode="after")
    def ___prepare_desc__(cls, value: str) -> str:
        """Prepare description string that was created on a template.

        :rtype: str
        """
        return dedent(value)

    @field_validator("stages", mode="after")
    def __validate_stage_id__(cls, value: list[Stage]) -> list[Stage]:
        """Validate a stage ID of all stage in stages field should not be
        duplicate.

        :rtype: list[Stage]
        """
        # VALIDATE: Validate stage id should not duplicate.
        rs: list[str] = []
        for stage in value:
            name: str = stage.iden
            if name in rs:
                raise ValueError(
                    "Stage name in jobs object should not be duplicate."
                )
            rs.append(name)
        return value

    @model_validator(mode="after")
    def __validate_job_id__(self) -> Self:
        """Validate job id should not have templating syntax.

        :rtype: Self
        """
        # VALIDATE: Validate job id should not dynamic with params template.
        if has_template(self.id):
            raise ValueError("Job ID should not has any template.")

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
                return stage
        raise ValueError(f"Stage ID {stage_id} does not exists")

    def check_needs(
        self, jobs: dict[str, Any]
    ) -> TriggerState:  # pragma: no cov
        """Return True if job's need exists in an input list of job's ID.

        :param jobs: A mapping of job model and its ID.

        :rtype: TriggerState
        """
        if not self.needs:
            return TriggerState.passed

        def make_return(result: bool) -> TriggerState:
            return TriggerState.passed if result else TriggerState.failed

        need_exist: dict[str, Any] = {
            need: jobs[need] for need in self.needs if need in jobs
        }
        if len(need_exist) != len(self.needs):
            return TriggerState.waiting
        elif all("skipped" in need_exist[job] for job in need_exist):
            return TriggerState.skipped
        elif self.trigger_rule == TriggerRules.all_done:
            return TriggerState.passed
        elif self.trigger_rule == TriggerRules.all_success:
            rs = all(
                k not in need_exist[job]
                for k in ("errors", "skipped")
                for job in need_exist
            )
        elif self.trigger_rule == TriggerRules.all_failed:
            rs = all("errors" in need_exist[job] for job in need_exist)
        elif self.trigger_rule == TriggerRules.one_success:
            rs = sum(
                k not in need_exist[job]
                for k in ("errors", "skipped")
                for job in need_exist
            ) + 1 == len(self.needs)
        elif self.trigger_rule == TriggerRules.one_failed:
            rs = sum("errors" in need_exist[job] for job in need_exist) == 1
        elif self.trigger_rule == TriggerRules.none_skipped:
            rs = all("skipped" not in need_exist[job] for job in need_exist)
        elif self.trigger_rule == TriggerRules.none_failed:
            rs = all("errors" not in need_exist[job] for job in need_exist)
        else:  # pragma: no cov
            raise NotImplementedError(
                f"Trigger rule: {self.trigger_rule} does not support yet."
            )
        return make_return(rs)

    def is_skipped(self, params: DictData | None = None) -> bool:
        """Return true if condition of this job do not correct. This process
        use build-in eval function to execute the if-condition.

        :raise JobException: When it has any error raise from the eval
            condition statement.
        :raise JobException: When return type of the eval condition statement
            does not return with boolean type.

        :param params: (DictData) A parameters that want to pass to condition
            template.

        :rtype: bool
        """
        if self.condition is None:
            return False

        params: DictData = {} if params is None else params

        try:
            # WARNING: The eval build-in function is very dangerous. So, it
            #   should use the `re` module to validate eval-string before
            #   running.
            rs: bool = eval(
                param2template(self.condition, params), globals() | params, {}
            )
            if not isinstance(rs, bool):
                raise TypeError("Return type of condition does not be boolean")
            return not rs
        except Exception as err:
            raise JobException(f"{err.__class__.__name__}: {err}") from err

    def set_outputs(self, output: DictData, to: DictData) -> DictData:
        """Set an outputs from execution process to the received context. The
        result from execution will pass to value of `strategies` key.

            For example of setting output method, If you receive execute output
        and want to set on the `to` like;

            ... (i)   output: {'strategy-01': bar, 'strategy-02': bar}
            ... (ii)  to: {'jobs': {}}

        The result of the `to` variable will be;

            ... (iii) to: {
                        'jobs': {
                            '<job-id>': {
                                'strategies': {
                                    'strategy-01': bar,
                                    'strategy-02': bar
                                }
                            }
                        }
                    }

        :raise JobException: If the job's ID does not set and the setting
            default job ID flag does not set.

        :param output: An output context.
        :param to: A context data that want to add output result.

        :rtype: DictData
        """
        if "jobs" not in to:
            to["jobs"] = {}

        if self.id is None and not config.job_default_id:
            raise JobException(
                "This job do not set the ID before setting execution output."
            )

        # NOTE: If the job ID did not set, it will use index of jobs key
        #   instead.
        _id: str = self.id or str(len(to["jobs"]) + 1)

        errors: DictData = (
            {"errors": output.pop("errors", {})} if "errors" in output else {}
        )

        if "SKIP" in output:  # pragma: no cov
            to["jobs"][_id] = output["SKIP"]
        elif self.strategy.is_set():
            to["jobs"][_id] = {"strategies": output, **errors}
        else:
            _output = output.get(next(iter(output), "FIRST"), {})
            _output.pop("matrix", {})
            to["jobs"][_id] = {**_output, **errors}
        return to

    def execute(
        self,
        params: DictData,
        *,
        run_id: str | None = None,
        parent_run_id: str | None = None,
        result: Result | None = None,
        event: Event | None = None,
    ) -> Result:
        """Job execution with passing dynamic parameters from the workflow
        execution. It will generate matrix values at the first step and run
        multithread on this metrics to the `stages` field of this job.

        :param params: An input parameters that use on job execution.
        :param run_id: (str) A job running ID.
        :param parent_run_id: (str) A parent workflow running ID.
        :param result: (Result) A result object for keeping context and status
            data.
        :param event: (Event) An event manager that pass to the
            PoolThreadExecutor.

        :rtype: Result
        """
        result: Result = Result.construct_with_rs_or_id(
            result,
            run_id=run_id,
            parent_run_id=parent_run_id,
            id_logic=(self.id or "not-set"),
        )

        if self.runs_on.type == RunsOnType.LOCAL:
            return local_execute(
                job=self,
                params=params,
                result=result,
                event=event,
            )
        elif self.runs_on.type == RunsOnType.SELF_HOSTED:  # pragma: no cov
            pass
        elif self.runs_on.type == RunsOnType.K8S:  # pragma: no cov
            pass

        # pragma: no cov
        result.trace.error(
            f"[JOB]: Job executor does not support for runs-on type: "
            f"{self.runs_on.type} yet"
        )
        raise NotImplementedError(
            f"The job runs-on other type: {self.runs_on.type} does not "
            f"support yet."
        )


def local_execute_strategy(
    job: Job,
    strategy: DictData,
    params: DictData,
    *,
    result: Result | None = None,
    event: Event | None = None,
    raise_error: bool = False,
) -> Result:
    """Local job strategy execution with passing dynamic parameters from the
    workflow execution to strategy matrix.

        This execution is the minimum level of execution of this job model.
    It different with `self.execute` because this method run only one
    strategy and return with context of this strategy data.

        The result of this execution will return result with strategy ID
    that generated from the `gen_id` function with an input strategy value.

    :raise JobException: If it has any error from `StageException` or
        `UtilException`.

    :param job: (Job) A job model that want to execute.
    :param strategy: A strategy metrix value that use on this execution.
        This value will pass to the `matrix` key for templating.
    :param params: A dynamic parameters that will deepcopy to the context.
    :param result: (Result) A result object for keeping context and status
        data.
    :param event: (Event) An event manager that pass to the PoolThreadExecutor.
    :param raise_error: (bool) A flag that all this method raise error

    :rtype: Result
    """
    if result is None:
        result: Result = Result(run_id=gen_id(job.id or "not-set", unique=True))

    strategy_id: str = gen_id(strategy)

    # PARAGRAPH:
    #
    #       Create strategy execution context and update a matrix and copied
    #   of params. So, the context value will have structure like;
    #
    #   {
    #       "params": { ... },      <== Current input params
    #       "jobs": { ... },        <== Current input params
    #       "matrix": { ... }       <== Current strategy value
    #       "stages": { ... }       <== Catching stage outputs
    #   }
    #
    context: DictData = copy.deepcopy(params)
    context.update({"matrix": strategy, "stages": {}})

    if strategy:
        result.trace.info(f"[JOB]: Execute Strategy ID: {strategy_id}")
        result.trace.info(f"[JOB]: ... Matrix: {strategy_id}")

    # IMPORTANT: The stage execution only run sequentially one-by-one.
    for stage in job.stages:

        if stage.is_skipped(params=context):
            result.trace.info(f"[STAGE]: Skip stage: {stage.iden!r}")
            stage.set_outputs(output={"skipped": True}, to=context)
            continue

        if event and event.is_set():
            error_msg: str = (
                "Job strategy was canceled from event that had set before "
                "strategy execution."
            )
            return result.catch(
                status=Status.FAILED,
                context={
                    strategy_id: {
                        "matrix": strategy,
                        "stages": context.pop("stages", {}),
                        "errors": JobException(error_msg).to_dict(),
                    },
                },
            )

        # PARAGRAPH:
        #
        #       This step will add the stage result to `stages` key in that
        #   stage id. It will have structure like;
        #
        #   {
        #       "params": { ... },
        #       "jobs": { ... },
        #       "matrix": { ... },
        #       "stages": { { "stage-id-01": { "outputs": { ... } } }, ... }
        #   }
        #
        # IMPORTANT:
        #   This execution change all stage running IDs to the current job
        #   running ID, but it still trac log to the same parent running ID
        #   (with passing `run_id` and `parent_run_id` to the stage
        #   execution arguments).
        #
        try:
            stage.set_outputs(
                stage.handler_execute(
                    params=context,
                    run_id=result.run_id,
                    parent_run_id=result.parent_run_id,
                    event=event,
                ).context,
                to=context,
            )
        except (StageException, UtilException) as err:
            result.trace.error(f"[JOB]: {err.__class__.__name__}: {err}")
            if raise_error or config.job_raise_error:
                raise JobException(
                    f"Stage execution error: {err.__class__.__name__}: "
                    f"{err}"
                ) from None

            return result.catch(
                status=Status.FAILED,
                context={
                    strategy_id: {
                        "matrix": strategy,
                        "stages": context.pop("stages", {}),
                        "errors": err.to_dict(),
                    },
                },
            )

    return result.catch(
        status=Status.SUCCESS,
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
    run_id: str | None = None,
    parent_run_id: str | None = None,
    result: Result | None = None,
    event: Event | None = None,
    raise_error: bool = False,
) -> Result:
    """Local job execution with passing dynamic parameters from the workflow
    execution. It will generate matrix values at the first step and run
    multithread on this metrics to the `stages` field of this job.

        This method does not raise any JobException if it runs with
    multi-threading strategy.

    :param job: (Job) A job model that want to execute.
    :param params: (DictData) An input parameters that use on job execution.
    :param run_id: (str) A job running ID for this execution.
    :param parent_run_id: (str) A parent workflow running ID for this release.
    :param result: (Result) A result object for keeping context and status
        data.
    :param event: (Event) An event manager that pass to the PoolThreadExecutor.
    :param raise_error: (bool) A flag that all this method raise error to the
        strategy execution.

    :rtype: Result
    """
    result: Result = Result.construct_with_rs_or_id(
        result,
        run_id=run_id,
        parent_run_id=parent_run_id,
        id_logic=(job.id or "not-set"),
    )
    event: Event = Event() if event is None else event

    # NOTE: Normal Job execution without parallel strategy matrix. It uses
    #   for-loop to control strategy execution sequentially.
    if (not job.strategy.is_set()) or job.strategy.max_parallel == 1:

        for strategy in job.strategy.make():

            if event and event.is_set():  # pragma: no cov
                return result.catch(
                    status=Status.FAILED,
                    context={
                        "errors": JobException(
                            "Job strategy was canceled from event that had set "
                            "before strategy execution."
                        ).to_dict()
                    },
                )

            local_execute_strategy(
                job=job,
                strategy=strategy,
                params=params,
                result=result,
                event=event,
                raise_error=raise_error,
            )

        return result.catch(status=Status.SUCCESS)

    fail_fast_flag: bool = job.strategy.fail_fast
    ls: str = "Fail-Fast" if fail_fast_flag else "All-Completed"
    result.trace.info(
        f"[JOB]: Start multithreading: {job.strategy.max_parallel} threads "
        f"with {ls} mode."
    )

    if event and event.is_set():  # pragma: no cov
        return result.catch(
            status=Status.FAILED,
            context={
                "errors": JobException(
                    "Job strategy was canceled from event that had set "
                    "before strategy execution."
                ).to_dict()
            },
        )

    # IMPORTANT: Start running strategy execution by multithreading because
    #   it will run by strategy values without waiting previous execution.
    with ThreadPoolExecutor(
        max_workers=job.strategy.max_parallel,
        thread_name_prefix="job_strategy_exec_",
    ) as executor:

        futures: list[Future] = [
            executor.submit(
                local_execute_strategy,
                job=job,
                strategy=strategy,
                params=params,
                result=result,
                event=event,
                raise_error=raise_error,
            )
            for strategy in job.strategy.make()
        ]

        context: DictData = {}
        status: Status = Status.SUCCESS

        if not fail_fast_flag:
            done = as_completed(futures, timeout=1800)
        else:
            done, not_done = wait(
                futures, timeout=1800, return_when=FIRST_EXCEPTION
            )

            if len(done) != len(futures):
                result.trace.warning(
                    "[JOB]: Set the event for stop running stage."
                )
                event.set()
                for future in not_done:
                    future.cancel()

            nd: str = (
                f", the strategies do not run is {not_done}" if not_done else ""
            )
            result.trace.debug(f"[JOB]: Strategy is set Fail Fast{nd}")

        for future in done:
            try:
                future.result()
            except JobException as err:
                status = Status.FAILED
                result.trace.error(
                    f"[JOB]: {ls} Catch:\n\t{err.__class__.__name__}:"
                    f"\n\t{err}"
                )
                context.update({"errors": err.to_dict()})

    return result.catch(status=status, context=context)
