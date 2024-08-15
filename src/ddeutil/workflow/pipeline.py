# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import copy
import logging
import os
import time
from concurrent.futures import (
    FIRST_EXCEPTION,
    Future,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
    wait,
)
from datetime import datetime
from multiprocessing import Event, Manager
from pickle import PickleError
from queue import Queue
from typing import Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from pydantic.functional_validators import model_validator
from typing_extensions import Self

from .__types import DictData, DictStr, Matrix, MatrixExclude, MatrixInclude
from .exceptions import JobException, PipelineException, StageException
from .loader import Loader
from .on import On
from .scheduler import CronRunner
from .stage import Stage
from .utils import (
    Param,
    Result,
    cross_product,
    dash2underscore,
    gen_id,
    get_diff_sec,
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
        ...         'second': ['foo', 'bar']
        ...     },
        ...     'include': [{'first': 4, 'second': 'foo'}],
        ...     'exclude': [{'first': 1, 'second': 'bar'}],
        ... }
    """

    fail_fast: bool = Field(default=False)
    max_parallel: int = Field(default=1, gt=0)
    matrix: Matrix = Field(default_factory=dict)
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
        ...     "strategy": {},
        ...     "needs": [],
        ...     "stages": [
        ...         {
        ...             "name": "Some stage",
        ...             "run": "print('Hello World')",
        ...         },
        ...     ],
        ... }
    """

    name: Optional[str] = Field(default=None)
    desc: Optional[str] = Field(default=None)
    runs_on: Optional[str] = Field(default=None)
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

    @model_validator(mode="before")
    def __prepare_keys(cls, values: DictData) -> DictData:
        """Rename key that use dash to underscore because Python does not
        support this character exist in any variable name.
        """
        dash2underscore("runs-on", values)
        return values

    def stage(self, stage_id: str) -> Stage:
        """Return stage model that match with an input stage ID."""
        for stage in self.stages:
            if stage_id == (stage.id or ""):
                return stage
        raise ValueError(f"Stage ID {stage_id} does not exists")

    @staticmethod
    def set_outputs(output: DictData) -> DictData:
        if len(output) > 1:
            return {"strategies": output}

        return output[next(iter(output))]

    def strategy_execute(
        self,
        strategy: DictData,
        params: DictData,
        *,
        event: Event | None = None,
    ) -> Result:
        """Strategy execution with passing dynamic parameters from the pipeline
        stage execution.

        :param strategy:
        :param params:
        :param event: An manger event that pass to the PoolThreadExecutor.
        :rtype: Result
        """
        _stop_rs: Result = Result(
            status=1,
            context={
                gen_id(strategy): {
                    "matrix": strategy,
                    "stages": {},
                    "error": "Event stopped",
                },
            },
        )
        if event and event.is_set():
            return _stop_rs

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
            _st_name: str = stage.id or stage.name

            if stage.is_skip(params=context):
                logging.info(f"[JOB]: Skip the stage: {_st_name!r}")
                continue
            logging.info(f"[JOB]: Start execute the stage: {_st_name!r}")

            # NOTE: Logging a matrix that pass on this stage execution.
            if strategy:
                logging.info(f"[...]: Matrix: {strategy}")

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
                return _stop_rs
            rs: Result = stage.execute(params=context)
            if rs.status == 0:
                stage.set_outputs(rs.context, params=context)
            else:
                raise JobException(
                    f"Getting status does not equal zero on stage: "
                    f"{stage.name}."
                )
        # TODO: Filter and warning if it pass any objects to context between
        #   strategy job executor like function, etc.
        return Result(
            status=0,
            context={
                gen_id(strategy): {
                    "matrix": strategy,
                    "stages": context.pop("stages", {}),
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
        strategy_context: DictData = {}
        rs = Result(context=strategy_context)

        if self.strategy.max_parallel == 1:
            for strategy in self.strategy.make():
                rs: Result = self.strategy_execute(
                    strategy, params=copy.deepcopy(params)
                )
                strategy_context.update(rs.context)
            return rs

        # FIXME: (WF001) I got error that raise when use
        #  ``ProcessPoolExecutor``;
        #   ---
        #   _pickle.PicklingError: Can't pickle
        #       <function ??? at 0x000001F0BE80F160>: attribute lookup ???
        #       on ddeutil.workflow.stage failed
        #
        with Manager() as manager:
            event: Event = manager.Event()

            with ProcessPoolExecutor(
                max_workers=self.strategy.max_parallel
            ) as pool:
                pool_result: list[Future] = [
                    pool.submit(
                        self.strategy_execute,
                        st,
                        params=copy.deepcopy(params),
                        event=event,
                    )
                    for st in self.strategy.make()
                ]
                if self.strategy.fail_fast:

                    # NOTE: Get results from a collection of tasks with a
                    #   timeout that has the first exception.
                    done, not_done = wait(
                        pool_result, timeout=60, return_when=FIRST_EXCEPTION
                    )
                    logging.error(
                        "[JOB]: Strategy is set Fail Fast, the strategies do "
                        f"not run is {not_done}"
                    )

                    # NOTE: Stop all running tasks
                    event.set()

                    # NOTE: Cancel any scheduled tasks
                    for future in pool_result:
                        future.cancel()

                    for f in done:
                        if f.exception():
                            logging.error(
                                f"One task failed with: {f.exception()}, "
                                f"shutting down"
                            )
                        elif f.cancelled():
                            continue
                        else:
                            rs: Result = f.result(timeout=60)
                            strategy_context.update(rs.context)
                    rs.status = 1
                    rs.context = strategy_context
                    return rs

                for pool_rs in as_completed(pool_result):
                    try:
                        rs: Result = pool_rs.result(timeout=60)
                        strategy_context.update(rs.context)
                    except PickleError as err:
                        # NOTE: I do not want to fix this issue because it does
                        #   not make sense and over-engineering with this bug
                        #   fix process.
                        raise JobException(
                            f"PyStage that create object on locals does use "
                            f"parallel in strategy;\n\t{err}"
                        ) from None
                    except TimeoutError:
                        rs.status = 1
                        logging.warning("Task is hanging. Attempting to kill.")
                        pool_rs.cancel()
                        if not pool_rs.cancelled():
                            logging.warning("Failed to cancel the task.")
                        else:
                            logging.warning("Task canceled successfully.")
                    except StageException as err:
                        rs.status = 1
                        logging.warning(
                            f"Get stage exception with fail-fast does not set;"
                            f"\n\t{err}"
                        )
        rs.status = 0
        rs.context = strategy_context
        return rs


class Pipeline(BaseModel):
    """Pipeline Model this is the main feature of this project because it use to
    be workflow data for running everywhere that you want. It use lightweight
    coding line to execute it.
    """

    name: str = Field(description="A pipeline name.")
    desc: Optional[str] = Field(
        default=None,
        description=(
            "A pipeline description that is able to be string of markdown "
            "content."
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

    @classmethod
    def from_loader(
        cls,
        name: str,
        externals: DictData | None = None,
    ) -> Self:
        """Create Pipeline instance from the Loader object.

        :param name: A pipeline name that want to pass to Loader object.
        :param externals: An external parameters that want to pass to Loader
            object.
        """
        loader: Loader = Loader(name, externals=(externals or {}))
        loader_data: DictData = copy.deepcopy(loader.data)

        # NOTE: Add name to loader data
        loader_data["name"] = name.replace(" ", "_")

        if "jobs" not in loader_data:
            raise ValueError("Config does not set ``jobs`` value")

        # NOTE: Prepare `on` data
        cls.__bypass_on(loader_data)
        return cls.model_validate(loader_data)

    @classmethod
    def __bypass_on(cls, data: DictData, externals: DictData | None = None):
        """Bypass the on data to loaded config data."""
        if on := data.pop("on", []):
            if isinstance(on, str):
                on = [on]
            if any(not isinstance(i, (dict, str)) for i in on):
                raise TypeError("The ``on`` key should be list of str or dict")
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

    @model_validator(mode="after")
    def __validate_jobs_need(self):
        for job in self.jobs:
            if not_exist := [
                need for need in self.jobs[job].needs if need not in self.jobs
            ]:
                raise PipelineException(
                    f"This needed jobs: {not_exist} do not exist in this "
                    f"pipeline."
                )
        return self

    def job(self, name: str) -> Job:
        """Return Job model that exists on this pipeline.

        :param name: A job name that want to get from a mapping of job models.
        :type name: str

        :rtype: Job
        :returns: A job model that exists on this pipeline by input name.
        """
        if name not in self.jobs:
            raise ValueError(f"Job {name!r} does not exists")
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
        params: DictData | None = None,
        *,
        waiting_sec: int = 600,
        sleep_interval: int = 10,
    ) -> str:
        """Start running pipeline with the on schedule in period of 30 minutes.
        That mean it will still running at background 30 minutes until the
        schedule matching with its time.
        """
        params: DictData = params or {}
        logging.info(f"[CORE] Start release: {self.name!r} : {on.cronjob}")

        gen: CronRunner = on.generate(datetime.now())
        tz: ZoneInfo = gen.tz
        next_running_time: datetime = gen.next

        if get_diff_sec(next_running_time, tz=tz) < waiting_sec:
            logging.debug(
                f"[CORE]: {self.name} closely to run >> "
                f"{next_running_time:%Y-%m-%d %H:%M:%S}"
            )

            # NOTE: Release when the time is nearly to schedule time.
            while (duration := get_diff_sec(next_running_time, tz=tz)) > 15:
                time.sleep(sleep_interval)
                logging.debug(
                    f"[CORE]: {self.name!r} : Sleep until: {duration}"
                )

            time.sleep(1)
            rs: Result = self.execute(params=params)
            logging.debug(f"{rs.context}")

            return f"[CORE]: Start Execute: {self.name}"
        return f"[CORE]: {self.name} does not closely to run yet."

    def poke(self, params: DictData | None = None):
        """Poke pipeline threading task for executing with its schedules that
        was set on the `on`.
        """
        params: DictData = params or {}
        logging.info(
            f"[CORE]: Start Poking: {self.name!r} :"
            f"{gen_id(self.name, unique=True)}"
        )
        results = []
        with ThreadPoolExecutor(
            max_workers=int(
                os.getenv("WORKFLOW_CORE_MAX_PIPELINE_POKING", "4")
            ),
        ) as executor:
            futures: list[Future] = [
                executor.submit(
                    self.release,
                    on,
                    params=params,
                )
                for on in self.on
            ]
            for future in as_completed(futures):
                rs = future.result()
                logging.info(rs)
                results.append(rs)
        return results

    def job_execute(self): ...

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

        ---

        See Also:

            The result of execution process for each jobs and stages on this
        pipeline will keeping in dict which able to catch out with all jobs and
        stages by dot annotation.

            For example, when I want to use the output from previous stage, I
        can access it with syntax:

            ... ${job-name}.stages.${stage-id}.outputs.${key}

        """
        logging.info(
            f"[CORE]: Start Execute: {self.name}:"
            f"{gen_id(self.name, unique=True)}"
        )
        params: DictData = params or {}

        # NOTE: It should not do anything if it does not have job.
        if not self.jobs:
            logging.warning("[PIPELINE]: This pipeline does not have any jobs")
            return Result(status=0, context=params)

        # NOTE: create a job queue that keep the job that want to running after
        #   it dependency condition.
        jq: Queue = Queue()
        for job_id in self.jobs:
            jq.put(job_id)

        ts: float = time.monotonic()
        not_time_out_flag: bool = True

        # NOTE: Create result context that will pass this context to any
        #   execution dependency.
        rs: Result = Result(context=self.parameterize(params))

        # IMPORTANT: The job execution can run parallel and waiting by needed.
        while not jq.empty() and (
            not_time_out_flag := ((time.monotonic() - ts) < timeout)
        ):
            job_id: str = jq.get()
            logging.info(f"[PIPELINE]: Start execute the job: {job_id!r}")
            job: Job = self.jobs[job_id]

            # TODO: Condition on ``needs`` of this job was set. It should create
            #   multithreading process on this step.
            #   But, I don't know how to handle changes params between each job
            #   execution while its use them together.
            #   ---
            #   >>> import multiprocessing
            #   >>> with multiprocessing.Pool(processes=3) as pool:
            #   ...     results = pool.starmap(merge_names, ('', '', ...))
            #   ---
            #   This case we use multi-process because I want to split usage of
            #   data in this level, that mean the data that push to parallel job
            #   should not use across another job.
            #
            if any(need not in rs.context["jobs"] for need in job.needs):
                jq.put(job_id)

            # NOTE: copy current the result context for reference other job
            #   context.
            job_context: DictData = copy.deepcopy(rs.context)
            job_rs: Result = job.execute(params=job_context)
            if job_rs.status != 0:
                logging.warning(
                    f"Getting status does not equal zero on job: {job_id}."
                )
                rs.status = 1
                rs.context["jobs"][job_id] = job.set_outputs(job_rs.context)
                return rs

            # NOTE: Receive output of job execution.
            rs.context["jobs"][job_id] = job.set_outputs(job_rs.context)

        if not not_time_out_flag:
            logging.warning("Execution of pipeline was time out")
            rs.status = 1
            return rs
        rs.status = 0
        return rs
