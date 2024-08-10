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
from collections.abc import Iterator
from inspect import Parameter
from pathlib import Path
from subprocess import CompletedProcess
from typing import Callable, Optional, Union

import msgspec as spec
from pydantic import BaseModel, Field

from .__types import DictData, DictStr, Re, TupleStr
from .exceptions import StageException
from .utils import Registry, TagFunc, make_exec, make_registry, param2template


class BaseStage(BaseModel, ABC):
    """Base Stage Model that keep only id and name fields for the stage
    metadata. If you want to implement any custom stage, you can use this class
    to parent and implement ``self.execute()`` method only.
    """

    id: Optional[str] = Field(
        default=None,
        description=(
            "A stage ID that use to keep execution output or getting by job "
            "owner."
        ),
    )
    name: str = Field(
        description="A stage name that want to logging when start execution."
    )
    condition: Optional[str] = Field(
        default=None,
        alias="if",
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

    def is_skip(self, params: DictData | None = None) -> bool:
        """Return true if condition of this stage do not correct."""
        params: DictData = params or {}
        if self.condition is None:
            return False

        _g: DictData = globals() | params
        try:
            rs: bool = eval(
                param2template(self.condition, params, repr_flag=True), _g, {}
            )
            if not isinstance(rs, bool):
                raise TypeError("Return type of condition does not be boolean")
            return not rs
        except Exception as err:
            logging.error(str(err))
            raise StageException(str(err)) from err


class EmptyStage(BaseStage):
    """Empty stage that do nothing (context equal empty stage) and logging the
    name of stage only to stdout.
    """

    echo: Optional[str] = Field(
        default=None,
        description="A string statement that want to logging",
    )

    def execute(self, params: DictData) -> DictData:
        """Execution method for the Empty stage that do only logging out to
        stdout.

        :param params: A context data that want to add output result. But this
            stage does not pass any output.
        """
        logging.info(f"[STAGE]: Empty-Execute: {self.name!r}")
        return params


class ShellStage(BaseStage):
    """Shell execution stage that execute bash script on the current OS.
    That mean if your current OS is Windows, it will running bash in the WSL.

        I get some limitation when I run shell statement with the built-in
    supprocess package. It does not good enough to use multiline statement.
    Thus, I add writing ``.sh`` file before execution process for fix this
    issue.

    Data Validate:
        >>> stage = {
        ...     "name": "Shell stage execution",
        ...     "shell": 'echo "Hello $FOO"',
        ...     "env": {
        ...         "FOO": "BAR",
        ...     },
        ... }
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
    def __prepare_shell(self, shell: str, env: DictStr) -> Iterator[TupleStr]:
        """Return context of prepared shell statement that want to execute. This
        step will write the `.sh` file before giving this file name to context.
        After that, it will auto delete this file automatic.
        """
        f_name: str = f"{uuid.uuid4()}.sh"
        f_shebang: str = "bash" if sys.platform.startswith("win") else "sh"
        with open(f"./{f_name}", mode="w", newline="\n") as f:
            f.write(f"#!/bin/{f_shebang}\n")

            # NOTE: add setting environment variable before bash skip statement.
            f.writelines([f"{k}='{env[k]}';\n" for k in env])

            # NOTE: make sure that shell script file does not have `\r` char.
            f.write(shell.replace("\r\n", "\n"))

        make_exec(f"./{f_name}")

        yield [f_shebang, f_name]

        Path(f"./{f_name}").unlink()

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

        :param params: A parameter data that want to use in this execution.
        :rtype: DictData
        """
        shell: str = param2template(self.shell, params)
        with self.__prepare_shell(
            shell=shell, env=param2template(self.env, params)
        ) as sh:
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
            logging.error(f"{err}\nRunning Statement:\n---\n{shell}")
            raise StageException(f"{err}\nRunning Statement:\n---\n{shell}")
        self.set_outputs(rs, params)
        return params


class PyStage(BaseStage):
    """Python executor stage that running the Python statement that receive
    globals nad additional variables.
    """

    run: str = Field(description="A Python statement that want to run.")
    vars: DictData = Field(default_factory=dict)

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
        _globals: DictData = (
            globals() | params | param2template(self.vars, params)
        )
        _locals: DictData = {}
        try:
            logging.info(f"[STAGE]: Py-Execute: {uuid.uuid4()}")
            exec(param2template(self.run, params), _globals, _locals)
        except Exception as err:
            raise StageException(
                f"{err.__class__.__name__}: {err}\nRunning Statement:\n---\n"
                f"{self.run}"
            ) from None

        # NOTE: set outputs from ``_locals`` value from ``exec``.
        self.set_outputs(_locals, params)
        return params | {k: _globals[k] for k in params if k in _globals}


class HookSearch(spec.Struct, kw_only=True, tag="task"):
    """Hook Search Struct that use the `msgspec` for the best performance data
    serialize.
    """

    path: str
    func: str
    tag: str

    def to_dict(self) -> DictData:
        """Return dict data from struct fields."""
        return {f: getattr(self, f) for f in self.__struct_fields__}


class HookStage(BaseStage):
    """Hook executor that hook the Python function from registry with tag
    decorator function in ``utils`` module and run it with input arguments.

        This stage is different with PyStage because the PyStage is just calling
    a Python statement with the ``eval`` and pass that locale before eval that
    statement. So, you can create your function complexly that you can for your
    propose to invoked by this stage object.

    Data Validate:
        >>> stage = {
        ...     "name": "Task stage execution",
        ...     "task": "tasks/function-name@tag-name",
        ...     "args": {
        ...         "FOO": "BAR",
        ...     },
        ... }
    """

    uses: str = Field(
        description="A pointer that want to load function from registry",
    )
    args: DictData = Field(alias="with")

    @staticmethod
    def extract_hook(hook: str) -> Callable[[], TagFunc]:
        """Extract Hook string value to hook function.

        :param hook: A hook string value that able to search with Task regex.
        """
        if not (found := Re.RE_TASK_FMT.search(hook)):
            raise ValueError("Task does not match with task format regex.")

        # NOTE: Pass the searching hook string to `path`, `func`, and `tag`.
        hook: HookSearch = HookSearch(**found.groupdict())

        # NOTE: Registry object should implement on this package only.
        rgt: dict[str, Registry] = make_registry(f"{hook.path}")
        if hook.func not in rgt:
            raise NotImplementedError(
                f"``REGISTER-MODULES.{hook.path}.registries`` does not "
                f"implement registry: {hook.func!r}."
            )

        if hook.tag not in rgt[hook.func]:
            raise NotImplementedError(
                f"tag: {hook.tag!r} does not found on registry func: "
                f"``REGISTER-MODULES.{hook.path}.registries.{hook.func}``"
            )
        return rgt[hook.func][hook.tag]

    def execute(self, params: DictData) -> DictData:
        """Execute the Task function that already mark registry.

        :param params: A parameter that want to pass before run any statement.
        :type params: DictData

        :rtype: DictData
        :returns: A parameters from an input that was mapped output if the stage
            ID was set.
        """
        t_func: TagFunc = self.extract_hook(param2template(self.uses, params))()
        if not callable(t_func):
            raise ImportError("Hook caller function does not callable.")

        # VALIDATE: check input task caller parameters that exists before
        #   calling.
        args: DictData = param2template(self.args, params)
        ips = inspect.signature(t_func)
        if any(
            k not in args
            for k in ips.parameters
            if ips.parameters[k].default == Parameter.empty
        ):
            raise ValueError(
                f"Necessary params, ({', '.join(ips.parameters.keys())}), "
                f"does not set to args"
            )

        try:
            logging.info(f"[STAGE]: Hook-Execute: {t_func.name}@{t_func.tag}")
            rs: DictData = t_func(**param2template(args, params))
        except Exception as err:
            raise StageException(f"{err.__class__.__name__}: {err}") from err
        self.set_outputs(rs, params)
        return params


class TriggerStage(BaseStage):
    """Trigger Pipeline execution stage that execute another pipeline object."""

    trigger: str = Field(description="A trigger pipeline name.")
    params: DictData = Field(default_factory=dict)

    def execute(self, params: DictData) -> DictData:
        """Trigger execution.

        :param params: A parameter data that want to use in this execution.
        :rtype: DictData
        """
        from .pipeline import Pipeline

        pipe: Pipeline = Pipeline.from_loader(name=self.trigger, externals={})
        pipe.execute(params=self.params)
        return params


# NOTE: Order of parsing stage data
Stage = Union[
    PyStage,
    ShellStage,
    HookStage,
    TriggerStage,
    EmptyStage,
]
