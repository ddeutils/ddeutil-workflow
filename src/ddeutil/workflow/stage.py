# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import contextlib
import inspect
import logging
import subprocess
import sys
import uuid
from abc import ABC, abstractmethod
from inspect import Parameter
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any, Callable, Optional, Union

import msgspec as spec
from pydantic import BaseModel, Field

from .__types import DictData, DictStr, Re
from .exceptions import TaskException
from .loader import map_params
from .utils import Registry, make_exec, make_registry


class BaseStage(BaseModel, ABC):
    """Base Stage Model that keep only id and name fields for the stage
    metadata. If you want to implement any custom stage, you can use this class
    to parent and implement ``self.execute()`` method only.
    """

    id: Optional[str] = Field(
        default=None,
        description=(
            "The stage ID that use to keep execution output or getting by job "
            "owner."
        ),
    )
    name: str = Field(
        description="The stage name that want to logging when start execution."
    )

    @abstractmethod
    def execute(self, params: DictData) -> DictData:
        """Execute abstraction method that action something by sub-model class.
        This is important method that make this class is able to be the stage.

        :param params: A parameter data that want to use in this execution.
        :rtype: DictData
        """
        raise NotImplementedError("Stage should implement ``execute`` method.")

    def set_outputs(self, rs: DictData, params: DictData) -> DictData:
        """Set an outputs from execution process to an input params.

        :param rs: A result data that want to extract to an output key.
        :param params: A context data that want to add output result.
        :rtype: DictData
        """
        if self.id is None:
            return params

        if "stages" not in params:
            params["stages"] = {}

        params["stages"][self.id] = {"outputs": rs}
        return params


class EmptyStage(BaseStage):
    """Empty stage that do nothing (context equal empty stage) and logging the
    name of stage only to stdout.
    """

    def execute(self, params: DictData) -> DictData:
        """Execution method for the Empty stage that do only logging out to
        stdout.

        :param params: A context data that want to add output result. But this
            stage does not pass any output.
        """
        logging.info(f"[STAGE]: Empty-Execute: {self.name!r}")
        return params


class ShellStage(BaseStage):
    """Shell stage that execute bash script on the current OS. That mean if your
    current OS is Windows, it will running bash in the WSL.
    """

    shell: str = Field(description="A shell statement that want to execute.")
    env: DictStr = Field(
        default_factory=dict,
        description=(
            "An environment variable mapping that want to set before execute "
            "this shell statement."
        ),
    )

    @contextlib.contextmanager
    def __prepare_shell(self):
        """Return context of prepared shell statement that want to execute. This
        step will write the `.sh` file before giving this file name to context.
        After that, it will auto delete this file automatic.
        """
        f_name: str = f"{uuid.uuid4()}.sh"
        f_shebang: str = "bash" if sys.platform.startswith("win") else "sh"
        with open(f"./{f_name}", mode="w", newline="\n") as f:
            f.write(f"#!/bin/{f_shebang}\n")

            for k in self.env:
                f.write(f"{k}='{self.env[k]}';\n")

            # NOTE: make sure that shell script file does not have `\r` char.
            f.write(self.shell.replace("\r\n", "\n"))

        make_exec(f"./{f_name}")

        yield [f_shebang, f_name]

        Path(f_name).unlink()

    def set_outputs(self, rs: CompletedProcess, params: DictData) -> DictData:
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
                "stdout": rs.stdout.rstrip("\n"),
            },
        }
        return params

    def execute(self, params: DictData) -> DictData:
        """Execute the Shell & Powershell statement with the Python build-in
        ``subprocess`` package.
        """
        with self.__prepare_shell() as sh:
            logging.info(f"[STAGE]: Shell-Execute: {sh}")
            rs: CompletedProcess = subprocess.run(
                sh,
                shell=False,
                capture_output=True,
                text=True,
            )
        if rs.returncode > 0:
            err: str = (
                rs.stderr.encode("utf-8").decode("utf-16")
                if "\\x00" in rs.stderr
                else rs.stderr
            )
            logging.error(f"{err}\nRunning Statement:\n---\n{self.shell}")
            raise TaskException(f"{err}\nRunning Statement:\n---\n{self.shell}")
        self.set_outputs(rs, params)
        return params


