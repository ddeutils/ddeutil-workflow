# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import itertools
import logging
import time
from queue import Queue
from typing import Optional, Union

from pydantic import BaseModel, Field
from pydantic.functional_validators import model_validator
from typing_extensions import Self

from .__types import DictData, DictStr
from .loader import Loader
from .on import On
from .stage import Stage
from .utils import Params


class Strategy(BaseModel):
    """Strategy Model that will combine a matrix together for running the
    special job.

    Examples:
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
    exclude: list[dict[str, Union[str, int]]] = Field(default_factory=list)

    @model_validator(mode="before")
    def __prepare_keys(cls, values: DictData) -> DictData:
        if "max-parallel" in values:
            values["max_parallel"] = values.pop("max-parallel")
        if "fail-fast" in values:
            values["fail_fast"] = values.pop("fail-fast")
        return values


class Job(BaseModel):
    """Job Model that is able to call a group of stages."""

    runs_on: Optional[str] = Field(default=None)
    stages: list[Stage] = Field(default_factory=list)
    needs: list[str] = Field(
        default_factory=list,
        description="A list of the job ID that want to run before this job.",
    )
    strategy: Strategy = Field(default_factory=Strategy)

    @model_validator(mode="before")
    def __prepare_keys(cls, values: DictData) -> DictData:
        if "runs-on" in values:
            values["runs_on"] = values.pop("runs-on")
        return values

    def stage(self, stage_id: str) -> Stage:
        """Return stage model that match with an input stage ID."""
        for stage in self.stages:
            if stage_id == (stage.id or ""):
                return stage
        raise ValueError(f"Stage ID {stage_id} does not exists")

    def make_strategy(self) -> list[DictStr]:
        """Return List of combination of matrix values that already filter with
        exclude and add include values.
        """
        if not (mt := self.strategy.matrix):
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
                for exclude in self.strategy.exclude
            ):
                continue
            final.append(r)

        if not final:
            return [{}]

        for include in self.strategy.include:
            if include.keys() != final[0].keys():
                raise ValueError("Include should have the keys equal to matrix")
            if any(all(include[k] == v for k, v in f.items()) for f in final):
                continue
            final.append(include)
        return final

    def execute(self, params: DictData | None = None) -> DictData:
        """Execute job with passing dynamic parameters from the pipeline."""
        for strategy in self.make_strategy():
            params.update({"matrix": strategy})

            # IMPORTANT: The stage execution only run sequentially one-by-one.
            for stage in self.stages:
                logging.info(
                    f"[JOB]: Start execute the stage: "
                    f"{(stage.id if stage.id else stage.name)!r}"
                )

                # NOTE:
                #       I do not use below syntax because `params` dict be the
                #   reference memory pointer and it was changed when I action
                #   anything like update or re-construct this.
                #       ... params |= stage.execute(params=params)
                stage.execute(params=params)
        # TODO: We should not return matrix key to outside
        return params


class Pipeline(BaseModel):
    """Pipeline Model this is the main feature of this project because it use to
    be workflow data for running everywhere that you want. It use lightweight
    coding line to execute it.
    """

    desc: Optional[str] = Field(default=None)
    params: dict[str, Params] = Field(default_factory=dict)
    on: list[On] = Field(
        default_factory=list,
        description="A list of On instance for this pipeline schedule.",
    )
    jobs: dict[str, Job] = Field(
        description="A mapping of job ID and job model that already loaded.",
    )

    @classmethod
    def from_loader(
        cls,
        name: str,
        externals: DictData | None = None,
    ) -> Self:
        """Create Pipeline instance from the Loader object."""
        loader: Loader = Loader(name, externals=(externals or {}))
        loader_data: DictData = loader.data.copy()
        if "jobs" not in loader_data:
            raise ValueError("Config does not set ``jobs`` value")
        if on := loader_data.pop("on", []):
            if isinstance(on, str):
                on = [on]
            if any(not isinstance(i, (dict, str)) for i in on):
                raise TypeError("The ``on`` key should be list of str or dict")
            loader_data["on"] = [
                (
                    Loader(n, externals=(externals or {})).data
                    if isinstance(n, str)
                    else n
                )
                for n in on
            ]
        return cls.model_validate(loader_data)

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

    def execute(
        self,
        params: DictData | None = None,
        time_out: int = 60,
    ) -> DictData:
        """Execute pipeline with passing dynamic parameters to any jobs that
        included in the pipeline.

        :param params: An input parameters that use on pipeline execution.
        :param time_out: A time out in second unit that use for limit time of
            this pipeline execution.

        ---

        See Also:

            The result of execution process for each jobs and stages on this
        pipeline will keeping in dict which able to catch out with all jobs and
        stages by dot annotation.

            For example, when I want to use the output from previous stage, I
        can access it with syntax:

            ... "<job-name>.stages.<stage-id>.outputs.<key>"

        """
        params: DictData = params or {}
        if check_key := tuple(f"{k!r}" for k in self.params if k not in params):
            raise ValueError(
                f"Parameters that needed on pipeline does not pass: "
                f"{', '.join(check_key)}."
            )

        if any(p not in params for p in self.params if self.params[p].required):
            raise ValueError("Required parameter does not pass")

        # NOTE: mapping type of param before adding it to params variable.
        params: DictData = {
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

        # NOTE: create a job queue that keep the job that want to running after
        #   it dependency condition.
        jq = Queue()
        for job_id in self.jobs:
            jq.put(job_id)

        ts: float = time.monotonic()
        not_time_out_flag = True

        # IMPORTANT: The job execution can run parallel and waiting by needed.
        while not jq.empty() and (
            not_time_out_flag := ((time.monotonic() - ts) < time_out)
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
