# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Stages module include all stage model that use be the minimum execution layer
of this workflow engine. The stage handle the minimize task that run in some
thread (same thread at its job owner) that mean it is the lowest executor that
you can track logs.

    The output of stage execution only return SUCCESS or CANCEL status because
I do not want to handle stage error on this stage execution. I think stage model
have a lot of use-case, and it should does not worry about it error output.

    So, I will create `handler_execute` for any exception class that raise from
the stage execution method.

    Execution   --> Ok      ---( handler )--> Result with `SUCCESS` or `CANCEL`

                --> Error   ┬--( handler )-> Result with `FAILED` (Set `raise_error` flag)
                            |
                            ╰--( handler )-> Raise StageException(...)

    On the context I/O that pass to a stage object at execute process. The
execute method receives a `params={"params": {...}}` value for passing template
searching.
"""
from __future__ import annotations

import asyncio
import contextlib
import copy
import inspect
import json
import subprocess
import sys
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from concurrent.futures import (
    FIRST_EXCEPTION,
    Future,
    ThreadPoolExecutor,
    as_completed,
    wait,
)
from datetime import datetime
from inspect import Parameter, isclass, isfunction, ismodule
from pathlib import Path
from subprocess import CompletedProcess
from textwrap import dedent
from threading import Event
from typing import Annotated, Any, Optional, TypeVar, Union, get_type_hints

from pydantic import BaseModel, Field
from pydantic.functional_validators import model_validator
from typing_extensions import Self

from .__types import DictData, DictStr, StrOrInt, TupleStr
from .conf import dynamic
from .exceptions import StageException, to_dict
from .result import CANCEL, FAILED, SUCCESS, WAIT, Result, Status
from .reusables import TagFunc, extract_call, not_in_template, param2template
from .utils import (
    delay,
    filter_func,
    gen_id,
    make_exec,
)

T = TypeVar("T")


class BaseStage(BaseModel, ABC):
    """Base Stage Model that keep only necessary fields like `id`, `name` or
    `condition` for the stage metadata. If you want to implement any custom
    stage, you can inherit this class and implement `self.execute()` method
    only.

        This class is the abstraction class for any inherit stage model that
    want to implement on this workflow package.
    """

    extras: DictData = Field(
        default_factory=dict,
        description="An extra parameter that override core config values.",
    )
    id: Optional[str] = Field(
        default=None,
        description=(
            "A stage ID that use to keep execution output or getting by job "
            "owner."
        ),
    )
    name: str = Field(
        description="A stage name that want to logging when start execution.",
    )
    condition: Optional[str] = Field(
        default=None,
        description=(
            "A stage condition statement to allow stage executable. This field "
            "alise with `if` field."
        ),
        alias="if",
    )

    @property
    def iden(self) -> str:
        """Return this stage identity that return the `id` field first and if
        this `id` field does not set, it will use the `name` field instead.

        :rtype: str
        """
        return self.id or self.name

    @model_validator(mode="after")
    def __prepare_running_id(self) -> Self:
        """Prepare stage running ID that use default value of field and this
        method will validate name and id fields should not contain any template
        parameter (exclude matrix template).

        :raise ValueError: When the ID and name fields include matrix parameter
            template with the 'matrix.' string value.

        :rtype: Self
        """

        # VALIDATE: Validate stage id and name should not dynamic with params
        #   template. (allow only matrix)
        if not_in_template(self.id) or not_in_template(self.name):
            raise ValueError(
                "Stage name and ID should only template with 'matrix.'"
            )

        return self

    @abstractmethod
    def execute(
        self,
        params: DictData,
        *,
        result: Result | None = None,
        event: Event | None = None,
    ) -> Result:
        """Execute abstraction method that action something by sub-model class.
        This is important method that make this class is able to be the stage.

        :param params: (DictData) A parameter data that want to use in this
            execution.
        :param result: (Result) A result object for keeping context and status
            data.
        :param event: (Event) An event manager that use to track parent execute
            was not force stopped.

        :rtype: Result
        """
        raise NotImplementedError("Stage should implement `execute` method.")

    def handler_execute(
        self,
        params: DictData,
        *,
        run_id: str | None = None,
        parent_run_id: str | None = None,
        result: Result | None = None,
        event: Event | None = None,
        raise_error: bool | None = None,
    ) -> Result | DictData:
        """Handler stage execution result from the stage `execute` method.

            This stage exception handler still use ok-error concept, but it
        allows you force catching an output result with error message by
        specific environment variable,`WORKFLOW_CORE_STAGE_RAISE_ERROR`.

            Execution   --> Ok      --> Result
                                        |-status: SUCCESS
                                        ╰-context:
                                            ╰-outputs: ...

                        --> Error   --> Result (if `raise_error` was set)
                                        |-status: FAILED
                                        ╰-errors:
                                            |-class: ...
                                            |-name: ...
                                            ╰-message: ...

                        --> Error   --> Raise StageException(...)

            On the last step, it will set the running ID on a return result
        object from the current stage ID before release the final result.

        :param params: (DictData) A parameter data.
        :param run_id: (str) A running stage ID.
        :param parent_run_id: (str) A parent running ID.
        :param result: (Result) A result object for keeping context and status
            data before execution.
        :param event: (Event) An event manager that pass to the stage execution.
        :param raise_error: (bool) A flag that all this method raise error

        :raise StageException: If the raise_error was set and the execution
            raise any error.

        :rtype: Result
        """
        result: Result = Result.construct_with_rs_or_id(
            result,
            run_id=run_id,
            parent_run_id=parent_run_id,
            id_logic=self.iden,
            extras=self.extras,
        )
        try:
            return self.execute(params, result=result, event=event)
        except Exception as e:
            e_name: str = e.__class__.__name__
            result.trace.error(f"[STAGE]: Error Handler:||{e_name}:||{e}")
            if dynamic("stage_raise_error", f=raise_error, extras=self.extras):
                if isinstance(e, StageException):
                    raise
                raise StageException(
                    f"{self.__class__.__name__}: {e_name}: {e}"
                ) from e
            return result.catch(status=FAILED, context={"errors": to_dict(e)})

    def set_outputs(self, output: DictData, to: DictData) -> DictData:
        """Set an outputs from execution result context to the received context
        with a `to` input parameter. The result context from stage execution
        will be set with `outputs` key in this stage ID key.

            For example of setting output method, If you receive execute output
        and want to set on the `to` like;

            ... (i)   output: {'foo': 'bar', 'skipped': True}
            ... (ii)  to: {'stages': {}}

            The received context in the `to` argument will be;

            ... (iii) to: {
                        'stages': {
                            '<stage-id>': {
                                'outputs': {'foo': 'bar'},
                                'skipped': True,
                            }
                        }
                    }

            The keys that will set to the received context is `outputs`,
        `errors`, and `skipped` keys. The `errors` and `skipped` keys will
        extract from the result context if it exists. If it does not found, it
        will not set on the received context.

        Important:

            This method is use for reconstruct the result context and transfer
        to the `to` argument. The result context was soft copied before set
        output step.

        :param output: (DictData) A result data context that want to extract
            and transfer to the `outputs` key in receive context.
        :param to: (DictData) A received context data.

        :rtype: DictData
        """
        if "stages" not in to:
            to["stages"] = {}

        if self.id is None and not dynamic(
            "stage_default_id", extras=self.extras
        ):
            return to

        _id: str = (
            param2template(self.id, params=to, extras=self.extras)
            if self.id
            else gen_id(
                param2template(self.name, params=to, extras=self.extras)
            )
        )
        output: DictData = output.copy()
        errors: DictData = (
            {"errors": output.pop("errors", {})} if "errors" in output else {}
        )
        skipping: dict[str, bool] = (
            {"skipped": output.pop("skipped", False)}
            if "skipped" in output
            else {}
        )
        to["stages"][_id] = {
            "outputs": copy.deepcopy(output),
            **skipping,
            **errors,
        }
        return to

    def get_outputs(self, output: DictData) -> DictData:
        """Get the outputs from stages data. It will get this stage ID from
        the stage outputs mapping.

        :param output: (DictData) A stage output context that want to get this
            stage ID `outputs` key.

        :rtype: DictData
        """
        if self.id is None and not dynamic(
            "stage_default_id", extras=self.extras
        ):
            return {}

        _id: str = (
            param2template(self.id, params=output, extras=self.extras)
            if self.id
            else gen_id(
                param2template(self.name, params=output, extras=self.extras)
            )
        )
        return output.get("stages", {}).get(_id, {}).get("outputs", {})

    def is_skipped(self, params: DictData) -> bool:
        """Return true if condition of this stage do not correct. This process
        use build-in eval function to execute the if-condition.

        :param params: (DictData) A parameters that want to pass to condition
            template.

        :raise StageException: When it has any error raise from the eval
            condition statement.
        :raise StageException: When return type of the eval condition statement
            does not return with boolean type.

        :rtype: bool
        """
        if self.condition is None:
            return False

        try:
            # WARNING: The eval build-in function is very dangerous. So, it
            #   should use the `re` module to validate eval-string before
            #   running.
            rs: bool = eval(
                param2template(self.condition, params, extras=self.extras),
                globals() | params,
                {},
            )
            if not isinstance(rs, bool):
                raise TypeError("Return type of condition does not be boolean")
            return not rs
        except Exception as e:
            raise StageException(f"{e.__class__.__name__}: {e}") from e


class BaseAsyncStage(BaseStage):
    """Base Async Stage model to make any stage model allow async execution for
    optimize CPU and Memory on the current node. If you want to implement any
    custom async stage, you can inherit this class and implement
    `self.axecute()` (async + execute = axecute) method only.

        This class is the abstraction class for any inherit asyncable stage
    model.
    """

    @abstractmethod
    def execute(
        self,
        params: DictData,
        *,
        result: Result | None = None,
        event: Event | None = None,
    ) -> Result:
        raise NotImplementedError(
            "Async Stage should implement `execute` method."
        )

    @abstractmethod
    async def axecute(
        self,
        params: DictData,
        *,
        result: Result | None = None,
        event: Event | None = None,
    ) -> Result:
        """Async execution method for this Empty stage that only logging out to
        stdout.

        :param params: (DictData) A context data that want to add output result.
            But this stage does not pass any output.
        :param result: (Result) A result object for keeping context and status
            data.
        :param event: (Event) An event manager that use to track parent execute
            was not force stopped.

        :rtype: Result
        """
        raise NotImplementedError(
            "Async Stage should implement `axecute` method."
        )

    async def handler_axecute(
        self,
        params: DictData,
        *,
        run_id: str | None = None,
        parent_run_id: str | None = None,
        result: Result | None = None,
        event: Event | None = None,
        raise_error: bool | None = None,
    ) -> Result:
        """Async Handler stage execution result from the stage `execute` method.

        :param params: (DictData) A parameter data.
        :param run_id: (str) A stage running ID.
        :param parent_run_id: (str) A parent job running ID.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.
        :param raise_error: (bool) A flag that all this method raise error

        :rtype: Result
        """
        result: Result = Result.construct_with_rs_or_id(
            result,
            run_id=run_id,
            parent_run_id=parent_run_id,
            id_logic=self.iden,
            extras=self.extras,
        )

        try:
            rs: Result = await self.axecute(params, result=result, event=event)
            return rs
        except Exception as e:  # pragma: no cov
            e_name: str = e.__class__.__name__
            await result.trace.aerror(f"[STAGE]: Handler {e_name}: {e}")
            if dynamic("stage_raise_error", f=raise_error, extras=self.extras):
                if isinstance(e, StageException):
                    raise

                raise StageException(
                    f"{self.__class__.__name__}: {e_name}: {e}"
                ) from None

            return result.catch(status=FAILED, context={"errors": to_dict(e)})


class EmptyStage(BaseAsyncStage):
    """Empty stage executor that do nothing and log the `message` field to
    stdout only. It can use for tracking a template parameter on the workflow or
    debug step.

        You can pass a sleep value in second unit to this stage for waiting
    after log message.

    Data Validate:
        >>> stage = {
        ...     "name": "Empty stage execution",
        ...     "echo": "Hello World",
        ...     "sleep": 1,
        ... }
    """

    echo: Optional[str] = Field(
        default=None,
        description="A message that want to show on the stdout.",
    )
    sleep: float = Field(
        default=0,
        description=(
            "A second value to sleep before start execution. This value should "
            "gather or equal 0, and less than 1800 seconds."
        ),
        ge=0,
        lt=1800,
    )

    def execute(
        self,
        params: DictData,
        *,
        result: Result | None = None,
        event: Event | None = None,
    ) -> Result:
        """Execution method for the Empty stage that do only logging out to
        stdout.

            The result context should be empty and do not process anything
        without calling logging function.

        :param params: (DictData) A parameter data.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :rtype: Result
        """
        result: Result = result or Result(
            run_id=gen_id(self.name + (self.id or ""), unique=True),
            extras=self.extras,
        )

        if not self.echo:
            message: str = "..."
        else:
            message: str = param2template(
                dedent(self.echo.strip("\n")), params, extras=self.extras
            )

        result.trace.info(
            f"[STAGE]: Execute Empty-Stage: {self.name!r}: ( {message} )"
        )
        if self.sleep > 0:
            if self.sleep > 5:
                result.trace.info(f"[STAGE]: ... sleep ({self.sleep} sec)")
            time.sleep(self.sleep)
        return result.catch(status=SUCCESS)

    async def axecute(
        self,
        params: DictData,
        *,
        result: Result | None = None,
        event: Event | None = None,
    ) -> Result:
        """Async execution method for this Empty stage that only logging out to
        stdout.

        :param params: (DictData) A parameter data.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :rtype: Result
        """
        result: Result = result or Result(
            run_id=gen_id(self.name + (self.id or ""), unique=True),
            extras=self.extras,
        )

        if not self.echo:
            message: str = "..."
        else:
            message: str = param2template(
                dedent(self.echo.strip("\n")), params, extras=self.extras
            )

        result.trace.info(f"[STAGE]: Empty-Stage: {self.name!r}: ( {message} )")
        if self.sleep > 0:
            if self.sleep > 5:
                await result.trace.ainfo(
                    f"[STAGE]: ... sleep ({self.sleep} sec)"
                )
            await asyncio.sleep(self.sleep)
        return result.catch(status=SUCCESS)


class BashStage(BaseStage):
    """Bash stage executor that execute bash script on the current OS.
    If your current OS is Windows, it will run on the bash from the current WSL.
    It will use `bash` for Windows OS and use `sh` for Linux OS.

        This stage has some limitation when it runs shell statement with the
    built-in subprocess package. It does not good enough to use multiline
    statement. Thus, it will write the `.sh` file before start running bash
    command for fix this issue.

    Data Validate:
        >>> stage = {
        ...     "name": "The Shell stage execution",
        ...     "bash": 'echo "Hello $FOO"',
        ...     "env": {
        ...         "FOO": "BAR",
        ...     },
        ... }
    """

    bash: str = Field(
        description=(
            "A bash statement that want to execute via Python subprocess."
        )
    )
    env: DictStr = Field(
        default_factory=dict,
        description=(
            "An environment variables that set before run bash command. It "
            "will add on the header of the `.sh` file."
        ),
    )

    @contextlib.asynccontextmanager
    async def acreate_sh_file(
        self, bash: str, env: DictStr, run_id: str | None = None
    ) -> AsyncIterator:  # pragma: no cov
        import aiofiles

        f_name: str = f"{run_id or uuid.uuid4()}.sh"
        f_shebang: str = "bash" if sys.platform.startswith("win") else "sh"

        async with aiofiles.open(f"./{f_name}", mode="w", newline="\n") as f:
            # NOTE: write header of `.sh` file
            await f.write(f"#!/bin/{f_shebang}\n\n")

            # NOTE: add setting environment variable before bash skip statement.
            await f.writelines([f"{k}='{env[k]}';\n" for k in env])

            # NOTE: make sure that shell script file does not have `\r` char.
            await f.write("\n" + bash.replace("\r\n", "\n"))

        # NOTE: Make this .sh file able to executable.
        make_exec(f"./{f_name}")

        yield [f_shebang, f_name]

        # Note: Remove .sh file that use to run bash.
        Path(f"./{f_name}").unlink()

    @contextlib.contextmanager
    def create_sh_file(
        self, bash: str, env: DictStr, run_id: str | None = None
    ) -> Iterator[TupleStr]:
        """Return context of prepared bash statement that want to execute. This
        step will write the `.sh` file before giving this file name to context.
        After that, it will auto delete this file automatic.

        :param bash: (str) A bash statement.
        :param env: (DictStr) An environment variable that set before run bash.
        :param run_id: (str | None) A running stage ID that use for writing sh
            file instead generate by UUID4.

        :rtype: Iterator[TupleStr]
        """
        f_name: str = f"{run_id or uuid.uuid4()}.sh"
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

        yield [f_shebang, f_name]

        # Note: Remove .sh file that use to run bash.
        Path(f"./{f_name}").unlink()

    def execute(
        self,
        params: DictData,
        *,
        result: Result | None = None,
        event: Event | None = None,
    ) -> Result:
        """Execute bash statement with the Python build-in `subprocess` package.
        It will catch result from the `subprocess.run` returning output like
        `return_code`, `stdout`, and `stderr`.

        :param params: (DictData) A parameter data.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :rtype: Result
        """
        result: Result = result or Result(
            run_id=gen_id(self.name + (self.id or ""), unique=True),
            extras=self.extras,
        )

        result.trace.info(f"[STAGE]: Execute Shell-Stage: {self.name}")

        bash: str = param2template(
            dedent(self.bash.strip("\n")), params, extras=self.extras
        )

        with self.create_sh_file(
            bash=bash,
            env=param2template(self.env, params, extras=self.extras),
            run_id=result.run_id,
        ) as sh:
            result.trace.debug(f"[STAGE] ... Create `{sh[1]}` file.")
            rs: CompletedProcess = subprocess.run(
                sh, shell=False, capture_output=True, text=True
            )

        if rs.returncode > 0:
            # NOTE: Prepare stderr message that returning from subprocess.
            e: str = (
                rs.stderr.encode("utf-8").decode("utf-16")
                if "\\x00" in rs.stderr
                else rs.stderr
            ).removesuffix("\n")
            raise StageException(
                f"Subprocess: {e}\n---( statement )---\n"
                f"```bash\n{bash}\n```"
            )
        return result.catch(
            status=SUCCESS,
            context={
                "return_code": rs.returncode,
                "stdout": None if (out := rs.stdout.strip("\n")) == "" else out,
                "stderr": None if (out := rs.stderr.strip("\n")) == "" else out,
            },
        )


class PyStage(BaseStage):
    """Python stage that running the Python statement with the current globals
    and passing an input additional variables via `exec` built-in function.

        This stage allow you to use any Python object that exists on the globals
    such as import your installed package.

    Warning:

        The exec build-in function is very dangerous. So, it should use the `re`
    module to validate exec-string before running or exclude the `os` package
    from the current globals variable.

    Data Validate:
        >>> stage = {
        ...     "name": "Python stage execution",
        ...     "run": 'print(f"Hello {VARIABLE}")',
        ...     "vars": {
        ...         "VARIABLE": "WORLD",
        ...     },
        ... }
    """

    run: str = Field(
        description="A Python string statement that want to run with `exec`.",
    )
    vars: DictData = Field(
        default_factory=dict,
        description=(
            "A variable mapping that want to pass to globals parameter in the "
            "`exec` func."
        ),
    )

    @staticmethod
    def filter_locals(values: DictData) -> Iterator[str]:
        """Filter a locals mapping values that be module, class, or
        __annotations__.

        :param values: (DictData) A locals values that want to filter.

        :rtype: Iterator[str]
        """
        for value in values:

            if (
                value == "__annotations__"
                or (value.startswith("__") and value.endswith("__"))
                or ismodule(values[value])
                or isclass(values[value])
            ):
                continue

            yield value

    def set_outputs(self, output: DictData, to: DictData) -> DictData:
        """Override set an outputs method for the Python execution process that
        extract output from all the locals values.

        :param output: (DictData) An output data that want to extract to an
            output key.
        :param to: (DictData) A context data that want to add output result.

        :rtype: DictData
        """
        output: DictData = output.copy()
        lc: DictData = output.pop("locals", {})
        gb: DictData = output.pop("globals", {})
        super().set_outputs(lc | output, to=to)
        to.update({k: gb[k] for k in to if k in gb})
        return to

    def execute(
        self,
        params: DictData,
        *,
        result: Result | None = None,
        event: Event | None = None,
    ) -> Result:
        """Execute the Python statement that pass all globals and input params
        to globals argument on `exec` build-in function.

        :param params: (DictData) A parameter data.
        :param result: (Result) A result object for keeping context and status
            data.
        :param event: (Event) An event manager that use to track parent execute
            was not force stopped.

        :rtype: Result
        """
        result: Result = result or Result(
            run_id=gen_id(self.name + (self.id or ""), unique=True),
            extras=self.extras,
        )

        lc: DictData = {}
        gb: DictData = (
            globals()
            | param2template(self.vars, params, extras=self.extras)
            | {"result": result}
        )

        result.trace.info(f"[STAGE]: Execute Py-Stage: {self.name}")

        # WARNING: The exec build-in function is very dangerous. So, it
        #   should use the re module to validate exec-string before running.
        exec(
            param2template(dedent(self.run), params, extras=self.extras),
            gb,
            lc,
        )

        return result.catch(
            status=SUCCESS,
            context={
                "locals": {k: lc[k] for k in self.filter_locals(lc)},
                "globals": {
                    k: gb[k]
                    for k in gb
                    if (
                        not k.startswith("__")
                        and k != "annotations"
                        and not ismodule(gb[k])
                        and not isclass(gb[k])
                        and not isfunction(gb[k])
                    )
                },
            },
        )

    async def axecute(
        self,
    ):
        """Async execution method.

        References:
            - https://stackoverflow.com/questions/44859165/async-exec-in-python
        """


class CallStage(BaseStage):
    """Call stage executor that call the Python function from registry with tag
    decorator function in `reusables` module and run it with input arguments.

        This stage is different with PyStage because the PyStage is just run
    a Python statement with the `exec` function and pass the current locals and
    globals before exec that statement. This stage will import the caller
    function can call it with an input arguments. So, you can create your
    function complexly that you can for your objective to invoked by this stage
    object.

        This stage is the most powerfull stage of this package for run every
    use-case by a custom requirement that you want by creating the Python
    function and adding it to the caller registry value by importer syntax like
    `module.caller.registry` not path style like `module/caller/registry`.

    Warning:

        The caller registry to get a caller function should importable by the
    current Python execution pointer.

    Data Validate:
        >>> stage = {
        ...     "name": "Task stage execution",
        ...     "uses": "tasks/function-name@tag-name",
        ...     "args": {"arg01": "BAR", "kwarg01": 10},
        ... }
    """

    uses: str = Field(
        description=(
            "A caller function with registry importer syntax that use to load "
            "function before execute step. The caller registry syntax should "
            "be `<import.part>/<func-name>@<tag-name>`."
        ),
    )
    args: DictData = Field(
        default_factory=dict,
        description=(
            "An argument parameter that will pass to this caller function."
        ),
        alias="with",
    )

    def execute(
        self,
        params: DictData,
        *,
        result: Result | None = None,
        event: Event | None = None,
    ) -> Result:
        """Execute this caller function with its argument parameter.

        :param params: (DictData) A parameter data.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :raise ValueError: If necessary arguments does not pass from the `args`
            field.
        :raise TypeError: If the result from the caller function does not match
            with a `dict` type.

        :rtype: Result
        """
        result: Result = result or Result(
            run_id=gen_id(self.name + (self.id or ""), unique=True),
            extras=self.extras,
        )

        call_func: TagFunc = extract_call(
            param2template(self.uses, params, extras=self.extras),
            registries=self.extras.get("registry_caller"),
        )()

        result.trace.info(
            f"[STAGE]: Execute Call-Stage: {call_func.name}@{call_func.tag}"
        )

        # VALIDATE: check input task caller parameters that exists before
        #   calling.
        args: DictData = {"result": result} | param2template(
            self.args, params, extras=self.extras
        )
        ips = inspect.signature(call_func)
        necessary_params: list[str] = []
        has_keyword: bool = False
        for k in ips.parameters:
            if (
                v := ips.parameters[k]
            ).default == Parameter.empty and v.kind not in (
                Parameter.VAR_KEYWORD,
                Parameter.VAR_POSITIONAL,
            ):
                necessary_params.append(k)
            elif v.kind == Parameter.VAR_KEYWORD:
                has_keyword = True

        if any(
            (k.removeprefix("_") not in args and k not in args)
            for k in necessary_params
        ):
            raise ValueError(
                f"Necessary params, ({', '.join(necessary_params)}, ), "
                f"does not set to args, {list(args.keys())}."
            )

        if "result" not in ips.parameters and not has_keyword:
            args.pop("result")

        args = self.parse_model_args(call_func, args, result)

        if inspect.iscoroutinefunction(call_func):
            loop = asyncio.get_event_loop()
            rs: DictData = loop.run_until_complete(
                call_func(**param2template(args, params, extras=self.extras))
            )
        else:
            rs: DictData = call_func(
                **param2template(args, params, extras=self.extras)
            )

        # VALIDATE:
        #   Check the result type from call function, it should be dict.
        if isinstance(rs, BaseModel):
            rs: DictData = rs.model_dump(by_alias=True)
        elif not isinstance(rs, dict):
            raise TypeError(
                f"Return type: '{call_func.name}@{call_func.tag}' does not "
                f"serialize to result model, you change return type to `dict`."
            )
        return result.catch(status=SUCCESS, context=rs)

    @staticmethod
    def parse_model_args(
        func: TagFunc,
        args: DictData,
        result: Result,
    ) -> DictData:
        """Parse Pydantic model from any dict data before parsing to target
        caller function.

        :param func: A tag function that want to get typing.
        :param args: An arguments before passing to this tag function.
        :param result: (Result) A result object for keeping context and status
            data.

        :rtype: DictData
        """
        try:
            type_hints: dict[str, Any] = get_type_hints(func)
        except TypeError as e:
            result.trace.warning(
                f"[STAGE]: Get type hint raise TypeError: {e}, so, it skip "
                f"parsing model args process."
            )
            return args

        for arg in type_hints:

            if arg == "return":
                continue

            if arg.removeprefix("_") in args:
                args[arg] = args.pop(arg.removeprefix("_"))

            t: Any = type_hints[arg]

            # NOTE: Check Result argument was passed to this caller function.
            #
            # if is_dataclass(t) and t.__name__ == "Result" and arg not in args:
            #     args[arg] = result

            if issubclass(t, BaseModel) and arg in args:
                args[arg] = t.model_validate(obj=args[arg])

        return args


class TriggerStage(BaseStage):
    """Trigger workflow executor stage that run an input trigger Workflow
    execute method. This is the stage that allow you to create the reusable
    Workflow template with dynamic parameters.

    Data Validate:
        >>> stage = {
        ...     "name": "Trigger workflow stage execution",
        ...     "trigger": 'workflow-name-for-loader',
        ...     "params": {"run-date": "2024-08-01", "source": "src"},
        ... }
    """

    trigger: str = Field(
        description=(
            "A trigger workflow name. This workflow name should exist on the "
            "config path because it will load by the `load_conf` method."
        ),
    )
    params: DictData = Field(
        default_factory=dict,
        description="A parameter that will pass to workflow execution method.",
    )

    def execute(
        self,
        params: DictData,
        *,
        result: Result | None = None,
        event: Event | None = None,
    ) -> Result:
        """Trigger another workflow execution. It will wait the trigger
        workflow running complete before catching its result.

        :param params: (DictData) A parameter data.
        :param result: (Result) A result object for keeping context and status
            data.
        :param event: (Event) An event manager that use to track parent execute
            was not force stopped.

        :rtype: Result
        """
        from .workflow import Workflow

        result: Result = result or Result(
            run_id=gen_id(self.name + (self.id or ""), unique=True),
            extras=self.extras,
        )

        _trigger: str = param2template(self.trigger, params, extras=self.extras)
        result.trace.info(f"[STAGE]: Execute Trigger-Stage: {_trigger!r}")
        rs: Result = Workflow.from_conf(
            name=_trigger,
            extras=self.extras | {"stage_raise_error": True},
        ).execute(
            params=param2template(self.params, params, extras=self.extras),
            parent_run_id=result.run_id,
            event=event,
        )
        if rs.status == FAILED:
            err_msg: str | None = (
                f" with:\n{msg}"
                if (msg := rs.context.get("errors", {}).get("message"))
                else "."
            )
            raise StageException(
                f"Trigger workflow return failed status{err_msg}"
            )
        return rs


class ParallelStage(BaseStage):  # pragma: no cov
    """Parallel stage executor that execute branch stages with multithreading.
    This stage let you set the fix branches for running child stage inside it on
    multithread pool.

        This stage is not the low-level stage model because it runs multi-stages
    in this stage execution.

    Data Validate:
        >>> stage = {
        ...     "name": "Parallel stage execution.",
        ...     "parallel": {
        ...         "branch01": [
        ...             {
        ...                 "name": "Echo first stage",
        ...                 "echo": "Start run with branch 1",
        ...                 "sleep": 3,
        ...             },
        ...         ],
        ...         "branch02": [
        ...             {
        ...                 "name": "Echo second stage",
        ...                 "echo": "Start run with branch 2",
        ...                 "sleep": 1,
        ...             },
        ...         ],
        ...     }
        ... }
    """

    parallel: dict[str, list[Stage]] = Field(
        description="A mapping of branch name and its stages.",
    )
    max_workers: int = Field(
        default=2,
        ge=1,
        lt=20,
        description=(
            "The maximum multi-thread pool worker size for execution parallel. "
            "This value should be gather or equal than 1, and less than 20."
        ),
        alias="max-workers",
    )

    def execute_branch(
        self,
        branch: str,
        params: DictData,
        result: Result,
        *,
        event: Event | None = None,
    ) -> Result:
        """Execute all stage with specific branch ID.

        :param branch: (str) A branch ID.
        :param params: (DictData) A parameter data.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :rtype: Result
        """
        result.trace.debug(f"[STAGE]: Execute Branch: {branch!r}")
        context: DictData = copy.deepcopy(params)
        context.update({"branch": branch})
        output: DictData = {"branch": branch, "stages": {}}
        for stage in self.parallel[branch]:

            if self.extras:
                stage.extras = self.extras

            if stage.is_skipped(params=context):
                result.trace.info(f"[STAGE]: Skip stage: {stage.iden!r}")
                stage.set_outputs(output={"skipped": True}, to=output)
                continue

            if event and event.is_set():
                error_msg: str = (
                    "Branch-Stage was canceled from event that had set before "
                    "stage branch execution."
                )
                return result.catch(
                    status=CANCEL,
                    parallel={
                        branch: {
                            "branch": branch,
                            "stages": filter_func(output.pop("stages", {})),
                            "errors": StageException(error_msg).to_dict(),
                        }
                    },
                )

            try:
                rs: Result = stage.handler_execute(
                    params=context,
                    run_id=result.run_id,
                    parent_run_id=result.parent_run_id,
                    raise_error=True,
                    event=event,
                )
                stage.set_outputs(rs.context, to=output)
                stage.set_outputs(stage.get_outputs(output), to=context)
            except StageException as e:  # pragma: no cov
                result.catch(
                    status=FAILED,
                    parallel={
                        branch: {
                            "branch": branch,
                            "stages": filter_func(output.pop("stages", {})),
                            "errors": e.to_dict(),
                        },
                    },
                )
                raise

            if rs.status == FAILED:
                error_msg: str = (
                    f"Branch-Stage was break because it has a sub stage, "
                    f"{stage.iden}, failed without raise error."
                )
                result.catch(
                    status=FAILED,
                    parallel={
                        branch: {
                            "branch": branch,
                            "stages": filter_func(output.pop("stages", {})),
                            "errors": StageException(error_msg).to_dict(),
                        },
                    },
                )
                raise StageException(error_msg)

        return result.catch(
            status=SUCCESS,
            parallel={
                branch: {
                    "branch": branch,
                    "stages": filter_func(output.pop("stages", {})),
                },
            },
        )

    def execute(
        self,
        params: DictData,
        *,
        result: Result | None = None,
        event: Event | None = None,
    ) -> Result:
        """Execute parallel each branch via multi-threading pool.

        :param params: (DictData) A parameter data.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :rtype: Result
        """
        result: Result = result or Result(
            run_id=gen_id(self.name + (self.id or ""), unique=True),
            extras=self.extras,
        )
        event: Event = Event() if event is None else event
        result.trace.info(
            f"[STAGE]: Execute Parallel-Stage: {self.max_workers} workers."
        )
        result.catch(status=WAIT, context={"parallel": {}})
        if event and event.is_set():  # pragma: no cov
            return result.catch(
                status=CANCEL,
                context={
                    "errors": StageException(
                        "Stage was canceled from event that had set "
                        "before stage parallel execution."
                    ).to_dict()
                },
            )

        with ThreadPoolExecutor(
            max_workers=self.max_workers, thread_name_prefix="stage_parallel_"
        ) as executor:

            context: DictData = {}
            status: Status = SUCCESS

            futures: list[Future] = (
                executor.submit(
                    self.execute_branch,
                    branch=branch,
                    params=params,
                    result=result,
                    event=event,
                )
                for branch in self.parallel
            )

            for future in as_completed(futures):
                try:
                    future.result()
                except StageException as e:
                    status = FAILED
                    result.trace.error(f"[STAGE]: {e.__class__.__name__}: {e}")
                    if "errors" in context:
                        context["errors"].append(e.to_dict())
                    else:
                        context["errors"] = [e.to_dict()]
        return result.catch(status=status, context=context)


class ForEachStage(BaseStage):
    """For-Each stage executor that execute all stages with each item in the
    foreach list.

        This stage is not the low-level stage model because it runs
    multi-stages in this stage execution.

    Data Validate:
        >>> stage = {
        ...     "name": "For-each stage execution",
        ...     "foreach": [1, 2, 3]
        ...     "stages": [
        ...         {
        ...             "name": "Echo stage",
        ...             "echo": "Start run with item ${{ item }}"
        ...         },
        ...     ],
        ... }
    """

    foreach: Union[list[str], list[int], str] = Field(
        description=(
            "A items for passing to stages via ${{ item }} template parameter."
        ),
    )
    stages: list[Stage] = Field(
        default_factory=list,
        description=(
            "A list of stage that will run with each item in the `foreach` "
            "field."
        ),
    )
    concurrent: int = Field(
        default=1,
        ge=1,
        lt=10,
        description=(
            "A concurrent value allow to run each item at the same time. It "
            "will be sequential mode if this value equal 1."
        ),
    )

    def execute_item(
        self,
        item: StrOrInt,
        params: DictData,
        result: Result,
        *,
        event: Event | None = None,
    ) -> Result:
        """Execute all stage with specific foreach item.

        :param item: (str | int) An item that want to execution.
        :param params: (DictData) A parameter data.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :raise StageException: If the stage execution raise errors.

        :rtype: Result
        """
        result.trace.debug(f"[STAGE]: Execute Item: {item!r}")
        context: DictData = copy.deepcopy(params)
        context.update({"item": item})
        output: DictData = {"item": item, "stages": {}}
        for stage in self.stages:

            if self.extras:
                stage.extras = self.extras

            if stage.is_skipped(params=context):
                result.trace.info(f"[STAGE]: Skip stage: {stage.iden!r}")
                stage.set_outputs(output={"skipped": True}, to=output)
                continue

            if event and event.is_set():  # pragma: no cov
                error_msg: str = (
                    "Item-Stage was canceled from event that had set before "
                    "stage item execution."
                )
                return result.catch(
                    status=CANCEL,
                    foreach={
                        item: {
                            "item": item,
                            "stages": filter_func(output.pop("stages", {})),
                            "errors": StageException(error_msg).to_dict(),
                        }
                    },
                )

            try:
                rs: Result = stage.handler_execute(
                    params=context,
                    run_id=result.run_id,
                    parent_run_id=result.parent_run_id,
                    raise_error=True,
                    event=event,
                )
                stage.set_outputs(rs.context, to=output)
                stage.set_outputs(stage.get_outputs(output), to=context)
            except StageException as e:
                result.catch(
                    status=FAILED,
                    foreach={
                        item: {
                            "item": item,
                            "stages": filter_func(output.pop("stages", {})),
                            "errors": e.to_dict(),
                        },
                    },
                )
                raise

            if rs.status == FAILED:
                error_msg: str = (
                    f"Item-Stage was break because it has a sub stage, "
                    f"{stage.iden}, failed without raise error."
                )
                result.trace.warning(f"[STAGE]: {error_msg}")
                result.catch(
                    status=FAILED,
                    foreach={
                        item: {
                            "item": item,
                            "stages": filter_func(output.pop("stages", {})),
                            "errors": StageException(error_msg).to_dict(),
                        },
                    },
                )
                raise StageException(error_msg)

        return result.catch(
            status=SUCCESS,
            foreach={
                item: {
                    "item": item,
                    "stages": filter_func(output.pop("stages", {})),
                },
            },
        )

    def execute(
        self,
        params: DictData,
        *,
        result: Result | None = None,
        event: Event | None = None,
    ) -> Result:
        """Execute the stages that pass each item form the foreach field.

        :param params: (DictData) A parameter data.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :raise TypeError: If the foreach does not match with type list.

        :rtype: Result
        """
        result: Result = result or Result(
            run_id=gen_id(self.name + (self.id or ""), unique=True),
            extras=self.extras,
        )
        event: Event = Event() if event is None else event
        foreach: Union[list[str], list[int]] = (
            param2template(self.foreach, params, extras=self.extras)
            if isinstance(self.foreach, str)
            else self.foreach
        )

        # [VALIDATE]: Type of the foreach should be `list` type.
        if not isinstance(foreach, list):
            raise TypeError(f"Does not support foreach: {foreach!r}")

        result.trace.info(f"[STAGE]: Execute Foreach-Stage: {foreach!r}.")
        result.catch(status=WAIT, context={"items": foreach, "foreach": {}})
        if event and event.is_set():  # pragma: no cov
            return result.catch(
                status=CANCEL,
                context={
                    "errors": StageException(
                        "Stage was canceled from event that had set "
                        "before stage foreach execution."
                    ).to_dict()
                },
            )

        with ThreadPoolExecutor(
            max_workers=self.concurrent, thread_name_prefix="stage_foreach_"
        ) as executor:

            futures: list[Future] = [
                executor.submit(
                    self.execute_item,
                    item=item,
                    params=params,
                    result=result,
                    event=event,
                )
                for item in foreach
            ]
            context: DictData = {}
            status: Status = SUCCESS

            done, not_done = wait(futures, return_when=FIRST_EXCEPTION)
            if len(done) != len(futures):
                result.trace.warning(
                    "[STAGE]: Set event for stop pending stage future."
                )
                event.set()
                for future in not_done:
                    future.cancel()

                nd: str = f", item not run: {not_done}" if not_done else ""
                result.trace.debug(f"[STAGE]: ... Foreach set Fail-Fast{nd}")

            for future in done:
                try:
                    future.result()
                except StageException as e:
                    status = FAILED
                    result.trace.error(f"[STAGE]: {e.__class__.__name__}: {e}")
                    context.update({"errors": e.to_dict()})
        return result.catch(status=status, context=context)


class UntilStage(BaseStage):
    """Until stage executor that will run stages in each loop until it valid
    with stop loop condition.

        This stage is not the low-level stage model because it runs
    multi-stages in this stage execution.

    Data Validate:
        >>> stage = {
        ...     "name": "Until stage execution",
        ...     "item": 1,
        ...     "until": "${{ item }} > 3"
        ...     "stages": [
        ...         {
        ...             "name": "Start increase item value.",
        ...             "run": "item = ${{ item }}\\nitem += 1\\n"
        ...         },
        ...     ],
        ... }
    """

    item: Union[str, int, bool] = Field(
        default=0,
        description=(
            "An initial value that can be any value in str, int, or bool type."
        ),
    )
    until: str = Field(description="A until condition for stop the while loop.")
    stages: list[Stage] = Field(
        default_factory=list,
        description=(
            "A list of stage that will run with each item in until loop."
        ),
    )
    max_loop: int = Field(
        default=10,
        ge=1,
        lt=100,
        description=(
            "The maximum value of loop for this until stage. This value should "
            "be gather or equal than 1, and less than 100."
        ),
        alias="max-loop",
    )

    def execute_loop(
        self,
        item: T,
        loop: int,
        params: DictData,
        result: Result,
        event: Event | None = None,
    ) -> tuple[Result, T]:
        """Execute all stage with specific loop and item.

        :param item: (T) An item that want to execution.
        :param loop: (int) A number of loop.
        :param params: (DictData) A parameter data.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :rtype: tuple[Result, T]
        :return: Return a pair of Result and changed item.
        """
        result.trace.debug(f"[STAGE]: ... Execute until item: {item!r}")
        context: DictData = copy.deepcopy(params)
        context.update({"item": item})
        output: DictData = {"loop": loop, "item": item, "stages": {}}
        next_item: T = None
        for stage in self.stages:

            if self.extras:
                stage.extras = self.extras

            if stage.is_skipped(params=context):
                result.trace.info(f"[STAGE]: Skip stage: {stage.iden!r}")
                stage.set_outputs(output={"skipped": True}, to=output)
                continue

            if event and event.is_set():
                error_msg: str = (
                    "Loop-Stage was canceled from event that had set before "
                    "stage loop execution."
                )
                return (
                    result.catch(
                        status=CANCEL,
                        until={
                            loop: {
                                "loop": loop,
                                "item": item,
                                "stages": filter_func(output.pop("stages", {})),
                                "errors": StageException(error_msg).to_dict(),
                            }
                        },
                    ),
                    next_item,
                )

            try:
                rs: Result = stage.handler_execute(
                    params=context,
                    run_id=result.run_id,
                    parent_run_id=result.parent_run_id,
                    raise_error=True,
                    event=event,
                )
                stage.set_outputs(rs.context, to=output)

                if "item" in (_output := stage.get_outputs(output)):
                    next_item = _output["item"]

                stage.set_outputs(_output, to=context)
            except StageException as e:
                result.catch(
                    status=FAILED,
                    until={
                        loop: {
                            "loop": loop,
                            "item": item,
                            "stages": filter_func(output.pop("stages", {})),
                            "errors": e.to_dict(),
                        }
                    },
                )
                raise

            if rs.status == FAILED:
                error_msg: str = (
                    f"Loop-Stage was break because it has a sub stage, "
                    f"{stage.iden}, failed without raise error."
                )
                result.catch(
                    status=FAILED,
                    until={
                        loop: {
                            "loop": loop,
                            "item": item,
                            "stages": filter_func(output.pop("stages", {})),
                            "errors": StageException(error_msg).to_dict(),
                        }
                    },
                )
                raise StageException(error_msg)

        return (
            result.catch(
                status=SUCCESS,
                until={
                    loop: {
                        "loop": loop,
                        "item": item,
                        "stages": filter_func(output.pop("stages", {})),
                    }
                },
            ),
            next_item,
        )

    def execute(
        self,
        params: DictData,
        *,
        result: Result | None = None,
        event: Event | None = None,
    ) -> Result:
        """Execute until loop with checking until condition.

        :param params: (DictData) A parameter data.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :rtype: Result
        """
        result: Result = result or Result(
            run_id=gen_id(self.name + (self.id or ""), unique=True),
            extras=self.extras,
        )

        result.trace.info(f"[STAGE]: Execute Until-Stage: {self.until}")
        item: Union[str, int, bool] = param2template(
            self.item, params, extras=self.extras
        )
        loop: int = 1
        track: bool = True
        exceed_loop: bool = False
        result.catch(status=WAIT, context={"until": {}})
        while track and not (exceed_loop := loop >= self.max_loop):

            if event and event.is_set():
                return result.catch(
                    status=CANCEL,
                    context={
                        "errors": StageException(
                            "Stage was canceled from event that had set "
                            "before stage loop execution."
                        ).to_dict()
                    },
                )

            result, item = self.execute_loop(
                item=item,
                loop=loop,
                params=params,
                result=result,
                event=event,
            )

            loop += 1
            if item is None:
                result.trace.warning(
                    f"[STAGE]: ... Loop-Execute not set item. It use loop: {loop} by "
                    f"default."
                )
                item: int = loop

            next_track: bool = eval(
                param2template(
                    self.until,
                    params | {"item": item, "loop": loop},
                    extras=self.extras,
                ),
                globals() | params | {"item": item},
                {},
            )
            if not isinstance(next_track, bool):
                raise StageException(
                    "Return type of until condition not be `boolean`, getting"
                    f": {next_track!r}"
                )
            track: bool = not next_track
            delay(0.025)

        if exceed_loop:
            raise StageException(
                f"The until loop was exceed {self.max_loop} loops"
            )
        return result.catch(status=SUCCESS)


class Match(BaseModel):
    """Match model for the Case Stage."""

    case: StrOrInt = Field(description="A match case.")
    stages: list[Stage] = Field(
        description="A list of stage to execution for this case."
    )


class CaseStage(BaseStage):
    """Case stage executor that execute all stages if the condition was matched.

    Data Validate:
        >>> stage = {
        ...     "name": "If stage execution.",
        ...     "case": "${{ param.test }}",
        ...     "match": [
        ...         {
        ...             "case": "1",
        ...             "stages": [
        ...                 {
        ...                     "name": "Stage case 1",
        ...                     "eche": "Hello case 1",
        ...                 },
        ...             ],
        ...         },
        ...         {
        ...             "case": "_",
        ...             "stages": [
        ...                 {
        ...                     "name": "Stage else",
        ...                     "eche": "Hello case else",
        ...                 },
        ...             ],
        ...         },
        ...     ],
        ... }

    """

    case: str = Field(description="A case condition for routing.")
    match: list[Match] = Field(
        description="A list of Match model that should not be an empty list.",
    )
    skip_not_match: bool = Field(
        default=False,
        description=(
            "A flag for making skip if it does not match and else condition "
            "does not set too."
        ),
        alias="skip-not-match",
    )

    def execute_case(
        self,
        case: str,
        stages: list[Stage],
        params: DictData,
        result: Result,
        *,
        event: Event | None = None,
    ) -> Result:
        """Execute case.

        :param case: (str) A case that want to execution.
        :param stages: (list[Stage]) A list of stage.
        :param params: (DictData) A parameter data.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :rtype: Result
        """
        context: DictData = copy.deepcopy(params)
        context.update({"case": case})
        output: DictData = {"case": case, "stages": {}}
        for stage in stages:

            if self.extras:
                stage.extras = self.extras

            if stage.is_skipped(params=context):
                result.trace.info(f"[STAGE]: ... Skip stage: {stage.iden!r}")
                stage.set_outputs(output={"skipped": True}, to=output)
                continue

            if event and event.is_set():  # pragma: no cov
                error_msg: str = (
                    "Case-Stage was canceled from event that had set before "
                    "stage case execution."
                )
                return result.catch(
                    status=CANCEL,
                    context={
                        "case": case,
                        "stages": filter_func(output.pop("stages", {})),
                        "errors": StageException(error_msg).to_dict(),
                    },
                )

            try:
                rs: Result = stage.handler_execute(
                    params=context,
                    run_id=result.run_id,
                    parent_run_id=result.parent_run_id,
                    raise_error=True,
                    event=event,
                )
                stage.set_outputs(rs.context, to=output)
                stage.set_outputs(stage.get_outputs(output), to=context)
            except StageException as e:  # pragma: no cov
                return result.catch(
                    status=FAILED,
                    context={
                        "case": case,
                        "stages": filter_func(output.pop("stages", {})),
                        "errors": e.to_dict(),
                    },
                )

            if rs.status == FAILED:
                error_msg: str = (
                    f"Case-Stage was break because it has a sub stage, "
                    f"{stage.iden}, failed without raise error."
                )
                return result.catch(
                    status=FAILED,
                    context={
                        "case": case,
                        "stages": filter_func(output.pop("stages", {})),
                        "errors": StageException(error_msg).to_dict(),
                    },
                )
        return result.catch(
            status=SUCCESS,
            context={
                "case": case,
                "stages": filter_func(output.pop("stages", {})),
            },
        )

    def execute(
        self,
        params: DictData,
        *,
        result: Result | None = None,
        event: Event | None = None,
    ) -> Result:
        """Execute case-match condition that pass to the case field.

        :param params: (DictData) A parameter data.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :rtype: Result
        """
        result: Result = result or Result(
            run_id=gen_id(self.name + (self.id or ""), unique=True),
            extras=self.extras,
        )

        _case: Optional[str] = param2template(
            self.case, params, extras=self.extras
        )

        result.trace.info(f"[STAGE]: Execute Case-Stage: {_case!r}.")
        _else: Optional[Match] = None
        stages: Optional[list[Stage]] = None
        for match in self.match:
            if (c := match.case) == "_":
                _else: Match = match
                continue

            _condition: str = param2template(c, params, extras=self.extras)
            if stages is None and _case == _condition:
                stages: list[Stage] = match.stages

        if stages is None:
            if _else is None:
                if not self.skip_not_match:
                    raise StageException(
                        "This stage does not set else for support not match "
                        "any case."
                    )
                result.trace.info(
                    "[STAGE]: ... Skip this stage because it does not match."
                )
                error_msg: str = (
                    "Case-Stage was canceled because it does not match any "
                    "case and else condition does not set too."
                )
                return result.catch(
                    status=CANCEL,
                    context={"errors": StageException(error_msg).to_dict()},
                )
            _case: str = "_"
            stages: list[Stage] = _else.stages

        if event and event.is_set():  # pragma: no cov
            return result.catch(
                status=CANCEL,
                context={
                    "errors": StageException(
                        "Stage was canceled from event that had set before "
                        "case-stage execution."
                    ).to_dict()
                },
            )

        return self.execute_case(
            case=_case, stages=stages, params=params, result=result, event=event
        )


class RaiseStage(BaseStage):  # pragma: no cov
    """Raise error stage executor that raise `StageException` that use a message
    field for making error message before raise.

    Data Validate:
        >>> stage = {
        ...     "name": "Raise stage",
        ...     "raise": "raise this stage",
        ... }

    """

    message: str = Field(
        description=(
            "An error message that want to raise with `StageException` class"
        ),
        alias="raise",
    )

    def execute(
        self,
        params: DictData,
        *,
        result: Result | None = None,
        event: Event | None = None,
    ) -> Result:
        """Raise the StageException object with the message field execution.

        :param params: (DictData) A parameter data.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.
        """
        result: Result = result or Result(
            run_id=gen_id(self.name + (self.id or ""), unique=True),
            extras=self.extras,
        )
        message: str = param2template(self.message, params, extras=self.extras)
        result.trace.info(f"[STAGE]: Execute Raise-Stage: {message!r}.")
        raise StageException(message)


class DockerStage(BaseStage):  # pragma: no cov
    """Docker container stage execution that will pull the specific Docker image
    with custom authentication and run this image by passing environment
    variables and mounting local volume to this Docker container.

        The volume path that mount to this Docker container will limit. That is
    this stage does not allow you to mount any path to this container.

    Data Validate:
        >>> stage = {
        ...     "name": "Docker stage execution",
        ...     "image": "image-name.pkg.com",
        ...     "env": {
        ...         "ENV": "dev",
        ...         "SECRET": "${SPECIFIC_SECRET}",
        ...     },
        ...     "auth": {
        ...         "username": "__json_key",
        ...         "password": "${GOOGLE_CREDENTIAL_JSON_STRING}",
        ...     },
        ... }
    """

    image: str = Field(
        description="A Docker image url with tag that want to run.",
    )
    tag: str = Field(default="latest", description="An Docker image tag.")
    env: DictData = Field(
        default_factory=dict,
        description=(
            "An environment variable that want pass to Docker container.",
        ),
    )
    volume: DictData = Field(
        default_factory=dict,
        description="A mapping of local and target mounting path.",
    )
    auth: DictData = Field(
        default_factory=dict,
        description=(
            "An authentication of the Docker registry that use in pulling step."
        ),
    )

    def execute_task(
        self,
        params: DictData,
        result: Result,
        event: Event | None = None,
    ) -> Result:
        """Execute Docker container task.

        :param params: (DictData) A parameter data.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :rtype: Result
        """
        from docker import DockerClient
        from docker.errors import ContainerError

        client = DockerClient(
            base_url="unix://var/run/docker.sock", version="auto"
        )

        resp = client.api.pull(
            repository=f"{self.image}",
            tag=self.tag,
            auth_config=param2template(self.auth, params, extras=self.extras),
            stream=True,
            decode=True,
        )
        for line in resp:
            result.trace.info(f"[STAGE]: ... {line}")

        if event and event.is_set():
            error_msg: str = (
                "Docker-Stage was canceled from event that had set before "
                "run the Docker container."
            )
            return result.catch(
                status=CANCEL,
                context={"errors": StageException(error_msg).to_dict()},
            )

        unique_image_name: str = f"{self.image}_{datetime.now():%Y%m%d%H%M%S%f}"
        container = client.containers.run(
            image=f"{self.image}:{self.tag}",
            name=unique_image_name,
            environment=self.env,
            volumes=(
                {
                    Path.cwd()
                    / f".docker.{result.run_id}.logs": {
                        "bind": "/logs",
                        "mode": "rw",
                    },
                }
                | {
                    Path.cwd() / source: {"bind": target, "mode": "rw"}
                    for source, target in (
                        volume.split(":", maxsplit=1) for volume in self.volume
                    )
                }
            ),
            detach=True,
        )

        for line in container.logs(stream=True, timestamps=True):
            result.trace.info(f"[STAGE]: ... {line.strip().decode()}")

        # NOTE: This code copy from the docker package.
        exit_status: int = container.wait()["StatusCode"]
        if exit_status != 0:
            out = container.logs(stdout=False, stderr=True)
            container.remove()
            raise ContainerError(
                container,
                exit_status,
                None,
                f"{self.image}:{self.tag}",
                out,
            )
        output_file: Path = Path(f".docker.{result.run_id}.logs/outputs.json")
        if not output_file.exists():
            return result.catch(status=SUCCESS)

        with output_file.open(mode="rt") as f:
            data = json.load(f)
        return result.catch(status=SUCCESS, context=data)

    def execute(
        self,
        params: DictData,
        *,
        result: Result | None = None,
        event: Event | None = None,
    ) -> Result:
        """Execute the Docker image via Python API.

        :param params: (DictData) A parameter data.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :rtype: Result
        """
        result: Result = result or Result(
            run_id=gen_id(self.name + (self.id or ""), unique=True),
            extras=self.extras,
        )

        result.trace.info(
            f"[STAGE]: Execute Docker-Stage: {self.image}:{self.tag}"
        )
        raise NotImplementedError("Docker Stage does not implement yet.")


class VirtualPyStage(PyStage):  # pragma: no cov
    """Virtual Python stage executor that run Python statement on the dependent
    Python virtual environment via the `uv` package.
    """

    version: str = Field(
        default="3.9",
        description="A Python version that want to run.",
    )
    deps: list[str] = Field(
        description=(
            "list of Python dependency that want to install before execution "
            "stage."
        ),
    )

    @contextlib.contextmanager
    def create_py_file(
        self,
        py: str,
        values: DictData,
        deps: list[str],
        run_id: str | None = None,
    ) -> Iterator[str]:
        """Create the .py file with an input Python string statement.

        :param py: A Python string statement.
        :param values: A variable that want to set before running this
        :param deps: An additional Python dependencies that want install before
            run this python stage.
        :param run_id: (str | None) A running ID of this stage execution.
        """
        run_id: str = run_id or uuid.uuid4()
        f_name: str = f"{run_id}.py"
        with open(f"./{f_name}", mode="w", newline="\n") as f:
            # NOTE: Create variable mapping that write before running statement.
            vars_str: str = "\n ".join(
                f"{var} = {value!r}" for var, value in values.items()
            )

            # NOTE: uv supports PEP 723 — inline TOML metadata.
            f.write(
                dedent(
                    f"""
                    # /// script
                    # dependencies = [{', '.join(f'"{dep}"' for dep in deps)}]
                    # ///
                    {vars_str}
                    """.strip(
                        "\n"
                    )
                )
            )

            # NOTE: make sure that py script file does not have `\r` char.
            f.write("\n" + py.replace("\r\n", "\n"))

        # NOTE: Make this .py file able to executable.
        make_exec(f"./{f_name}")

        yield f_name

        # Note: Remove .py file that use to run Python.
        Path(f"./{f_name}").unlink()

    def execute(
        self,
        params: DictData,
        *,
        result: Result | None = None,
        event: Event | None = None,
    ) -> Result:
        """Execute the Python statement via Python virtual environment.

        Steps:
            - Create python file with the `uv` syntax.
            - Execution python file with `uv run` via Python subprocess module.

        :param params: (DictData) A parameter data.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :rtype: Result
        """
        result: Result = result or Result(
            run_id=gen_id(self.name + (self.id or ""), unique=True),
            extras=self.extras,
        )

        result.trace.info(f"[STAGE]: Execute VirtualPy-Stage: {self.name}")
        run: str = param2template(dedent(self.run), params, extras=self.extras)
        with self.create_py_file(
            py=run,
            values=param2template(self.vars, params, extras=self.extras),
            deps=param2template(self.deps, params, extras=self.extras),
            run_id=result.run_id,
        ) as py:
            result.trace.debug(f"[STAGE]: ... Create `{py}` file.")
            rs: CompletedProcess = subprocess.run(
                ["uv", "run", py, "--no-cache"],
                # ["uv", "run", "--python", "3.9", py],
                shell=False,
                capture_output=True,
                text=True,
            )

        if rs.returncode > 0:
            # NOTE: Prepare stderr message that returning from subprocess.
            e: str = (
                rs.stderr.encode("utf-8").decode("utf-16")
                if "\\x00" in rs.stderr
                else rs.stderr
            ).removesuffix("\n")
            raise StageException(
                f"Subprocess: {e}\nRunning Statement:\n---\n"
                f"```python\n{run}\n```"
            )
        return result.catch(
            status=SUCCESS,
            context={
                "return_code": rs.returncode,
                "stdout": None if (out := rs.stdout.strip("\n")) == "" else out,
                "stderr": None if (out := rs.stderr.strip("\n")) == "" else out,
            },
        )


# NOTE:
#   An order of parsing stage model on the Job model with `stages` field.
#   From the current build-in stages, they do not have stage that have the same
#   fields that because of parsing on the Job's stages key.
#
Stage = Annotated[
    Union[
        DockerStage,
        BashStage,
        CallStage,
        TriggerStage,
        ForEachStage,
        UntilStage,
        ParallelStage,
        CaseStage,
        VirtualPyStage,
        PyStage,
        RaiseStage,
        EmptyStage,
    ],
    Field(union_mode="smart"),
]