class PyStage(BaseStage):
    """Python executor stage that running the Python statement that receive
    globals nad additional variables.
    """

    run: str
    vars: DictData = Field(default_factory=dict)

    def get_vars(self, params: DictData) -> DictData:
        """Return variables"""
        rs = self.vars.copy()
        for p, v in self.vars.items():
            rs[p] = map_params(v, params)
        return rs

    def set_outputs(self, rs: DictData, params: DictData) -> DictData:
        """Set an outputs from execution process to an input params.

        :param rs: A result data that want to extract to an output key.
        :param params: A context data that want to add output result.
        :rtype: DictData
        """
        # NOTE: skipping set outputs of stage execution when id does not set.
        if self.id is None:
            return params

        if "stages" not in params:
            params["stages"] = {}

        params["stages"][self.id] = {
            # NOTE: The output will fileter unnecessary keys from ``_locals``.
            "outputs": {k: rs[k] for k in rs if k != "__annotations__"},
        }
        return params

    def execute(self, params: DictData) -> DictData:
        """Execute the Python statement that pass all globals and input params
        to globals argument on ``exec`` build-in function.

        :param params: A parameter that want to pass before run any statement.
        :type params: DictData

        :rtype: DictData
        :returns: A parameters from an input that was mapped output if the stage
            ID was set.
        """
        _globals: DictData = globals() | params | self.get_vars(params)
        _locals: DictData = {}
        try:
            exec(map_params(self.run, params), _globals, _locals)
        except Exception as err:
            raise TaskException(
                f"{err.__class__.__name__}: {err}\nRunning Statement:\n---\n"
                f"{self.run}"
            ) from None

        # NOTE: set outputs from ``_locals`` value from ``exec``.
        self.set_outputs(_locals, params)
        return params | {k: _globals[k] for k in params if k in _globals}


class TaskSearch(spec.Struct, kw_only=True, tag="task"):
    """Task Search Struct that use the `msgspec` for the best performance data
    serialize.
    """

    path: str
    func: str
    tag: str

    def to_dict(self) -> DictData:
        """Return dict data from struct fields."""
        return {f: getattr(self, f) for f in self.__struct_fields__}


class TaskStage(BaseStage):
    """Task executor stage that running the Python function."""

    task: str = Field(description="...")
    args: DictData

    @staticmethod
    def extract_task(task: str) -> Callable[[], Callable[[Any], Any]]:
        """Extract Task string value to task function.

        :param task: A task string value that able to search with Task regex.
        """
        if not (found := Re.RE_TASK_FMT.search(task)):
            raise ValueError("Task does not match with task format regex.")

        # NOTE: Pass the searching task string to path, func, tag.
        task: TaskSearch = TaskSearch(**found.groupdict())

        # NOTE: Registry object should implement on this package only.
        rgt: dict[str, Registry] = make_registry(f"{task.path}")
        if task.func not in rgt:
            raise NotImplementedError(
                f"``REGISTER-MODULES.{task.path}.registries`` does not "
                f"implement registry: {task.func}."
            )

        if task.tag not in rgt[task.func]:
            raise NotImplementedError(
                f"tag: {task.tag} does not found on registry func: "
                f"``REGISTER-MODULES.{task.path}.registries.{task.func}``"
            )
        return rgt[task.func][task.tag]

    def execute(self, params: DictData) -> DictData:
        """Execute the Task that already mark registry.

        :param params: A parameter that want to pass before run any statement.
        :type params: DictData

        :rtype: DictData
        :returns: A parameters from an input that was mapped output if the stage
            ID was set.
        """
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
            rs = task_caller(**map_params(self.args, params))
        except Exception as err:
            raise TaskException(f"{err.__class__.__name__}: {err}") from err
        self.set_outputs(rs, params)
        return params


class TriggerStage(BaseStage):
    """Trigger Stage (Just POC)"""

    trigger: str
    params: DictData = Field(default_factory=dict)

    def execute(self, params: DictData) -> DictData:
        return params


# NOTE: Order of parsing stage data
Stage = Union[
    PyStage,
    ShellStage,
    TaskStage,
    EmptyStage,
    # TriggerStage,
]
