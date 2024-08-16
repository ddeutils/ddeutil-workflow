# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Stage Model that use for getting stage data template from Job Model.
The stage that handle the minimize task that run in some thread (same thread at
its job owner) that mean it is the lowest executor of a pipeline workflow that
can tracking logs.

    The output of stage execution only return 0 status because I do not want to
handle stage error on this stage model. I think stage model should have a lot of
usecase and it does not worry when I want to create a new one.

    Execution --> Ok    --> Result with 0
              --> Error --> Raise StageException
"""
from __future__ import annotations

import contextlib
import inspect
import logging
import os
import subprocess
import sys
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from functools import wraps
from inspect import Parameter
from pathlib import Path
from subprocess import CompletedProcess
from textwrap import dedent
from typing import Callable, Optional, Union

try:
    from typing import ParamSpec
except ImportError:
    from typing_extensions import ParamSpec

from ddeutil.core import str2bool
from pydantic import BaseModel, Field
from pydantic.functional_validators import model_validator

from .__types import DictData, DictStr, Re, TupleStr
from .exceptions import StageException
from .utils import (
    Registry,
    Result,
    TagFunc,
    gen_id,
    make_exec,
    make_registry,
    not_in_template,
    param2template,
)

P = ParamSpec("P")
__all__: TupleStr = (
    "Stage",
    "EmptyStage",
    "BashStage",
    "PyStage",
    "HookStage",
    "TriggerStage",
    "handler_result",
)


def handler_result(message: str | None = None) -> Callable[P, Result]:
    """Decorator function for handler result from the stage execution. This
    function should to use with execution method only.
    """
    message: str = message or ""

    def decorator(func: Callable[P, Result]) -> Callable[P, Result]:

        @wraps(func)
        def wrapped(self: BaseStage, *args, **kwargs):
            try:
                # NOTE: Start calling origin function with a passing args.
                return func(self, *args, **kwargs)
            except Exception as err:
                # NOTE: Start catching error from the stage execution.
                logging.error(
                    f"({self.run_id}) [STAGE]: {err.__class__.__name__}: {err}"
                )
                if isinstance(err, StageException):
                    raise StageException(
                        f"{self.__class__.__name__}: {message}\n\t{err}"
                    ) from err
                raise StageException(
                    f"{self.__class__.__name__}: {message}\n\t"
                    f"{err.__class__.__name__}: {err}"
                ) from None

        return wrapped

    return decorator


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
    run_id: Optional[str] = Field(
        default=None,
        description="A running stage ID.",
        repr=False,
    )

    @model_validator(mode="after")
    def __prepare_running_id(self):
        if self.run_id is None:
            self.run_id = gen_id(self.name + (self.id or ""), unique=True)

        # VALIDATE: Validate stage id and name should not dynamic with params
        #   template. (allow only matrix)
        if not_in_template(self.id) or not_in_template(self.name):
            raise ValueError(
                "Stage name and ID should only template with matrix."
            )

        return self

    @abstractmethod
    def execute(self, params: DictData) -> Result:
        """Execute abstraction method that action something by sub-model class.
        This is important method that make this class is able to be the stage.

        :param params: A parameter data that want to use in this execution.
        :rtype: Result
        """
        raise NotImplementedError("Stage should implement ``execute`` method.")

    def set_outputs(self, output: DictData, to: DictData) -> DictData:
        """Set an outputs from execution process to an input params.

        :param output: A output data that want to extract to an output key.
        :param to: A context data that want to add output result.
        :rtype: DictData
        """
        if not (
            self.id
            or str2bool(os.getenv("WORKFLOW_CORE_DEFAULT_STAGE_ID", "false"))
        ):
            logging.debug(
                f"({self.run_id}) [STAGE]: Output does not set because this "
                f"stage does not set ID or default stage ID config flag not be "
                f"True."
            )
            return to

        # NOTE: Create stages key to receive an output from the stage execution.
        if "stages" not in to:
            to["stages"] = {}

        if self.id:
            _id: str = param2template(self.id, params=to)
        else:
            _id: str = gen_id(param2template(self.name, params=to))

        # NOTE: Set the output to that stage generated ID.
        to["stages"][_id] = {"outputs": output}
        logging.debug(
            f"({self.run_id}) [STAGE]: Set output complete with stage ID: {_id}"
        )
        return to

    def is_skipped(self, params: DictData | None = None) -> bool:
        """Return true if condition of this stage do not correct.

        :param params: A parameters that want to pass to condition template.
        :rtype: bool
        """
        params: DictData = params or {}
        if self.condition is None:
            return False

        _g: DictData = globals() | params
        try:
            rs: bool = eval(param2template(self.condition, params), _g, {})
            if not isinstance(rs, bool):
                raise TypeError("Return type of condition does not be boolean")
            return not rs
        except Exception as err:
            logging.error(f"({self.run_id}) [STAGE]: {err}")
            raise StageException(f"{err.__class__.__name__}: {err}") from err


class EmptyStage(BaseStage):
    """Empty stage that do nothing (context equal empty stage) and logging the
    name of stage only to stdout.

    Data Validate:
        >>> stage = {
        ...     "name": "Empty stage execution",
        ...     "echo": "Hello World",
        ... }
    """

    echo: Optional[str] = Field(
        default=None,
        description="A string statement that want to logging",
    )

    def execute(self, params: DictData) -> Result:
        """Execution method for the Empty stage that do only logging out to
        stdout.

        :param params: A context data that want to add output result. But this
            stage does not pass any output.
        """
        logging.info(
            f"({self.run_id}) [STAGE]: Empty-Execute: {self.name!r}: "
            f"( {param2template(self.echo, params=params) or '...'} )"
        )
        return Result(status=0, context={})


class BashStage(BaseStage):
    """Bash execution stage that execute bash script on the current OS.
    That mean if your current OS is Windows, it will running bash in the WSL.

        I get some limitation when I run shell statement with the built-in
    supprocess package. It does not good enough to use multiline statement.
    Thus, I add writing ``.sh`` file before execution process for fix this
    issue.

    Data Validate:
        >>> stage = {
        ...     "name": "Shell stage execution",
        ...     "bash": 'echo "Hello $FOO"',
        ...     "env": {
        ...         "FOO": "BAR",
        ...     },
        ... }
    """

    bash: str = Field(description="A bash statement that want to execute.")
    env: DictStr = Field(
        default_factory=dict,
        description=(
            "An environment variable mapping that want to set before execute "
            "this shell statement."
        ),
    )

    @contextlib.contextmanager
    def __prepare_bash(self, bash: str, env: DictStr) -> Iterator[TupleStr]:
        """Return context of prepared bash statement that want to execute. This
        step will write the `.sh` file before giving this file name to context.
        After that, it will auto delete this file automatic.
        """
        f_name: str = f"{uuid.uuid4()}.sh"
        f_shebang: str = "bash" if sys.platform.startswith("win") else "sh"
        with open(f"./{f_name}", mode="w", newline="\n") as f:
            # NOTE: write header of `.sh` file
            f.write(f"#!/bin/{f_shebang}\n\n")

            # NOTE: add setting environment variable before bash skip statement.
            f.writelines([f"{k}='{env[k]}';\n" for k in env])

            # NOTE: make sure that shell script file does not have `\r` char.
            f.write("\n" + bash.replace("\r\n", "\n"))

        # NOTE: Make this .sh file able to executable.
        make_exec(f"./{f_name}")

        logging.debug(
            f"({self.run_id}) [STAGE]: Start create `.sh` file and running a "
            f"bash statement."
        )

        yield [f_shebang, f_name]

        Path(f"./{f_name}").unlink()

    @handler_result()
    def execute(self, params: DictData) -> Result:
        """Execute the Bash statement with the Python build-in ``subprocess``
        package.

        :param params: A parameter data that want to use in this execution.
        :rtype: Result
        """
        bash: str = param2template(dedent(self.bash), params)
        with self.__prepare_bash(
            bash=bash, env=param2template(self.env, params)
        ) as sh:
            logging.info(f"({self.run_id}) [STAGE]: Shell-Execute: {sh}")
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
            ).removesuffix("\n")
            raise StageException(
                f"Subprocess: {err}\nRunning Statement:\n---\n"
                f"```bash\n{bash}\n```"
            )
        return Result(
            status=0,
            context={
                "return_code": rs.returncode,
                "stdout": rs.stdout.rstrip("\n"),
                "stderr": rs.stderr.rstrip("\n"),
            },
        )


class PyStage(BaseStage):
    """Python executor stage that running the Python statement that receive
    globals nad additional variables.

    Data Validate:
        >>> stage = {
        ...     "name": "Python stage execution",
        ...     "run": 'print("Hello {x}")',
        ...     "vars": {
        ...         "x": "BAR",
        ...     },
        ... }
    """

    run: str = Field(
        description="A Python string statement that want to run with exec.",
    )
    vars: DictData = Field(
        default_factory=dict,
        description=(
            "A mapping to variable that want to pass to globals in exec."
        ),
    )

    def set_outputs(self, output: DictData, to: DictData) -> DictData:
        """Set an outputs from the Python execution process to an input params.

        :param output: A output data that want to extract to an output key.
        :param to: A context data that want to add output result.
        :rtype: DictData
        """
        # NOTE: The output will fileter unnecessary keys from locals.
        _locals: DictData = output["locals"]
        super().set_outputs(
            {k: _locals[k] for k in _locals if k != "__annotations__"}, to=to
        )

        # NOTE:
        #   Override value that changing from the globals that pass via exec.
        _globals: DictData = output["globals"]
        to.update({k: _globals[k] for k in to if k in _globals})
        return to

    @handler_result()
    def execute(self, params: DictData) -> Result:
        """Execute the Python statement that pass all globals and input params
        to globals argument on ``exec`` build-in function.

        :param params: A parameter that want to pass before run any statement.
        :rtype: Result
        """
        # NOTE: create custom globals value that will pass to exec function.
        _globals: DictData = (
            globals() | params | param2template(self.vars, params)
        )
        _locals: DictData = {}
        run: str = param2template(dedent(self.run), params)
        logging.info(f"({self.run_id}) [STAGE]: Py-Execute: {uuid.uuid4()}")
        exec(run, _globals, _locals)
        return Result(
            status=0, context={"locals": _locals, "globals": _globals}
        )


@dataclass
class HookSearch:
    """Hook Search dataclass."""

    path: str
    func: str
    tag: str


def extract_hook(hook: str) -> Callable[[], TagFunc]:
    """Extract Hook string value to hook function.

    :param hook: A hook value that able to match with Task regex.
    :rtype: Callable[[], TagFunc]
    """
    if not (found := Re.RE_TASK_FMT.search(hook)):
        raise ValueError(
            f"Hook {hook!r} does not match with hook format regex."
        )

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
        ...     "uses": "tasks/function-name@tag-name",
        ...     "args": {
        ...         "FOO": "BAR",
        ...     },
        ... }
    """

    uses: str = Field(
        description="A pointer that want to load function from registry.",
    )
    args: DictData = Field(
        default_factory=dict,
        description="An arguments that want to pass to the hook function.",
        alias="with",
    )

    @handler_result()
    def execute(self, params: DictData) -> Result:
        """Execute the Hook function that already in the hook registry.

        :param params: A parameter that want to pass before run any statement.
        :type params: DictData
        :rtype: Result
        """
        t_func_hook: str = param2template(self.uses, params)
        t_func: TagFunc = extract_hook(t_func_hook)()

        # VALIDATE: check input task caller parameters that exists before
        #   calling.
        args: DictData = param2template(self.args, params)
        ips = inspect.signature(t_func)
        if any(
            (k.removeprefix("_") not in args and k not in args)
            for k in ips.parameters
            if ips.parameters[k].default == Parameter.empty
        ):
            raise ValueError(
                f"Necessary params, ({', '.join(ips.parameters.keys())}, ), "
                f"does not set to args"
            )
        # NOTE: add '_' prefix if it want to use.
        for k in ips.parameters:
            if k.removeprefix("_") in args:
                args[k] = args.pop(k.removeprefix("_"))

        logging.info(
            f"({self.run_id}) [STAGE]: Hook-Execute: "
            f"{t_func.name}@{t_func.tag}"
        )
        rs: DictData = t_func(**param2template(args, params))

        # VALIDATE:
        #   Check the result type from hook function, it should be dict.
        if not isinstance(rs, dict):
            raise TypeError(
                f"Return type: '{t_func.name}@{t_func.tag}' does not serialize "
                f"to result model, you change return type to `dict`."
            )
        return Result(status=0, context=rs)


