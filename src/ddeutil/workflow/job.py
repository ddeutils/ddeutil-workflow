# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
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
from pickle import PickleError
from textwrap import dedent
from threading import Event
from typing import Optional

from pydantic import BaseModel, Field
from pydantic.functional_validators import field_validator, model_validator
from typing_extensions import Self

from .__types import (
    DictData,
    DictStr,
    Matrix,
    MatrixExclude,
    MatrixInclude,
    TupleStr,
)
from .exceptions import (
    JobException,
    StageException,
    UtilException,
)
from .log import get_logger
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


__all__: TupleStr = (
    "Strategy",
    "Job",
)


class Strategy(BaseModel):
    """Strategy Model that will combine a matrix together for running the
    special job.

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
        """
        dash2underscore("max-parallel", values)
        dash2underscore("fail-fast", values)
        return values

    def is_set(self) -> bool:
        """Return True if this strategy was set from yaml template."""
        return len(self.matrix) > 0

    def make(self) -> list[DictStr]:
        """Return List of product of matrix values that already filter with
        exclude and add include.

        :rtype: list[DictStr]
        """
        # NOTE: If it does not set matrix, it will return list of an empty dict.
        if not (mt := self.matrix):
            return [{}]

        final: list[DictStr] = []
        for r in cross_product(matrix=mt):
            if any(
                all(r[k] == v for k, v in exclude.items())
                for exclude in self.exclude
            ):
                continue
            final.append(r)

        # NOTE: If it is empty matrix and include, it will return list of an
        #   empty dict.
        if not final and not self.include:
            return [{}]

        # NOTE: Add include to generated matrix with exclude list.
        add: list[DictStr] = []
        for include in self.include:
            # VALIDATE:
            #   Validate any key in include list should be a subset of some one
            #   in matrix.
            if all(not (set(include.keys()) <= set(m.keys())) for m in final):
                raise ValueError("Include should have the keys equal to matrix")

            # VALIDATE:
            #   Validate value of include does not duplicate with generated
            #   matrix.
            if any(
                all(include.get(k) == v for k, v in m.items())
                for m in [*final, *add]
            ):
                continue
            add.append(include)
        final.extend(add)
        return final


