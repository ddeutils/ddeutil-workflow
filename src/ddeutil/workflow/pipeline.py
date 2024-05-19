# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from typing import Any, Union

from ddeutil.io import Params
from pydantic import BaseModel, Field
from typing_extensions import Self

from .__types import DictData
from .exceptions import PipeArgumentError
from .loader import SimLoad


class EmptyStage(BaseModel):
    name: str


class PyStage(EmptyStage):
    run: str


class TaskStage(EmptyStage):
    uses: str


class HookStage(EmptyStage):
    hook: str


Stage = Union[EmptyStage, PyStage, TaskStage, HookStage]


class Job(BaseModel):
    stages: list[Stage] = Field(default_factory=list)


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
        """Execute pipeline with passing dynamic parameters."""
        params: dict[str, Any] = params or {}
        check_key = tuple(k for k in self.params if k not in params)
        if check_key:
            raise ValueError(
                f"Parameters that needed on pipeline does not pass: "
                f"{', '.join(check_key)}."
            )
        return params

    def job(self, name: str) -> Job:
        if name not in self.jobs:
            raise ValueError(f"Job {name} does not exists")
        return self.jobs[name]
