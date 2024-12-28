# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Job Model that use for keeping stages and node that running its stages.
The job handle the lineage of stages and location of execution of stages that
mean the job model able to define ``runs-on`` key that allow you to run this
job.
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
from typing import Any, Optional, Union

from ddeutil.core import freeze_args
from pydantic import BaseModel, Field
from pydantic.functional_validators import field_validator, model_validator
from typing_extensions import Self

from .__types import DictData, DictStr, Matrix, TupleStr
from .conf import config, get_logger
from .exceptions import (
    JobException,
    StageException,
    UtilException,
)
from .stage import Stage
from .utils import (
    Result,
    cross_product,
    cut_id,
    dash2underscore,
    filter_func,
    gen_id,
    has_template,
)

logger = get_logger("ddeutil.workflow")
MatrixFilter = list[dict[str, Union[str, int]]]


__all__: TupleStr = (
    "Strategy",
    "Job",
    "TriggerRules",
    "make",
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

    # NOTE: Remove matrix that exists on the exclude.
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
        #   Validate any key in include list should be a subset of some one
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
    any model object. The propose of this model is generate metrix result that
    comming from combination logic with any matrix values for running it with
    parallelism.

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
        serialization_alias="fail-fast",
    )
    max_parallel: int = Field(
        default=1,
        gt=0,
        description=(
            "The maximum number of executor thread pool that want to run "
            "parallel"
        ),
        serialization_alias="max-parallel",
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

    @model_validator(mode="before")
    def __prepare_keys(cls, values: DictData) -> DictData:
        """Rename key that use dash to underscore because Python does not
        support this character exist in any variable name.

        :param values: A parsing values to this models
        :rtype: DictData
        """
        dash2underscore("max-parallel", values)
        dash2underscore("fail-fast", values)
        return values

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


class RunsOn(str, Enum):
    """Runs-On enum object."""

    local: str = "local"
    docker: str = "docker"


class Job(BaseModel):
    """Job Pydantic model object (short descripte: a group of stages).

        This job model allow you to use for-loop that call matrix strategy. If
    you pass matrix mapping and it able to generate, you will see it running
    with loop of matrix values.

    Data Validate:
        >>> job = {
        ...     "runs-on": None,
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
    runs_on: Optional[str] = Field(
        default=None,
        description="A target executor node for this job use to execution.",
        serialization_alias="runs-on",
    )
    stages: list[Stage] = Field(
        default_factory=list,
        description="A list of Stage of this job.",
    )
    trigger_rule: TriggerRules = Field(
        default=TriggerRules.all_success,
        description="A trigger rule of tracking needed jobs.",
        serialization_alias="trigger-rule",
    )
    needs: list[str] = Field(
        default_factory=list,
        description="A list of the job ID that want to run before this job.",
    )
    strategy: Strategy = Field(
        default_factory=Strategy,
        description="A strategy matrix that want to generate.",
    )

    @model_validator(mode="before")
    def __prepare_keys__(cls, values: DictData) -> DictData:
        """Rename key that use dash to underscore because Python does not
        support this character exist in any variable name.

        :param values: A passing value that coming for initialize this object.
        :rtype: DictData
        """
        dash2underscore("runs-on", values)
        dash2underscore("trigger-rule", values)
        return values

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
            name: str = stage.id or stage.name
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

    def check_needs(self, jobs: dict[str, Any]) -> bool:
        """Return True if job's need exists in an input list of job's ID.

        :rtype: bool
        """
        return all(need in jobs for need in self.needs)

    def set_outputs(self, output: DictData, to: DictData) -> DictData:
        """Set an outputs from execution process to the receive context. The
        result from execution will pass to value of ``strategies`` key.

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
        if self.id is None and not config.job_default_id:
            raise JobException(
                "This job do not set the ID before setting execution output."
            )

        # NOTE: Create jobs key to receive an output from the job execution.
        if "jobs" not in to:
            to["jobs"] = {}

        # NOTE: If the job ID did not set, it will use index of jobs key
        #   instead.
        _id: str = self.id or str(len(to["jobs"]) + 1)
        to["jobs"][_id] = (
            {"strategies": output}
            if self.strategy.is_set()
            else output.get(next(iter(output), "DUMMY"), {})
        )
        return to

    def execute_strategy(
        self,
        strategy: DictData,
        params: DictData,
        *,
        run_id: str | None = None,
        event: Event | None = None,
    ) -> Result:
        """Job Strategy execution with passing dynamic parameters from the
        workflow execution to strategy matrix.

            This execution is the minimum level of execution of this job model.
        It different with ``self.execute`` because this method run only one
        strategy and return with context of this strategy data.

            The result of this execution will return result with strategy ID
        that generated from the `gen_id` function with a input strategy value.

        :raise JobException: If it has any error from ``StageException`` or
            ``UtilException``.

        :param strategy: A strategy metrix value that use on this execution.
            This value will pass to the `matrix` key for templating.
        :param params: A dynamic parameters that will deepcopy to the context.
        :param run_id: A job running ID for this strategy execution.
        :param event: An manger event that pass to the PoolThreadExecutor.

        :rtype: Result
        """
        run_id: str = run_id or gen_id(self.id or "", unique=True)
        strategy_id: str = gen_id(strategy)
        rs: Result = Result(run_id=run_id)

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

        # IMPORTANT: The stage execution only run sequentially one-by-one.
        for stage in self.stages:

            if stage.is_skipped(params=context):
                logger.info(
                    f"({cut_id(run_id)}) [JOB]: Skip stage: {stage.iden!r}"
                )
                continue

            logger.info(
                f"({cut_id(run_id)}) [JOB]: Execute stage: {stage.iden!r}"
            )

            # NOTE: Logging a matrix that pass on this stage execution.
            if strategy:
                logger.info(f"({cut_id(run_id)}) [JOB]: ... Matrix: {strategy}")

            # NOTE: Force stop this execution if event was set from main
            #   execution.
            if event and event.is_set():
                error_msg: str = (
                    "Job strategy was canceled from event that had set before "
                    "strategy execution."
                )
                return rs.catch(
                    status=1,
                    context={
                        strategy_id: {
                            "matrix": strategy,
                            # NOTE: If job strategy executor use multithreading,
                            #   it will not filter function object from context.
                            # ---
                            # "stages": filter_func(context.pop("stages", {})),
                            #
                            "stages": context.pop("stages", {}),
                            "error": JobException(error_msg),
                            "error_message": error_msg,
                        },
                    },
                )

            # PARAGRAPH:
            #
            #       I do not use below syntax because `params` dict be the
            #   reference memory pointer and it was changed when I action
            #   anything like update or re-construct this.
            #
            #       ... params |= stage.execute(params=params)
            #
            #   This step will add the stage result to ``stages`` key in
            #   that stage id. It will have structure like;
            #
            #   {
            #       "params": { ... },
            #       "jobs": { ... },
            #       "matrix": { ... },
            #       "stages": { { "stage-id-1": ... }, ... }
            #   }
            #
            try:
                stage.set_outputs(
                    stage.execute(params=context, run_id=run_id).context,
                    to=context,
                )
            except (StageException, UtilException) as err:
                logger.error(
                    f"({cut_id(run_id)}) [JOB]: {err.__class__.__name__}: {err}"
                )
                if config.job_raise_error:
                    raise JobException(
                        f"Get stage execution error: {err.__class__.__name__}: "
                        f"{err}"
                    ) from None
                return rs.catch(
                    status=1,
                    context={
                        strategy_id: {
                            "matrix": strategy,
                            "stages": context.pop("stages", {}),
                            "error": err,
                            "error_message": f"{err.__class__.__name__}: {err}",
                        },
                    },
                )

            # NOTE: Remove the current stage object for saving memory.
            del stage

        return rs.catch(
            status=0,
            context={
                strategy_id: {
                    "matrix": strategy,
                    "stages": filter_func(context.pop("stages", {})),
                },
            },
        )

    def execute(self, params: DictData, run_id: str | None = None) -> Result:
        """Job execution with passing dynamic parameters from the workflow
        execution. It will generate matrix values at the first step and run
        multithread on this metrics to the ``stages`` field of this job.

        :param params: An input parameters that use on job execution.
        :param run_id: A job running ID for this execution.

        :rtype: Result
        """

        # NOTE: I use this condition because this method allow passing empty
        #   params and I do not want to create new dict object.
        run_id: str = run_id or gen_id(self.id or "", unique=True)
        context: DictData = {}

        # NOTE: Normal Job execution without parallel strategy matrix. It use
        #   for-loop to control strategy execution sequentially.
        if (not self.strategy.is_set()) or self.strategy.max_parallel == 1:
            for strategy in self.strategy.make():
                rs: Result = self.execute_strategy(
                    strategy=strategy,
                    params=params,
                    run_id=run_id,
                )
                context.update(rs.context)
            return Result(
                status=0,
                context=context,
            )

        # NOTE: Create event for cancel executor by trigger stop running event.
        event: Event = Event()

        # IMPORTANT: Start running strategy execution by multithreading because
        #   it will running by strategy values without waiting previous
        #   execution.
        with ThreadPoolExecutor(
            max_workers=self.strategy.max_parallel,
            thread_name_prefix="job_strategy_exec_",
        ) as executor:

            futures: list[Future] = [
                executor.submit(
                    self.execute_strategy,
                    strategy=strategy,
                    params=params,
                    run_id=run_id,
                    event=event,
                )
                for strategy in self.strategy.make()
            ]

            return (
                self.__catch_fail_fast(event, futures=futures, run_id=run_id)
                if self.strategy.fail_fast
                else self.__catch_all_completed(futures=futures, run_id=run_id)
            )

    @staticmethod
    def __catch_fail_fast(
        event: Event,
        futures: list[Future],
        run_id: str,
        *,
        timeout: int = 1800,
    ) -> Result:
        """Job parallel pool futures catching with fail-fast mode. That will
        stop and set event on all not done futures if it receive the first
        exception from all running futures.

        :param event: An event manager instance that able to set stopper on the
            observing multithreading.
        :param futures: A list of futures.
        :param run_id: A job running ID from execution.
        :param timeout: A timeout to waiting all futures complete.

        :rtype: Result
        """
        rs_final: Result = Result(run_id=run_id)
        context: DictData = {}
        status: int = 0

        # NOTE: Get results from a collection of tasks with a timeout that has
        #   the first exception.
        done, not_done = wait(
            futures, timeout=timeout, return_when=FIRST_EXCEPTION
        )
        nd: str = (
            f", the strategies do not run is {not_done}" if not_done else ""
        )
        logger.debug(f"({cut_id(run_id)}) [JOB]: Strategy is set Fail Fast{nd}")

        # NOTE:
        #       Stop all running tasks with setting the event manager and cancel
        #   any scheduled tasks.
        #
        if len(done) != len(futures):
            event.set()
            for future in not_done:
                future.cancel()

        future: Future
        for future in done:

            # NOTE: Handle the first exception from feature
            if err := future.exception():
                status: int = 1
                logger.error(
                    f"({cut_id(run_id)}) [JOB]: Fail-fast catching:\n\t"
                    f"{future.exception()}"
                )
                context.update(
                    {
                        "error": err,
                        "error_message": f"{err.__class__.__name__}: {err}",
                    },
                )
                continue

            # NOTE: Update the result context to main job context.
            context.update(future.result().context)

        return rs_final.catch(status=status, context=context)

    @staticmethod
    def __catch_all_completed(
        futures: list[Future],
        run_id: str,
        *,
        timeout: int = 1800,
    ) -> Result:
        """Job parallel pool futures catching with all-completed mode.

        :param futures: A list of futures.
        :param run_id: A job running ID from execution.
        :param timeout: A timeout to waiting all futures complete.

        :rtype: Result
        """
        rs_final: Result = Result(run_id=run_id)
        context: DictData = {}
        status: int = 0

        for future in as_completed(futures, timeout=timeout):
            try:
                context.update(future.result().context)
            except JobException as err:
                status = 1
                logger.error(
                    f"({cut_id(run_id)}) [JOB]: All-completed catching:\n\t"
                    f"{err.__class__.__name__}:\n\t{err}"
                )
                context.update(
                    {
                        "error": err,
                        "error_message": f"{err.__class__.__name__}: {err}",
                    },
                )

        return rs_final.catch(status=status, context=context)