class Job(BaseModel):
    """Job Model (group of stages).

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
            "A job ID, this value will add from workflow after validation "
            "process."
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
    def __prepare_keys(cls, values: DictData) -> DictData:
        """Rename key that use dash to underscore because Python does not
        support this character exist in any variable name.
        """
        dash2underscore("runs-on", values)
        return values

    @field_validator("desc", mode="after")
    def ___prepare_desc(cls, value: str) -> str:
        """Prepare description string that was created on a template."""
        return dedent(value)

    @model_validator(mode="after")
    def __prepare_running_id(self):
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
        """Return stage model that match with an input stage ID."""
        for stage in self.stages:
            if stage_id == (stage.id or ""):
                return stage
        raise ValueError(f"Stage ID {stage_id} does not exists")

    def set_outputs(self, output: DictData) -> DictData:
        """Setting output of job execution"""
        if len(output) > 1 and self.strategy.is_set():
            return {"strategies": output}
        return output[next(iter(output))]

    def execute_strategy(
        self,
        strategy: DictData,
        params: DictData,
        *,
        event: Event | None = None,
    ) -> Result:
        """Job Strategy execution with passing dynamic parameters from the
        workflow execution to strategy matrix.

            This execution is the minimum level execution of job model.

        :param strategy: A metrix strategy value.
        :param params: A dynamic parameters.
        :param event: An manger event that pass to the PoolThreadExecutor.
        :rtype: Result

        :raise JobException: If it has any error from StageException or
            UtilException.
        """
        # NOTE: Force stop this execution if event was set from main execution.
        if event and event.is_set():
            return Result(
                status=1,
                context={
                    gen_id(strategy): {
                        "matrix": strategy,
                        "stages": {},
                        "error_message": {
                            "message": "Process Event stopped before execution"
                        },
                    },
                },
            )

        # NOTE: Create strategy execution context and update a matrix and copied
        #   of params. So, the context value will have structure like;
        #   ---
        #   {
        #       "params": { ... },      <== Current input params
        #       "jobs": { ... },        <== Current input params
        #       "matrix": { ... }       <== Current strategy value
        #   }
        #
        context: DictData = params
        context.update({"matrix": strategy})

        # IMPORTANT: The stage execution only run sequentially one-by-one.
        for stage in self.stages:

            # IMPORTANT: Change any stage running IDs to this job running ID.
            stage: Stage = stage.get_running_id(self.run_id)

            _st_name: str = stage.id or stage.name

            if stage.is_skipped(params=context):
                logger.info(
                    f"({self.run_id}) [JOB]: Skip the stage: {_st_name!r}"
                )
                continue

            logger.info(
                f"({self.run_id}) [JOB]: Start execute the stage: {_st_name!r}"
            )

            # NOTE: Logging a matrix that pass on this stage execution.
            if strategy:
                logger.info(f"({self.run_id}) [JOB]: Matrix: {strategy}")

            # NOTE:
            #       I do not use below syntax because `params` dict be the
            #   reference memory pointer and it was changed when I action
            #   anything like update or re-construct this.
            #
            #       ... params |= stage.execute(params=params)
            #
            #   This step will add the stage result to ``stages`` key in
            #   that stage id. It will have structure like;
            #   ---
            #   {
            #       "params": { ... },
            #       "jobs": { ... },
            #       "matrix": { ... },
            #       "stages": { { "stage-id-1": ... }, ... }
            #   }
            #
            if event and event.is_set():
                return Result(
                    status=1,
                    context={
                        gen_id(strategy): {
                            "matrix": strategy,
                            # NOTE: If job strategy executor use multithreading,
                            #   it will not filter function object from context.
                            # ---
                            # "stages": filter_func(context.pop("stages", {})),
                            "stages": context.pop("stages", {}),
                            "error_message": {
                                "message": (
                                    "Process Event stopped before execution"
                                ),
                            },
                        },
                    },
                )
            try:
                rs: Result = stage.execute(params=context)
                stage.set_outputs(rs.context, to=context)
            except (StageException, UtilException) as err:
                logger.error(
                    f"({self.run_id}) [JOB]: {err.__class__.__name__}: {err}"
                )
                raise JobException(
                    f"Get stage execution error: {err.__class__.__name__}: "
                    f"{err}"
                ) from None

            # NOTE: Remove new stage object that was created from
            #   ``get_running_id`` method.
            del stage

        return Result(
            status=0,
            context={
                gen_id(strategy): {
                    "matrix": strategy,
                    # NOTE: (WF001) filter own created function from stages
                    #   value, because it does not dump with pickle when you
                    #   execute with multiprocess.
                    #
                    "stages": filter_func(context.pop("stages", {})),
                },
            },
        )

    def execute(self, params: DictData | None = None) -> Result:
        """Job execution with passing dynamic parameters from the workflow
        execution. It will generate matrix values at the first step and for-loop
        any metrix to all stages dependency.

        :param params: An input parameters that use on job execution.
        :rtype: Result
        """
        context: DictData = {}

        # NOTE: Normal Job execution.
        if (not self.strategy.is_set()) or self.strategy.max_parallel == 1:
            for strategy in self.strategy.make():
                rs: Result = self.execute_strategy(
                    strategy, params=copy.deepcopy(params)
                )
                context.update(rs.context)
            return Result(
                status=0,
                context=context,
            )

        # # WARNING: (WF001) I got error that raise when use
        # #  ``ProcessPoolExecutor``;
        # #   ---
        # #   _pickle.PicklingError: Can't pickle
        # #       <function ??? at 0x000001F0BE80F160>: attribute lookup ???
        # #       on ddeutil.workflow.stage failed
        # #
        # # from multiprocessing import Event, Manager
        # with Manager() as manager:
        #     event: Event = manager.Event()
        #
        #     # NOTE: Start process pool executor for running strategy executor
        #     #   in parallel mode.
        #     with ProcessPoolExecutor(
        #         max_workers=self.strategy.max_parallel
        #     ) as executor:
        #         futures: list[Future] = [
        #             executor.submit(
        #                 self.execute_strategy,
        #                 strategy,
        #                 params=copy.deepcopy(params),
        #                 event=event,
        #             )
        #             for strategy in self.strategy.make()
        #         ]
        #         if self.strategy.fail_fast:
        #             rs = self.__catch_fail_fast(event, futures)
        #         else:
        #             rs = self.__catch_all_completed(futures)

        # NOTE: Create event for cancel executor stop running.
        event: Event = Event()

        with ThreadPoolExecutor(
            max_workers=self.strategy.max_parallel
        ) as executor:
            futures: list[Future] = [
                executor.submit(
                    self.execute_strategy,
                    strategy,
                    params=copy.deepcopy(params),
                    event=event,
                )
                for strategy in self.strategy.make()
            ]

            # NOTE: Dynamic catching futures object with fail-fast flag.
            if self.strategy.fail_fast:
                rs: Result = self.__catch_fail_fast(event, futures)
            else:
                rs: Result = self.__catch_all_completed(futures)
        return Result(
            status=0,
            context=rs.context,
        )

    def __catch_fail_fast(self, event: Event, futures: list[Future]) -> Result:
        """Job parallel pool futures catching with fail-fast mode. That will
        stop all not done futures if it receive the first exception from all
        running futures.

        :param event:
        :param futures: A list of futures.
        :rtype: Result
        """
        context: DictData = {}
        # NOTE: Get results from a collection of tasks with a
        #   timeout that has the first exception.
        done, not_done = wait(
            futures, timeout=1800, return_when=FIRST_EXCEPTION
        )
        nd: str = (
            f", the strategies do not run is {not_done}" if not_done else ""
        )
        logger.debug(f"({self.run_id}) [JOB]: Strategy is set Fail Fast{nd}")

        if len(done) != len(futures):

            # NOTE: Stop all running tasks
            event.set()

            # NOTE: Cancel any scheduled tasks
            for future in futures:
                future.cancel()

        status: int = 0
        for future in done:
            if future.exception():
                status = 1
                logger.error(
                    f"({self.run_id}) [JOB]: One stage failed with: "
                    f"{future.exception()}, shutting down this future."
                )
            elif future.cancelled():
                continue
            else:
                rs: Result = future.result(timeout=60)
                context.update(rs.context)
        return Result(status=status, context=context)

    def __catch_all_completed(self, futures: list[Future]) -> Result:
        """Job parallel pool futures catching with all-completed mode.

        :param futures: A list of futures.
        :rtype: Result
        """
        context: DictData = {}
        status: int = 0
        for future in as_completed(futures):
            try:
                rs: Result = future.result(timeout=60)
                context.update(rs.context)
            except PickleError as err:
                # NOTE: (WF001) I do not want to fix this issue because
                #   it does not make sense and over-engineering with
                #   this bug fix process.
                raise JobException(
                    f"PyStage that create object on locals does use "
                    f"parallel in strategy execution;\n\t{err}"
                ) from None
            except TimeoutError:
                status = 1
                logger.warning(
                    f"({self.run_id}) [JOB]: Task is hanging. Attempting to "
                    f"kill."
                )
                future.cancel()
                time.sleep(0.1)
                if not future.cancelled():
                    logger.warning(
                        f"({self.run_id}) [JOB]: Failed to cancel the task."
                    )
                else:
                    logger.warning(
                        f"({self.run_id}) [JOB]: Task canceled successfully."
                    )
            except JobException as err:
                status = 1
                logger.error(
                    f"({self.run_id}) [JOB]: Get stage exception with "
                    f"fail-fast does not set;\n{err.__class__.__name__}:\n\t"
                    f"{err}"
                )
        return Result(status=status, context=context)
