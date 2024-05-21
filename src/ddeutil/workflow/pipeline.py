# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import subprocess
from subprocess import CompletedProcess
from typing import Any, Optional, Union

from ddeutil.io import Params
from pydantic import BaseModel, Field
from typing_extensions import Self

from .__types import DictData
from .exceptions import PipeArgumentError
from .loader import SimLoad


class PyException(Exception): ...


class ShellException(Exception): ...


class EmptyStage(BaseModel):
    """Empty stage that is doing nothing and logging the name of stage only."""

    id: Optional[str] = None
    name: str

    def execute(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return params


class ShellStage(EmptyStage):
    """Shell statement stage."""

    shell: str

    def execute(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute the Shell & Powershell statement with the Python build-in
        ``subprocess`` package.
        """
        try:
            rs: CompletedProcess = subprocess.run(
                self.shell,
                capture_output=True,
                text=True,
                shell=True,
            )
            __rs = {(self.id or self.name): rs.stdout}
        except Exception as err:
            raise ShellException(
                f"{err.__class__.__name__}: {err}\nRunning Statement:\n"
                f"{self.shell}"
            ) from None
        if self.id:
            if "stages" not in params:
                params["stages"] = {}
            params["stages"][self.id] = __rs
        return params


class PyStage(EmptyStage):
    """Python statement stage."""

    run: str

    def execute(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute the Python statement that pass all globals and input params
        to globals argument on ``exec`` build-in function.

        :param params: A parameter that want to pass before run any statement.
        :type params: dict[str, Any]
        """
        _globals: dict[str, Any] = globals() | (params or {})
        try:
            exec(self.run, _globals)
        except Exception as err:
            raise PyException(
                f"{err.__class__.__name__}: {err}\nRunning Statement:\n"
                f"{self.run}"
            ) from None
        if self.id:
            if "stages" not in params:
                params["stages"] = {}
            params["stages"][self.id] = {}
        return params | {k: _globals[k] for k in params if k in _globals}


class TaskStage(EmptyStage):
    uses: str


class HookStage(EmptyStage):
    hook: str


# NOTE: Order of parsing stage data
Stage = Union[
    PyStage,
    ShellStage,
    TaskStage,
    HookStage,
    EmptyStage,
]


class Job(BaseModel):
    stages: list[Stage] = Field(default_factory=list)

    def execute(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        for stage in self.stages:
            params |= stage.execute(params=params)
        return params

    def stage(self, stage_id: str) -> Stage:
        for stage in self.stages:
            if stage_id == (stage.id or ""):
                return stage
        raise ValueError(f"Stage ID {stage_id} does not exists")


class Strategy(BaseModel):
    matrix: list[str]
    include: list[str]
    exclude: list[str]


class JobStrategy(Job):
    """Strategy job"""

    strategy: Strategy


class Pipeline(BaseModel):
    """Pipeline Model"""

    params: dict[str, Any] = Field(default_factory=dict)
    jobs: dict[str, Job]

    @classmethod
    def from_loader(
        cls,
        name: str,
        params: Params,
        externals: DictData,
    ) -> Self:
        loader: SimLoad = SimLoad(name, params=params, externals=externals)
        if "jobs" not in loader.data:
            raise PipeArgumentError("jobs", "Config does not set ``jobs``")
        return cls(
            jobs=loader.data["jobs"],
            params=loader.data.get("params", {}),
        )

    def execute(self, params: dict[str, Any] | None = None):
        """Execute pipeline with passing dynamic parameters.

        See Also:

            The result of execution process for each jobs and stages on this
        pipeline will keeping in dict which able to catch out with all jobs and
        stages by dot annotation.

            For example, when I want to use the output from previous stage, I
        can access it with syntax:

            ... "<job-name>.stages.<stage-id>.outputs.<key>"

        """
        params: dict[str, Any] = params or {}
        check_key = tuple(k for k in self.params if k not in params)
        if check_key:
            raise ValueError(
                f"Parameters that needed on pipeline does not pass: "
                f"{', '.join(check_key)}."
            )
        return params

    def job(self, name: str) -> Job:
        """Return Job model that exists on this pipeline."""
        if name not in self.jobs:
            raise ValueError(f"Job {name} does not exists")
        return self.jobs[name]
