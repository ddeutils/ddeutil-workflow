# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import itertools
import logging
import os
import time
from datetime import datetime
from hashlib import md5
from queue import Queue
from typing import Optional, Union
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from pydantic.functional_validators import model_validator
from typing_extensions import Self

from .__types import DictData, DictStr
from .loader import Loader
from .on import On
from .stage import Stage
from .utils import Param, dash2underscore


class Strategy(BaseModel):
    """Strategy Model that will combine a matrix together for running the
    special job.

    Data Validate:
        >>> strategy = {
        ...     'matrix': {
        ...         'first': [1, 2, 3],
        ...         'second': ['foo', 'bar']
        ...     },
        ...     'include': [{'first': 4, 'second': 'foo'}],
        ...     'exclude': [{'first': 1, 'second': 'bar'}],
        ... }
    """

    fail_fast: bool = Field(default=False)
    max_parallel: int = Field(default=-1)
    matrix: dict[str, Union[list[str], list[int]]] = Field(default_factory=dict)
    include: list[dict[str, Union[str, int]]] = Field(default_factory=list)
    exclude: list[dict[str, Union[str, int]]] = Field(
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
        if not (mt := self.matrix):
            return [{}]
        final: list[DictStr] = []
        for r in [
            {_k: _v for e in mapped for _k, _v in e.items()}
            for mapped in itertools.product(
                *[[{k: v} for v in vs] for k, vs in mt.items()]
            )
        ]:
            if any(
                all(r[k] == v for k, v in exclude.items())
                for exclude in self.exclude
            ):
                continue
            final.append(r)

        # NOTE: If it is empty matrix, it will return list of empty dict.
        if not final:
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
        ...             "name": "Set variable and function",
        ...             "run": (
        ...                 "var_inside: str = 'Inside'\\n"
        ...                 "def echo() -> None:\\n"
        ...                 '  print(f"Echo {var_inside}"\\n'
        ...             ),
        ...         },
        ...     ],
        ... }
    """

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

    def execute(self, params: DictData | None = None) -> DictData:
        """Execute job with passing dynamic parameters from the pipeline."""
        for strategy in self.strategy.make():
            params.update({"matrix": strategy})

            # TODO: we should add option for ``wait_as_complete`` for release
            #   a stage execution to run on background.
            # IMPORTANT: The stage execution only run sequentially one-by-one.
            for stage in self.stages:
                _st_name: str = stage.id if stage.id else stage.name

                if stage.is_skip(params=params):
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
                #       ... params |= stage.execute(params=params)
                stage.execute(params=params)
        # TODO: We should not return matrix key to outside and make new output
        #   that support running different matrix in stage output.
        return params


class Pipeline(BaseModel):
    """Pipeline Model this is the main feature of this project because it use to
    be workflow data for running everywhere that you want. It use lightweight
    coding line to execute it.
    """

    name: str = Field(description="A pipeline name.")
    desc: Optional[str] = Field(
        default=None,
        description="A pipeline description.",
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
        loader_data: DictData = loader.data.copy()

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

    def gen_run_id(self) -> str:
        """Generate running pipeline ID for able to tracking that pipeline
        execution logging.
        """
        tz: ZoneInfo = ZoneInfo(os.getenv("WORKFLOW_CORE_TIMEZONE", "UTC"))
        return md5(
            f"{self.name}{datetime.now(tz=tz):%Y%m%d%H%M%S%f}".encode()
        ).hexdigest()

    def parameterize(self, params: DictData | None = None) -> DictData:
        """Prepare parameters before passing to execution process."""
        params: DictData = params or {}
        # VALIDATE: Incoming params should have keys that set on this pipeline.
        if check_key := tuple(
            f"{k!r}"
            for k in self.params
            if (k not in params and self.params[k].required)
        ):
            raise ValueError(
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

    def execute(
        self,
        params: DictData | None = None,
        *,
        timeout: int = 60,
    ) -> DictData:
        """Execute pipeline with passing dynamic parameters to any jobs that
        included in the pipeline.

        :param params: An input parameters that use on pipeline execution.
        :param timeout: A time out in second unit that use for limit time of
            this pipeline execution.
        :rtype: DictData

        ---

        See Also:

            The result of execution process for each jobs and stages on this
        pipeline will keeping in dict which able to catch out with all jobs and
        stages by dot annotation.

            For example, when I want to use the output from previous stage, I
        can access it with syntax:

            ... ${job-name}.stages.${stage-id}.outputs.${key}

        """
        logging.info(f"[CORE]: Start Pipeline {self.name}:{self.gen_run_id()}")
        # NOTE: It should not do anything if it does not have job.
        if not self.jobs:
            logging.warning("[PIPELINE]: This pipeline does not have any jobs")
            return params

        # NOTE: create a job queue that keep the job that want to running after
        #   it dependency condition.
        jq: Queue = Queue()
        for job_id in self.jobs:
            jq.put(job_id)

        ts: float = time.monotonic()
        not_time_out_flag: bool = True
        params: DictData = self.parameterize(params)

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
            #
            if any(params["jobs"].get(need) for need in job.needs):
                jq.put(job_id)

            job.execute(params=params)
            params["jobs"][job_id] = {
                "stages": params.pop("stages", {}),
                "matrix": params.pop("matrix", {}),
            }
        if not not_time_out_flag:
            raise RuntimeError("Execution of pipeline was time out")
        return params