class TriggerStage(BaseStage):
    """Trigger Pipeline execution stage that execute another pipeline object.

    Data Validate:
        >>> stage = {
        ...     "name": "Trigger pipeline stage execution",
        ...     "trigger": 'pipeline-name-for-loader',
        ...     "params": {
        ...         "run-date": "2024-08-01",
        ...         "source": "src",
        ...     },
        ... }
    """

    trigger: str = Field(description="A trigger pipeline name.")
    params: DictData = Field(
        default_factory=dict,
        description="A parameter that want to pass to pipeline execution.",
    )

    @handler_result("Raise from trigger pipeline")
    def execute(self, params: DictData) -> Result:
        """Trigger pipeline execution.

        :param params: A parameter data that want to use in this execution.
        :rtype: Result
        """
        from .pipeline import Pipeline

        # NOTE: Loading pipeline object from trigger name.
        _trigger: str = param2template(self.trigger, params=params)
        pipe: Pipeline = Pipeline.from_loader(name=_trigger, externals={})

        # NOTE: Set running pipeline ID from running stage ID.
        pipe.run_id = self.run_id

        return pipe.execute(params=param2template(self.params, params))


# NOTE: Order of parsing stage data
Stage = Union[
    PyStage,
    BashStage,
    HookStage,
    TriggerStage,
    EmptyStage,
]
