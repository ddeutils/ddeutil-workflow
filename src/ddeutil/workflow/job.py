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
import time
from concurrent.futures import (
    FIRST_EXCEPTION,
    Future,
    ThreadPoolExecutor,
    as_completed,
    wait,
)
from functools import lru_cache
from textwrap import dedent
from threading import Event
from typing import Optional, Union

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
    dash2underscore,
    filter_func,
    gen_id,
    has_template,
)

logger = get_logger("ddeutil.workflow")
MatrixInclude = list[dict[str, Union[str, int]]]
MatrixExclude = list[dict[str, Union[str, int]]]


__all__: TupleStr = (
    "Strategy",
    "Job",
    "make",
)


@freeze_args
@lru_cache
def make(
    matrix: Matrix,
    include: MatrixInclude,
    exclude: MatrixExclude,
) -> list[DictStr]:
    """Make a list of product of matrix values that already filter with
    exclude matrix and add specific matrix with include.

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
    """Strategy Model that will combine a matrix together for running the
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
    include: MatrixInclude = Field(
        default_factory=list,
        description="A list of additional matrix that want to adds-in.",
    )
    exclude: MatrixExclude = Field(
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


class Job(BaseModel):
    """Job Pydantic model object (group of stages).

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
    needs: list[str] = Field(
        default_factory=list,
        description="A list of the job ID that want to run before this job.",
    )
    strategy: Strategy = Field(
        default_factory=Strategy,
        description="A strategy matrix that want to generate.",
    )
    run_id: Optional[str] = Field(
        default=None,
        description="A running job ID.",
        repr=False,
        exclude=True,
    )

    @model_validator(mode="before")
    def __prepare_keys__(cls, values: DictData) -> DictData:
        """Rename key that use dash to underscore because Python does not
        support this character exist in any variable name.

        :param values: A passing value that coming for initialize this object.
        :rtype: DictData
        """
        dash2underscore("runs-on", values)
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
    def __prepare_running_id_and_stage_name__(self) -> Self:
        """Prepare the job running ID.

        :rtype: Self
        """
        if self.run_id is None:
            self.run_id = gen_id(self.id or "", unique=True)

        # VALIDATE: Validate job id should not dynamic with params template.
        if has_template(self.id):
            raise ValueError("Job ID should not has any template.")

        return self

    def get_running_id(self, run_id: str) -> Self:
        """Return Job model object that changing job running ID with an
        input running ID.

        :param run_id: A replace job running ID.
        :rtype: Self
        """
        return self.model_copy(update={"run_id": run_id})

    def stage(self, stage_id: str) -> Stage:
        """Return stage model that match with an input stage ID.

        :param stage_id: A stage ID that want to extract from this job.
        :rtype: Stage
        """
        for stage in self.stages:
            if stage_id == (stage.id or ""):
                return stage
        raise ValueError(f"Stage ID {stage_id} does not exists")

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

        logger.debug(f"({self.run_id}) [JOB]: Set outputs on: {_id}")
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
        event: Event | None = None,
    ) -> Result:
        """Job Strategy execution with passing dynamic parameters from the
        workflow execution to strategy matrix.

            This execution is the minimum level of execution of this job model.
        It different with ``self.execute`` because this method run only one
        strategy and return with context of this strategy data.

        :raise JobException: If it has any error from ``StageException`` or
            ``UtilException``.

        :param strategy: A metrix strategy value.
        :param params: A dynamic parameters.
        :param event: An manger event that pass to the PoolThreadExecutor.

        :rtype: Result
        """
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

        # IMPORTANT: The stage execution only run sequentially one-by-one.
        for stage in self.stages:

            # IMPORTANT: Change any stage running IDs to this job running ID.
            stage: Stage = stage.get_running_id(self.run_id)

            name: str = stage.id or stage.name

            if stage.is_skipped(params=context):
                logger.info(f"({self.run_id}) [JOB]: Skip stage: {name!r}")
                continue

            logger.info(
                f"({self.run_id}) [JOB]: Start execute the stage: {name!r}"
            )

            # NOTE: Logging a matrix that pass on this stage execution.
            if strategy:
                logger.info(f"({self.run_id}) [JOB]: Matrix: {strategy}")

            # NOTE: Force stop this execution if event was set from main
            #   execution.
            if event and event.is_set():
                return Result(
                    status=1,
                    context={
                        strategy_id: {
                            "matrix": strategy,
                            # NOTE: If job strategy executor use multithreading,
                            #   it will not filter function object from context.
                            # ---
                            # "stages": filter_func(context.pop("stages", {})),
                            "stages": context.pop("stages", {}),
                            "error": JobException(
                                "Job strategy was canceled from trigger event "
                                "that had stopped before execution."
                            ),
                            "error_message": (
                                "Job strategy was canceled from trigger event "
                                "that had stopped before execution."
                            ),
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
                    stage.execute(params=context).context,
                    to=context,
                )
            except (StageException, UtilException) as err:
                logger.error(
                    f"({self.run_id}) [JOB]: {err.__class__.__name__}: {err}"
                )
                if config.job_raise_error:
                    raise JobException(
                        f"Get stage execution error: {err.__class__.__name__}: "
                        f"{err}"
                    ) from None
                return Result(
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

            # NOTE: Remove the current stage object that was created from
            #   ``get_running_id`` method for saving memory.
            del stage

        return Result(
            status=0,
            context={
                strategy_id: {
                    "matrix": strategy,
                    "stages": filter_func(context.pop("stages", {})),
                },
            },
        )

    def execute(self, params: DictData | None = None) -> Result:
        """Job execution with passing dynamic parameters from the workflow
        execution. It will generate matrix values at the first step and run
        multithread on this metrics to the ``stages`` field of this job.

        :param params: An input parameters that use on job execution.
        :rtype: Result
        """

        # NOTE: I use this condition because this method allow passing empty
        #   params and I do not want to create new dict object.
        params: DictData = {} if params is None else params
        context: DictData = {}

        # NOTE: Normal Job execution without parallel strategy.
        if (not self.strategy.is_set()) or self.strategy.max_parallel == 1:
            for strategy in self.strategy.make():
                rs: Result = self.execute_strategy(
                    strategy=strategy,
                    params=params,
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
                    event=event,
                )
                for strategy in self.strategy.make()
            ]

            # NOTE: Dynamic catching futures object with fail-fast flag.

            return (
                self.__catch_fail_fast(event=event, futures=futures)
                if self.strategy.fail_fast
                else self.__catch_all_completed(futures=futures)
            )

    def __catch_fail_fast(
        self,
        event: Event,
        futures: list[Future],
        *,
        timeout: int = 1800,
        result_timeout: int = 60,
    ) -> Result:
        """Job parallel pool futures catching with fail-fast mode. That will
        stop all not done futures if it receive the first exception from all
        running futures.

        :param event: An event manager instance that able to set stopper on the
            observing thread/process.
        :param futures: A list of futures.
        :param timeout: A timeout to waiting all futures complete.
        :param result_timeout: A timeout of getting result from the future
            instance when it was running completely.
        :rtype: Result
        """
        rs_final: Result = Result()
        context: DictData = {}
        status: int = 0

        # NOTE: Get results from a collection of tasks with a timeout that has
        #   the first exception.
        done, not_done = wait(
            futures,
            timeout=timeout,
            return_when=FIRST_EXCEPTION,
        )
        nd: str = (
            f", the strategies do not run is {not_done}" if not_done else ""
        )
        logger.debug(f"({self.run_id}) [JOB]: Strategy is set Fail Fast{nd}")

        # NOTE: Stop all running tasks with setting the event manager and cancel
        #   any scheduled tasks.
        #       This case is not common error and not raise when all process
        #   running normally, so, I will ignore and skip coverage to it.
        #
        if len(done) != len(futures):  # pragma: no cov
            event.set()
            for future in futures:
                future.cancel()

            del future

        print("This line")

        for future in done:
            if future.exception():
                status = 1
                logger.error(
                    f"({self.run_id}) [JOB]: One stage failed with: "
                    f"{future.exception()}, shutting down this future."
                )
            elif future.cancelled():
                continue

            # NOTE: Update the result context to main job context.
            context.update(future.result(timeout=result_timeout).context)

            del future

        return rs_final.catch(status=status, context=context)

    def __catch_all_completed(
        self,
        futures: list[Future],
        *,
        timeout: int = 1800,
        result_timeout: int = 60,
    ) -> Result:
        """Job parallel pool futures catching with all-completed mode.

        :param futures: A list of futures that want to catch all completed
            result.
        :param timeout: A timeout to waiting all futures complete.
        :param result_timeout: A timeout of getting result from the future
            instance when it was running completely.
        :rtype: Result
        """
        rs_final: Result = Result()
        context: DictData = {}
        status: int = 0
        for future in as_completed(futures, timeout=timeout):
            try:
                context.update(future.result(timeout=result_timeout).context)
            except TimeoutError:
                status = 1
                logger.warning(
                    f"({self.run_id}) [JOB]: Task is hanging. Attempting to "
                    f"kill."
                )
                future.cancel()
                time.sleep(0.1)

                stmt: str = (
                    "Failed to cancel the task."
                    if not future.cancelled()
                    else "Task canceled successfully."
                )
                logger.warning(f"({self.run_id}) [JOB]: {stmt}")
            except JobException as err:
                status = 1
                logger.error(
                    f"({self.run_id}) [JOB]: Get stage exception with "
                    f"fail-fast does not set;\n{err.__class__.__name__}:\n\t"
                    f"{err}"
                )
            finally:
                del future
        return rs_final.catch(status=status, context=context)
