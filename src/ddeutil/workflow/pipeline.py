# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import copy
import os
import time
from concurrent.futures import (
    FIRST_EXCEPTION,
    Future,
    ThreadPoolExecutor,
    as_completed,
    wait,
)
from datetime import datetime, timedelta
from heapq import heappush
from pickle import PickleError
from queue import Queue
from textwrap import dedent
from threading import Event
from typing import Optional
from zoneinfo import ZoneInfo

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
from .cron import CronRunner
from .exceptions import (
    JobException,
    PipelineException,
    StageException,
    UtilException,
)
from .log import FileLog, Log, get_logger
from .on import On
from .stage import Stage
from .utils import (
    Loader,
    Param,
    Result,
    cross_product,
    dash2underscore,
    delay,
    filter_func,
    gen_id,
    get_diff_sec,
    has_template,
    param2template,
)

logger = get_logger("ddeutil.workflow")


__all__: TupleStr = (
    "Strategy",
    "Job",
    "Pipeline",
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
            "A job ID, this value will add from pipeline after validation "
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
        pipeline execution to strategy matrix.

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
        """Job execution with passing dynamic parameters from the pipeline
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
