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

    Execution   --> Ok      ┬--( handler )--> Result with `SUCCESS` or `CANCEL`
                            |
                            ├--( handler )--> Result with `FAILED` (Set `raise_error` flag)
                            |
                            ╰--( handler )---> Result with `SKIP`

                --> Error   ---( handler )--> Raise StageError(...)

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
import traceback
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from concurrent.futures import (
    FIRST_EXCEPTION,
    CancelledError,
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

from pydantic import BaseModel, Field, ValidationError
from pydantic.functional_validators import field_validator, model_validator
from typing_extensions import Self

from .__types import DictData, DictStr, StrOrInt, StrOrNone, TupleStr
from .conf import dynamic, pass_env
from .errors import StageError, StageSkipError, to_dict
from .result import CANCEL, FAILED, SKIP, SUCCESS, WAIT, Result, Status
from .reusables import (
    TagFunc,
    create_model_from_caller,
    extract_call,
    not_in_template,
    param2template,
)
from .utils import (
    delay,
    dump_all,
    filter_func,
    gen_id,
    make_exec,
    to_train,
)

T = TypeVar("T")
DictOrModel = Union[DictData, BaseModel]


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
    id: StrOrNone = Field(
        default=None,
        description=(
            "A stage ID that use to keep execution output or getting by job "
            "owner."
        ),
    )
    name: str = Field(
        description="A stage name that want to logging when start execution.",
    )
    desc: StrOrNone = Field(
        default=None,
        description=(
            "A stage description that use to logging when start execution."
        ),
    )
    condition: StrOrNone = Field(
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

    @field_validator("desc", mode="after")
    def ___prepare_desc__(cls, value: str) -> str:
        """Prepare description string that was created on a template.

        :rtype: str
        """
        return dedent(value.lstrip("\n"))

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
        result: Optional[Result] = None,
        event: Optional[Event] = None,
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
        run_id: StrOrNone = None,
        parent_run_id: StrOrNone = None,
        result: Optional[Result] = None,
        event: Optional[Event] = None,
    ) -> Union[Result, DictData]:
        """Handler stage execution result from the stage `execute` method.

            This stage exception handler still use ok-error concept, but it
        allows you force catching an output result with error message by
        specific environment variable,`WORKFLOW_CORE_STAGE_RAISE_ERROR` or set
        `raise_error` parameter to True.

            Execution   --> Ok      --> Result
                                        |-status: SUCCESS
                                        ╰-context:
                                            ╰-outputs: ...

                        --> Ok      --> Result
                                        |-status: CANCEL
                                        ╰-errors:
                                            |-name: ...
                                            ╰-message: ...

                        --> Ok      --> Result
                                        |-status: SKIP
                                        ╰-skipped: True

                        --> Ok      --> Result
                                        |-status: FAILED
                                        ╰-errors:
                                            |-name: ...
                                            ╰-message: ...

            On the last step, it will set the running ID on a return result
        object from the current stage ID before release the final result.

        :param params: (DictData) A parameter data.
        :param run_id: (str) A running stage ID.
        :param parent_run_id: (str) A parent running ID.
        :param result: (Result) A result object for keeping context and status
            data before execution.
        :param event: (Event) An event manager that pass to the stage execution.

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
            result.trace.info(
                f"[STAGE]: Handler {to_train(self.__class__.__name__)}: "
                f"{self.name!r}."
            )
            if self.desc:
                result.trace.debug(f"[STAGE]: Description:||{self.desc}||")
            return self.execute(params, result=result, event=event)
        except StageSkipError as e:
            result.trace.info(
                f"[STAGE]: Skip Handler:||StageSkipError:{e}||"
                f"{traceback.format_exc()}"
            )
            return result.catch(status=SKIP, context={"skipped": True})
        except StageError as e:
            result.trace.error(
                f"[STAGE]: Error Handler:||StageError:||{e}||"
                f"{traceback.format_exc()}"
            )
            return result.catch(status=FAILED, context={"errors": e.to_dict()})
        except Exception as e:
            result.trace.error(
                f"[STAGE]: Error Handler:||{e.__class__.__name__}:||{e}||"
                f"{traceback.format_exc()}"
            )
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

        output: DictData = output.copy()
        errors: DictData = (
            {"errors": output.pop("errors", {})} if "errors" in output else {}
        )
        skipping: dict[str, bool] = (
            {"skipped": output.pop("skipped", False)}
            if "skipped" in output
            else {}
        )
        to["stages"][self.gen_id(params=to)] = {
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
        return (
            output.get("stages", {})
            .get(self.gen_id(params=output), {})
            .get("outputs", {})
        )

    def is_skipped(self, params: DictData) -> bool:
        """Return true if condition of this stage do not correct. This process
        use build-in eval function to execute the if-condition.

        :param params: (DictData) A parameters that want to pass to condition
            template.

        :raise StageError: When it has any error raise from the eval
            condition statement.
        :raise StageError: When return type of the eval condition statement
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
            raise StageError(f"{e.__class__.__name__}: {e}") from e

    def gen_id(self, params: DictData) -> str:
        """Generate stage ID that dynamic use stage's name if it ID does not
        set.

        :param params: A parameter data.

        :rtype: str
        """
        return (
            param2template(self.id, params=params, extras=self.extras)
            if self.id
            else gen_id(
                param2template(self.name, params=params, extras=self.extras)
            )
        )

    @property
    def is_nested(self) -> bool:
        """Return true if this stage is nested stage.

        :rtype: bool
        """
        return False


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
        result: Optional[Result] = None,
        event: Optional[Event] = None,
    ) -> Result:
        raise NotImplementedError(
            "Async Stage should implement `execute` method."
        )

    @abstractmethod
    async def axecute(
        self,
        params: DictData,
        *,
        result: Optional[Result] = None,
        event: Optional[Event] = None,
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
        run_id: StrOrNone = None,
        parent_run_id: StrOrNone = None,
        result: Optional[Result] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Async Handler stage execution result from the stage `execute` method.

        :param params: (DictData) A parameter data.
        :param run_id: (str) A stage running ID.
        :param parent_run_id: (str) A parent job running ID.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

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
            await result.trace.ainfo(
                f"[STAGE]: Handler {to_train(self.__class__.__name__)}: "
                f"{self.name!r}."
            )
            if self.desc:
                await result.trace.adebug(
                    f"[STAGE]: Description:||{self.desc}||"
                )
            return await self.axecute(params, result=result, event=event)
        except StageSkipError as e:
            await result.trace.ainfo(
                f"[STAGE]: Skip Handler:||StageSkipError:{e}||"
                f"{traceback.format_exc()}"
            )
            return result.catch(status=SKIP, context={"skipped": True})
        except StageError as e:
            await result.trace.aerror(
                f"[STAGE]: Error Handler:||StageError:||{e}||"
                f"{traceback.format_exc()}"
            )
            return result.catch(status=FAILED, context={"errors": e.to_dict()})
        except Exception as e:
            await result.trace.aerror(
                f"[STAGE]: Error Handler:||{e.__class__.__name__}:||{e}||"
                f"{traceback.format_exc()}"
            )
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

    echo: StrOrNone = Field(
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
        result: Optional[Result] = None,
        event: Optional[Event] = None,
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
        message: str = (
            param2template(
                dedent(self.echo.strip("\n")), params, extras=self.extras
            )
            if self.echo
            else "..."
        )

        result.trace.info(f"[STAGE]: Message: ( {message} )")
        if self.sleep > 0:
            if self.sleep > 5:
                result.trace.info(f"[STAGE]: Sleep ... ({self.sleep} sec)")
            time.sleep(self.sleep)
        return result.catch(status=SUCCESS)

    async def axecute(
        self,
        params: DictData,
        *,
        result: Optional[Result] = None,
        event: Optional[Event] = None,
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

        message: str = (
            param2template(
                dedent(self.echo.strip("\n")), params, extras=self.extras
            )
            if self.echo
            else "..."
        )

        result.trace.info(f"[STAGE]: Message: ( {message} )")
        if self.sleep > 0:
            if self.sleep > 5:
                await result.trace.ainfo(
                    f"[STAGE]: Sleep ... ({self.sleep} sec)"
                )
            await asyncio.sleep(self.sleep)
        return result.catch(status=SUCCESS)


class BashStage(BaseAsyncStage):
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
    async def async_create_sh_file(
        self, bash: str, env: DictStr, run_id: StrOrNone = None
    ) -> AsyncIterator[TupleStr]:
        """Async create and write `.sh` file with the `aiofiles` package.

        :param bash: (str) A bash statement.
        :param env: (DictStr) An environment variable that set before run bash.
        :param run_id: (StrOrNone) A running stage ID that use for writing sh
            file instead generate by UUID4.

        :rtype: AsyncIterator[TupleStr]
        """
        import aiofiles

        f_name: str = f"{run_id or uuid.uuid4()}.sh"
        f_shebang: str = "bash" if sys.platform.startswith("win") else "sh"

        async with aiofiles.open(f"./{f_name}", mode="w", newline="\n") as f:
            # NOTE: write header of `.sh` file
            await f.write(f"#!/bin/{f_shebang}\n\n")

            # NOTE: add setting environment variable before bash skip statement.
            await f.writelines(pass_env([f"{k}='{env[k]}';\n" for k in env]))

            # NOTE: make sure that shell script file does not have `\r` char.
            await f.write("\n" + pass_env(bash.replace("\r\n", "\n")))

        # NOTE: Make this .sh file able to executable.
        make_exec(f"./{f_name}")

        yield f_shebang, f_name

        # Note: Remove .sh file that use to run bash.
        Path(f"./{f_name}").unlink()

    @contextlib.contextmanager
    def create_sh_file(
        self, bash: str, env: DictStr, run_id: StrOrNone = None
    ) -> Iterator[TupleStr]:
        """Create and write the `.sh` file before giving this file name to
        context. After that, it will auto delete this file automatic.

        :param bash: (str) A bash statement.
        :param env: (DictStr) An environment variable that set before run bash.
        :param run_id: (StrOrNone) A running stage ID that use for writing sh
            file instead generate by UUID4.

        :rtype: Iterator[TupleStr]
        :return: Return context of prepared bash statement that want to execute.
        """
        f_name: str = f"{run_id or uuid.uuid4()}.sh"
        f_shebang: str = "bash" if sys.platform.startswith("win") else "sh"

        with open(f"./{f_name}", mode="w", newline="\n") as f:
            # NOTE: write header of `.sh` file
            f.write(f"#!/bin/{f_shebang}\n\n")

            # NOTE: add setting environment variable before bash skip statement.
            f.writelines(pass_env([f"{k}='{env[k]}';\n" for k in env]))

            # NOTE: make sure that shell script file does not have `\r` char.
            f.write("\n" + pass_env(bash.replace("\r\n", "\n")))

        # NOTE: Make this .sh file able to executable.
        make_exec(f"./{f_name}")

        yield f_shebang, f_name

        # Note: Remove .sh file that use to run bash.
        Path(f"./{f_name}").unlink()

    def execute(
        self,
        params: DictData,
        *,
        result: Optional[Result] = None,
        event: Optional[Event] = None,
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
        bash: str = param2template(
            dedent(self.bash.strip("\n")), params, extras=self.extras
        )
        with self.create_sh_file(
            bash=bash,
            env=param2template(self.env, params, extras=self.extras),
            run_id=result.run_id,
        ) as sh:
            result.trace.debug(f"[STAGE]: Create `{sh[1]}` file.")
            rs: CompletedProcess = subprocess.run(
                sh,
                shell=False,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        if rs.returncode > 0:
            e: str = rs.stderr.removesuffix("\n")
            raise StageError(
                f"Subprocess: {e}\n---( statement )---\n```bash\n{bash}\n```"
            )
        return result.catch(
            status=SUCCESS,
            context={
                "return_code": rs.returncode,
                "stdout": None if (out := rs.stdout.strip("\n")) == "" else out,
                "stderr": None if (out := rs.stderr.strip("\n")) == "" else out,
            },
        )

    async def axecute(
        self,
        params: DictData,
        *,
        result: Optional[Result] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Async execution method for this Bash stage that only logging out to
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
        bash: str = param2template(
            dedent(self.bash.strip("\n")), params, extras=self.extras
        )
        async with self.async_create_sh_file(
            bash=bash,
            env=param2template(self.env, params, extras=self.extras),
            run_id=result.run_id,
        ) as sh:
            await result.trace.adebug(f"[STAGE]: Create `{sh[1]}` file.")
            rs: CompletedProcess = subprocess.run(
                sh,
                shell=False,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

        if rs.returncode > 0:
            e: str = rs.stderr.removesuffix("\n")
            raise StageError(
                f"Subprocess: {e}\n---( statement )---\n```bash\n{bash}\n```"
            )
        return result.catch(
            status=SUCCESS,
            context={
                "return_code": rs.returncode,
                "stdout": None if (out := rs.stdout.strip("\n")) == "" else out,
                "stderr": None if (out := rs.stderr.strip("\n")) == "" else out,
            },
        )


class PyStage(BaseAsyncStage):
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
        result: Optional[Result] = None,
        event: Optional[Event] = None,
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

        # WARNING: The exec build-in function is very dangerous. So, it
        #   should use the re module to validate exec-string before running.
        exec(
            pass_env(
                param2template(dedent(self.run), params, extras=self.extras)
            ),
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
        params: DictData,
        *,
        result: Optional[Result] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Async execution method for this Bash stage that only logging out to
        stdout.

        :param params: (DictData) A parameter data.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        References:
            - https://stackoverflow.com/questions/44859165/async-exec-in-python

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


class CallStage(BaseAsyncStage):
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
        result: Optional[Result] = None,
        event: Optional[Event] = None,
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
            f"[STAGE]: Caller Func: '{call_func.name}@{call_func.tag}'"
        )

        # VALIDATE: check input task caller parameters that exists before
        #   calling.
        args: DictData = {"result": result} | param2template(
            self.args, params, extras=self.extras
        )
        sig = inspect.signature(call_func)
        necessary_params: list[str] = []
        has_keyword: bool = False
        for k in sig.parameters:
            if (
                v := sig.parameters[k]
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

        if "result" not in sig.parameters and not has_keyword:
            args.pop("result")

        args = self.validate_model_args(call_func, args, result)
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
                f"Return type: '{call_func.name}@{call_func.tag}' can not "
                f"serialize, you must set return be `dict` or Pydantic "
                f"model."
            )
        return result.catch(status=SUCCESS, context=rs)

    async def axecute(
        self,
        params: DictData,
        *,
        result: Optional[Result] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Async execution method for this Bash stage that only logging out to
        stdout.

        :param params: (DictData) A parameter data.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        References:
            - https://stackoverflow.com/questions/44859165/async-exec-in-python

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

        await result.trace.ainfo(
            f"[STAGE]: Caller Func: '{call_func.name}@{call_func.tag}'"
        )

        # VALIDATE: check input task caller parameters that exists before
        #   calling.
        args: DictData = {"result": result} | param2template(
            self.args, params, extras=self.extras
        )
        sig = inspect.signature(call_func)
        necessary_params: list[str] = []
        has_keyword: bool = False
        for k in sig.parameters:
            if (
                v := sig.parameters[k]
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

        if "result" not in sig.parameters and not has_keyword:
            args.pop("result")

        args = self.validate_model_args(call_func, args, result)
        if inspect.iscoroutinefunction(call_func):
            rs: DictOrModel = await call_func(
                **param2template(args, params, extras=self.extras)
            )
        else:
            rs: DictOrModel = call_func(
                **param2template(args, params, extras=self.extras)
            )

        # VALIDATE:
        #   Check the result type from call function, it should be dict.
        if isinstance(rs, BaseModel):
            rs: DictData = rs.model_dump(by_alias=True)
        elif not isinstance(rs, dict):
            raise TypeError(
                f"Return type: '{call_func.name}@{call_func.tag}' can not "
                f"serialize, you must set return be `dict` or Pydantic "
                f"model."
            )
        return result.catch(status=SUCCESS, context=dump_all(rs, by_alias=True))

    @staticmethod
    def validate_model_args(
        func: TagFunc,
        args: DictData,
        result: Result,
    ) -> DictData:
        """Validate an input arguments before passing to the caller function.

        :param func: A tag function that want to get typing.
        :param args: An arguments before passing to this tag function.
        :param result: (Result) A result object for keeping context and status
            data.

        :rtype: DictData
        """
        try:
            model_instance = create_model_from_caller(func).model_validate(args)
            override = dict(model_instance)
            args.update(override)

            type_hints: dict[str, Any] = get_type_hints(func)
            for arg in type_hints:

                if arg == "return":
                    continue

                if arg.removeprefix("_") in args:
                    args[arg] = args.pop(arg.removeprefix("_"))
                    continue

            return args
        except ValidationError as e:
            raise StageError(
                "Validate argument from the caller function raise invalid type."
            ) from e
        except TypeError as e:
            result.trace.warning(
                f"[STAGE]: Get type hint raise TypeError: {e}, so, it skip "
                f"parsing model args process."
            )
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
        result: Optional[Result] = None,
        event: Optional[Event] = None,
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
        rs: Result = Workflow.from_conf(
            name=pass_env(_trigger),
            extras=self.extras | {"stage_raise_error": True},
        ).execute(
            params=param2template(self.params, params, extras=self.extras),
            run_id=None,
            parent_run_id=result.parent_run_id,
            event=event,
        )
        if rs.status == FAILED:
            err_msg: StrOrNone = (
                f" with:\n{msg}"
                if (msg := rs.context.get("errors", {}).get("message"))
                else "."
            )
            raise StageError(
                f"Trigger workflow return `FAILED` status{err_msg}"
            )
        return rs


class BaseNestedStage(BaseStage):
    """Base Nested Stage model. This model is use for checking the child stage
    is the nested stage or not.
    """

    @abstractmethod
    def execute(
        self,
        params: DictData,
        *,
        result: Optional[Result] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Execute abstraction method that action something by sub-model class.
        This is important method that make this class is able to be the nested
        stage.

        :param params: (DictData) A parameter data that want to use in this
            execution.
        :param result: (Result) A result object for keeping context and status
            data.
        :param event: (Event) An event manager that use to track parent execute
            was not force stopped.

        :rtype: Result
        """
        raise NotImplementedError(
            "Nested-Stage should implement `execute` method."
        )

    @property
    def is_nested(self) -> bool:
        """Check if this stage is a nested stage or not.

        :rtype: bool
        """
        return True


class ParallelStage(BaseNestedStage):
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
        event: Optional[Event] = None,
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
                result.catch(
                    status=CANCEL,
                    parallel={
                        branch: {
                            "branch": branch,
                            "stages": filter_func(output.pop("stages", {})),
                            "errors": StageError(error_msg).to_dict(),
                        }
                    },
                )
                raise StageError(error_msg, refs=branch)

            try:
                rs: Result = stage.handler_execute(
                    params=context,
                    run_id=result.run_id,
                    parent_run_id=result.parent_run_id,
                    event=event,
                )
                stage.set_outputs(rs.context, to=output)
                stage.set_outputs(stage.get_outputs(output), to=context)
            except StageError as e:
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
                raise StageError(str(e), refs=branch) from e

            if rs.status == FAILED:  # pragma: no cov
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
                            "errors": StageError(error_msg).to_dict(),
                        },
                    },
                )
                raise StageError(error_msg, refs=branch)

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
        result: Optional[Result] = None,
        event: Optional[Event] = None,
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
        event: Event = event or Event()
        result.trace.info(f"[STAGE]: Parallel with {self.max_workers} workers.")
        result.catch(status=WAIT, context={"parallel": {}})
        if event and event.is_set():
            return result.catch(
                status=CANCEL,
                context={
                    "errors": StageError(
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

            futures: list[Future] = [
                executor.submit(
                    self.execute_branch,
                    branch=branch,
                    params=params,
                    result=result,
                    event=event,
                )
                for branch in self.parallel
            ]

            for future in as_completed(futures):
                try:
                    future.result()
                except StageError as e:
                    status = FAILED
                    if "errors" in context:
                        context["errors"][e.refs] = e.to_dict()
                    else:
                        context["errors"] = e.to_dict(with_refs=True)
        return result.catch(status=status, context=context)


class ForEachStage(BaseNestedStage):
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
    use_index_as_key: bool = Field(
        default=False,
        description=(
            "A flag for using the loop index as a key instead item value. "
            "This flag allow to skip checking duplicate item step."
        ),
    )

    def execute_item(
        self,
        index: int,
        item: StrOrInt,
        params: DictData,
        result: Result,
        *,
        event: Optional[Event] = None,
    ) -> Result:
        """Execute all nested stage that set on this stage with specific foreach
        item parameter.

        :param index: (int) An index value of foreach loop.
        :param item: (str | int) An item that want to execution.
        :param params: (DictData) A parameter data.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :raise StageError: If event was set.
        :raise StageError: If the stage execution raise any Exception error.
        :raise StageError: If the result from execution has `FAILED` status.

        :rtype: Result
        """
        result.trace.debug(f"[STAGE]: Execute Item: {item!r}")
        key: StrOrInt = index if self.use_index_as_key else item
        context: DictData = copy.deepcopy(params)
        context.update({"item": item, "loop": index})
        output: DictData = {"item": item, "stages": {}}
        for stage in self.stages:

            if self.extras:
                stage.extras = self.extras

            if stage.is_skipped(params=context):
                result.trace.info(f"[STAGE]: Skip stage: {stage.iden!r}")
                stage.set_outputs(output={"skipped": True}, to=output)
                continue

            if event and event.is_set():
                error_msg: str = (
                    "Item-Stage was canceled because event was set."
                )
                result.catch(
                    status=CANCEL,
                    foreach={
                        key: {
                            "item": item,
                            "stages": filter_func(output.pop("stages", {})),
                            "errors": StageError(error_msg).to_dict(),
                        }
                    },
                )
                raise StageError(error_msg, refs=key)

            try:
                rs: Result = stage.handler_execute(
                    params=context,
                    run_id=result.run_id,
                    parent_run_id=result.parent_run_id,
                    event=event,
                )
                stage.set_outputs(rs.context, to=output)
                stage.set_outputs(stage.get_outputs(output), to=context)
            except StageError as e:
                result.catch(
                    status=FAILED,
                    foreach={
                        key: {
                            "item": item,
                            "stages": filter_func(output.pop("stages", {})),
                            "errors": e.to_dict(),
                        },
                    },
                )
                raise StageError(str(e), refs=key) from e

            if rs.status == FAILED:  # pragma: no cov
                error_msg: str = (
                    f"Item-Stage was break because it has a sub stage, "
                    f"{stage.iden}, failed without raise error."
                )
                result.trace.warning(f"[STAGE]: {error_msg}")
                result.catch(
                    status=FAILED,
                    foreach={
                        key: {
                            "item": item,
                            "stages": filter_func(output.pop("stages", {})),
                            "errors": StageError(error_msg).to_dict(),
                        },
                    },
                )
                raise StageError(error_msg, refs=key)

        return result.catch(
            status=SUCCESS,
            foreach={
                key: {
                    "item": item,
                    "stages": filter_func(output.pop("stages", {})),
                },
            },
        )

    def execute(
        self,
        params: DictData,
        *,
        result: Optional[Result] = None,
        event: Optional[Event] = None,
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
        event: Event = event or Event()
        foreach: Union[list[str], list[int]] = (
            param2template(self.foreach, params, extras=self.extras)
            if isinstance(self.foreach, str)
            else self.foreach
        )

        # [VALIDATE]: Type of the foreach should be `list` type.
        if not isinstance(foreach, list):
            raise TypeError(f"Does not support foreach: {foreach!r}")
        elif len(set(foreach)) != len(foreach) and not self.use_index_as_key:
            raise ValueError(
                "Foreach item should not duplicate. If this stage must to pass "
                "duplicate item, it should set `use_index_as_key: true`."
            )

        result.trace.info(f"[STAGE]: Foreach: {foreach!r}.")
        result.catch(status=WAIT, context={"items": foreach, "foreach": {}})
        if event and event.is_set():
            return result.catch(
                status=CANCEL,
                context={
                    "errors": StageError(
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
                    index=i,
                    item=item,
                    params=params,
                    result=result,
                    event=event,
                )
                for i, item in enumerate(foreach, start=0)
            ]
            context: DictData = {}
            status: Status = SUCCESS

            done, not_done = wait(futures, return_when=FIRST_EXCEPTION)
            if len(list(done)) != len(futures):
                result.trace.warning(
                    "[STAGE]: Set event for stop pending for-each stage."
                )
                event.set()
                for future in not_done:
                    future.cancel()
                time.sleep(0.075)

                nd: str = (
                    (
                        f", {len(not_done)} item"
                        f"{'s' if len(not_done) > 1 else ''} not run!!!"
                    )
                    if not_done
                    else ""
                )
                result.trace.debug(
                    f"[STAGE]: ... Foreach-Stage set failed event{nd}"
                )
                done: Iterator[Future] = as_completed(futures)

            for future in done:
                try:
                    future.result()
                except StageError as e:
                    status = FAILED
                    if "errors" in context:
                        context["errors"][e.refs] = e.to_dict()
                    else:
                        context["errors"] = e.to_dict(with_refs=True)
                except CancelledError:
                    pass
        return result.catch(status=status, context=context)


class UntilStage(BaseNestedStage):
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
        ...             "run": (
        ...                 "item = ${{ item }}\\n"
        ...                 "item += 1\\n"
        ...             )
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
        event: Optional[Event] = None,
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
                                "errors": StageError(error_msg).to_dict(),
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
                    event=event,
                )
                stage.set_outputs(rs.context, to=output)

                if "item" in (_output := stage.get_outputs(output)):
                    next_item = _output["item"]

                stage.set_outputs(_output, to=context)
            except StageError as e:
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
                            "errors": StageError(error_msg).to_dict(),
                        }
                    },
                )
                raise StageError(error_msg)

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
        result: Optional[Result] = None,
        event: Optional[Event] = None,
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

        result.trace.info(f"[STAGE]: Until: {self.until}")
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
                        "errors": StageError(
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
                raise StageError(
                    "Return type of until condition not be `boolean`, getting"
                    f": {next_track!r}"
                )
            track: bool = not next_track
            delay(0.025)

        if exceed_loop:
            raise StageError(f"The until loop was exceed {self.max_loop} loops")
        return result.catch(status=SUCCESS)


class Match(BaseModel):
    """Match model for the Case Stage."""

    case: StrOrInt = Field(description="A match case.")
    stages: list[Stage] = Field(
        description="A list of stage to execution for this case."
    )


class CaseStage(BaseNestedStage):
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
        event: Optional[Event] = None,
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

            if event and event.is_set():
                error_msg: str = (
                    "Case-Stage was canceled from event that had set before "
                    "stage case execution."
                )
                return result.catch(
                    status=CANCEL,
                    context={
                        "case": case,
                        "stages": filter_func(output.pop("stages", {})),
                        "errors": StageError(error_msg).to_dict(),
                    },
                )

            try:
                rs: Result = stage.handler_execute(
                    params=context,
                    run_id=result.run_id,
                    parent_run_id=result.parent_run_id,
                    event=event,
                )
                stage.set_outputs(rs.context, to=output)
                stage.set_outputs(stage.get_outputs(output), to=context)
            except StageError as e:
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
                        "errors": StageError(error_msg).to_dict(),
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
        result: Optional[Result] = None,
        event: Optional[Event] = None,
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

        _case: StrOrNone = param2template(self.case, params, extras=self.extras)

        result.trace.info(f"[STAGE]: Case: {_case!r}.")
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
                    raise StageError(
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
                    context={"errors": StageError(error_msg).to_dict()},
                )
            _case: str = "_"
            stages: list[Stage] = _else.stages

        if event and event.is_set():
            return result.catch(
                status=CANCEL,
                context={
                    "errors": StageError(
                        "Stage was canceled from event that had set before "
                        "case-stage execution."
                    ).to_dict()
                },
            )

        return self.execute_case(
            case=_case, stages=stages, params=params, result=result, event=event
        )


class RaiseStage(BaseAsyncStage):
    """Raise error stage executor that raise `StageError` that use a message
    field for making error message before raise.

    Data Validate:
        >>> stage = {
        ...     "name": "Raise stage",
        ...     "raise": "raise this stage",
        ... }

    """

    message: str = Field(
        description=(
            "An error message that want to raise with `StageError` class"
        ),
        alias="raise",
    )

    def execute(
        self,
        params: DictData,
        *,
        result: Optional[Result] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Raise the StageError object with the message field execution.

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
        result.trace.info(f"[STAGE]: Message: ( {message} )")
        raise StageError(message)

    async def axecute(
        self,
        params: DictData,
        *,
        result: Optional[Result] = None,
        event: Optional[Event] = None,
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
        result: Result = result or Result(
            run_id=gen_id(self.name + (self.id or ""), unique=True),
            extras=self.extras,
        )
        message: str = param2template(self.message, params, extras=self.extras)
        await result.trace.ainfo(f"[STAGE]: Execute Raise-Stage: ( {message} )")
        raise StageError(message)


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
            "An environment variable that want pass to Docker container."
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
        event: Optional[Event] = None,
    ) -> Result:
        """Execute Docker container task.

        :param params: (DictData) A parameter data.
        :param result: (Result) A Result instance for return context and status.
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :rtype: Result
        """
        try:
            from docker import DockerClient
            from docker.errors import ContainerError
        except ImportError:
            raise ImportError(
                "Docker stage need the docker package, you should install it "
                "by `pip install docker` first."
            ) from None

        client = DockerClient(
            base_url="unix://var/run/docker.sock", version="auto"
        )

        resp = client.api.pull(
            repository=pass_env(self.image),
            tag=pass_env(self.tag),
            auth_config=pass_env(
                param2template(self.auth, params, extras=self.extras)
            ),
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
                context={"errors": StageError(error_msg).to_dict()},
            )

        unique_image_name: str = f"{self.image}_{datetime.now():%Y%m%d%H%M%S%f}"
        container = client.containers.run(
            image=pass_env(f"{self.image}:{self.tag}"),
            name=unique_image_name,
            environment=pass_env(self.env),
            volumes=pass_env(
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
                out.decode("utf-8"),
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
        result: Optional[Result] = None,
        event: Optional[Event] = None,
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

        result.trace.info(f"[STAGE]: Docker: {self.image}:{self.tag}")
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
        run_id: StrOrNone = None,
    ) -> Iterator[str]:
        """Create the `.py` file and write an input Python statement and its
        Python dependency on the header of this file.

            The format of Python dependency was followed by the `uv`
        recommended.

        :param py: A Python string statement.
        :param values: A variable that want to set before running this
        :param deps: An additional Python dependencies that want install before
            run this python stage.
        :param run_id: (StrOrNone) A running ID of this stage execution.
        """
        run_id: str = run_id or uuid.uuid4()
        f_name: str = f"{run_id}.py"
        with open(f"./{f_name}", mode="w", newline="\n") as f:
            # NOTE: Create variable mapping that write before running statement.
            vars_str: str = pass_env(
                "\n ".join(
                    f"{var} = {value!r}" for var, value in values.items()
                )
            )

            # NOTE: `uv` supports PEP 723 — inline TOML metadata.
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
            f.write("\n" + pass_env(py.replace("\r\n", "\n")))

        # NOTE: Make this .py file able to executable.
        make_exec(f"./{f_name}")

        yield f_name

        # Note: Remove .py file that use to run Python.
        Path(f"./{f_name}").unlink()

    def execute(
        self,
        params: DictData,
        *,
        result: Optional[Result] = None,
        event: Optional[Event] = None,
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
        run: str = param2template(dedent(self.run), params, extras=self.extras)
        with self.create_py_file(
            py=run,
            values=param2template(self.vars, params, extras=self.extras),
            deps=param2template(self.deps, params, extras=self.extras),
            run_id=result.run_id,
        ) as py:
            result.trace.debug(f"[STAGE]: Create `{py}` file.")
            rs: CompletedProcess = subprocess.run(
                ["python", "-m", "uv", "run", py, "--no-cache"],
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
            raise StageError(
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
    Field(
        union_mode="smart",
        description="A stage models that already implemented on this package.",
    ),
]  # pragma: no cov
