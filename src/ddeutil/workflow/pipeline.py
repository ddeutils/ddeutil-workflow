# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import inspect
import subprocess
from inspect import Parameter
from subprocess import CompletedProcess
from typing import Any, Callable, Optional, Union

from ddeutil.io import Params
from pydantic import BaseModel, Field
from typing_extensions import Self

from .__regex import RegexConf
from .__types import DictData
from .exceptions import PipeArgumentError, PyException, TaskException
from .loader import SimLoad, map_caller


class StageResult(BaseModel): ...


class JobResult(BaseModel): ...


class PipeResult(BaseModel): ...


class EmptyStage(BaseModel):
    """Empty stage that is doing nothing and logging the name of stage only."""

    id: Optional[str] = None
    name: str

    def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        return params


class ShellStage(EmptyStage):
    """Shell statement stage."""

    shell: str
    env: dict[str, str] = Field(default_factory=dict)

    @staticmethod
    def __prepare_shell(shell: str):
        """Prepare shell statement string that include newline"""
        return shell.replace("\n", ";")

    def set_outputs(
        self, rs: CompletedProcess, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Set outputs to params"""
        # NOTE: skipping set outputs of stage execution when id does not set.
        if self.id is None:
            return params

        if "stages" not in params:
            params["stages"] = {}

        params["stages"][self.id] = {
            # NOTE: The output will fileter unnecessary keys from ``_locals``.
            "outputs": {
                "return_code": rs.returncode,
                "stdout": rs.stdout,
                "stderr": rs.stderr,
            },
        }
        return params

    def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute the Shell & Powershell statement with the Python build-in
        ``subprocess`` package.
        """
        rs: CompletedProcess = subprocess.run(
            self.__prepare_shell(self.shell),
            capture_output=True,
            text=True,
            shell=True,
        )
        if rs.returncode > 0:
            print(f"{rs.stderr}\nRunning Statement:\n---\n{self.shell}")
            # FIXME: raise err for this execution.
            # raise ShellException(
            #     f"{rs.stderr}\nRunning Statement:\n---\n"
            #     f"{self.shell}"
            # )
        self.set_outputs(rs, params)
        return params


class PyStage(EmptyStage):
    """Python executor stage that running the Python statement that receive
    globals nad additional variables.
    """

    run: str
    vars: dict[str, Any] = Field(default_factory=dict)

    def get_var(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return variables"""
        rs = self.vars.copy()
        for p, v in self.vars.items():
            rs[p] = map_caller(v, params)
        return rs

    def set_outputs(
        self, lc: dict[str, Any], params: dict[str, Any]
    ) -> dict[str, Any]:
        """Set outputs to params"""
        # NOTE: skipping set outputs of stage execution when id does not set.
        if self.id is None:
            return params

        if "stages" not in params:
            params["stages"] = {}

        params["stages"][self.id] = {
            # NOTE: The output will fileter unnecessary keys from ``_locals``.
            "outputs": {k: lc[k] for k in lc if k != "__annotations__"},
        }
        return params

    def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute the Python statement that pass all globals and input params
        to globals argument on ``exec`` build-in function.

        :param params: A parameter that want to pass before run any statement.
        :type params: dict[str, Any]

        :rtype: dict[str, Any]
        :returns: A parameters from an input that was mapped output if the stage
            ID was set.
        """
        _globals: dict[str, Any] = globals() | params | self.get_var(params)
        _locals: dict[str, Any] = {}
        try:
            exec(map_caller(self.run, params), _globals, _locals)
        except Exception as err:
            raise PyException(
                f"{err.__class__.__name__}: {err}\nRunning Statement:\n---\n"
                f"{self.run}"
            ) from None

        # NOTE: set outputs from ``_locals`` value from ``exec``.
        self.set_outputs(_locals, params)
        return params | {k: _globals[k] for k in params if k in _globals}


class TaskSearch(BaseModel):
    path: str
    func: str
    tag: str


class TaskStage(EmptyStage):
    task: str
    args: dict[str, Any]

    @staticmethod
    def extract_task(task: str) -> Callable[[], Callable[[Any], Any]]:
        """Extract Task string value to task function."""
        if found := RegexConf.RE_TASK_FMT.search(task):
            tasks = TaskSearch(**found.groupdict())

            from ddeutil.core import import_string

            rgt = import_string(f"ddeutil.workflow.{tasks.path}.registries")
            if tasks.func not in rgt:
                raise NotImplementedError(
                    f"ddeutil.workflow.{tasks.path}.registries does not "
                    f"implement registry: {tasks.func}."
                )
            if tasks.tag not in rgt[tasks.func]:
                raise NotImplementedError(
                    f"tag: {tasks.tag} does not found on registry func: "
                    f"ddeutil.workflow.{tasks.path}.registries."
                    f"{tasks.func}"
                )
            return rgt[tasks.func][tasks.tag]
        raise ValueError("Task does not match with task format regex.")

    def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute the Task function."""
        task_caller = self.extract_task(self.task)()
        if not callable(task_caller):
            raise ImportError("Task caller function does not callable.")

        # NOTE: check task caller parameters
        ips = inspect.signature(task_caller)
        if any(
            k not in self.args
            for k in ips.parameters
            if ips.parameters[k].default == Parameter.empty
        ):
            raise ValueError(
                f"necessary parameters, ({', '.join(ips.parameters.keys())}), "
                f"does not set to args"
            )
        try:
            rs = task_caller(**self.args)
        except Exception as err:
            raise TaskException(f"{err.__class__.__name__}: {err}") from err
        return {"output": rs}


class HookStage(EmptyStage):
    hook: str
    args: dict[str, Any]

    def execute(self, params: dict[str, Any]) -> dict[str, Any]: ...


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
    needs: list[str] = Field(default_factory=list)

    def stage(self, stage_id: str) -> Stage:
        for stage in self.stages:
            if stage_id == (stage.id or ""):
                return stage
        raise ValueError(f"Stage ID {stage_id} does not exists")

    def execute(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        for stage in self.stages:
            # NOTE:
            #       I do not use below syntax because `params` dict be the
            #   reference memory pointer and it was changed when I action
            #   anything like update or re-construct this.
            #       ... params |= stage.execute(params=params)
            stage.execute(params=params)
        return params


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
            params=loader.params(),
        )

    def job(self, name: str) -> Job:
        """Return Job model that exists on this pipeline."""
        if name not in self.jobs:
            raise ValueError(f"Job {name} does not exists")
        return self.jobs[name]

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
        check_key = tuple(f"{k!r}" for k in self.params if k not in params)
        if check_key:
            raise ValueError(
                f"Parameters that needed on pipeline does not pass: "
                f"{', '.join(check_key)}."
            )
        params: dict[str, Any] = {
            "params": (
                params
                | {
                    k: self.params[k](params[k])
                    for k in params
                    if k in self.params
                }
            )
        }
        for job_id in self.jobs:
            print(f"[PIPELINE]: Start execute the job: {job_id!r}")
            job = self.jobs[job_id]
            # TODO: Condition on ``needs`` of this job was set. It should create
            #   multithreading process on this step.
            job.execute(params=params)
        return params
