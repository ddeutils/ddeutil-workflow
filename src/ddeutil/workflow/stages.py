# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
r"""Stages module include all stage model that implemented to be the minimum execution
layer of this workflow core engine. The stage handle the minimize task that run
in a thread (same thread at its job owner) that mean it is the lowest executor that
you can track logs.

    The output of stage execution only return SUCCESS or CANCEL status because
I do not want to handle stage error on this stage execution. I think stage model
have a lot of use-case, and it should does not worry about it error output.

    So, I will create `execute` for any exception class that raise from
the stage execution method.

    Handler     --> Ok      --> Result
                                        |-status: SUCCESS
                                        ╰-context:
                                            ╰-outputs: ...

                --> Ok      --> Result
                                ╰-status: CANCEL

                --> Ok      --> Result
                                ╰-status: SKIP

                --> Ok      --> Result
                                |-status: FAILED
                                ╰-errors:
                                    |-name: ...
                                    ╰-message: ...

    On the context I/O that pass to a stage object at execute step. The
execute method receives a `params={"params": {...}}` value for passing template
searching.

    All stages model inherit from `BaseStage` or `AsyncBaseStage` models that has the
base fields:

| field     | alias | data type   | default  | description                                                           |
|-----------|-------|-------------|:--------:|-----------------------------------------------------------------------|
| id        |       | str \| None |  `None`  | A stage ID that use to keep execution output or getting by job owner. |
| name      |       | str         |          | A stage name that want to log when start execution.               |
| condition | if    | str \| None |  `None`  | A stage condition statement to allow stage executable.                |
| extras    |       | dict        | `dict()` | An extra parameter that override core config values.                  |

    It has a special base class is `BaseRetryStage` that inherit from `AsyncBaseStage`
that use to handle retry execution when it got any error with `retry` field.
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
from typing import (
    Annotated,
    Any,
    Callable,
    Optional,
    TypeVar,
    Union,
    get_type_hints,
)

from ddeutil.core import str2list
from pydantic import BaseModel, Field, ValidationError
from pydantic.functional_validators import field_validator, model_validator
from typing_extensions import Self

from .__types import DictData, DictStr, StrOrInt, StrOrNone, TupleStr
from .conf import dynamic, pass_env
from .errors import StageCancelError, StageError, StageSkipError, to_dict
from .result import (
    CANCEL,
    FAILED,
    SKIP,
    SUCCESS,
    WAIT,
    Result,
    Status,
    catch,
    get_status_from_error,
    validate_statuses,
)
from .reusables import (
    TagFunc,
    create_model_from_caller,
    extract_call,
    not_in_template,
    param2template,
)
from .traces import TraceManager, get_trace
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
    """Abstract base class for all stage implementations.

    BaseStage provides the foundation for all stage types in the workflow system.
    It defines the common interface and metadata fields that all stages must
    implement, ensuring consistent behavior across different stage types.

    This abstract class handles core stage functionality including:
    - Stage identification and naming
    - Conditional execution logic
    - Output management and templating
    - Execution lifecycle management

    Custom stages should inherit from this class and implement the abstract
    `process()` method to define their specific execution behavior.

    Attributes:
        extras (dict): Additional configuration parameters
        id (str, optional): Unique stage identifier for output reference
        name (str): Human-readable stage name for logging
        desc (str, optional): Stage description for documentation
        condition (str, optional): Conditional expression for execution

    Abstract Methods:
        process: Main execution logic that must be implemented by subclasses

    Example:
        ```python
        class CustomStage(BaseStage):
            custom_param: str = Field(description="Custom parameter")

            def process(self, params: dict, **kwargs) -> Result:
                # Custom execution logic
                return Result(status=SUCCESS)
        ```
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
    condition: Optional[Union[str, bool]] = Field(
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

        Returns:
            str: Return an identity of this stage for making output.
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
    def process(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Process abstraction method that action something by sub-model class.
        This is important method that make this class is able to be the stage.

        Args:
            params: A parameter data that want to use in this
                execution.
            run_id: A running stage ID.
            context: A context data.
            parent_run_id: A parent running ID. (Default is None)
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The execution result with status and context data.
        """
        raise NotImplementedError("Stage should implement `process` method.")

    def execute(
        self,
        params: DictData,
        *,
        run_id: StrOrNone = None,
        event: Optional[Event] = None,
    ) -> Union[Result, DictData]:
        """Handler stage execution result from the stage `process` method.

            This handler strategy will catch and mapping message to the result
        context data before returning. All possible status that will return from
        this method be:

            Handler     --> Ok      --> Result
                                        |-status: SUCCESS
                                        ╰-context:
                                            ╰-outputs: ...

                        --> Ok      --> Result
                                        ╰-status: CANCEL

                        --> Ok      --> Result
                                        ╰-status: SKIP

                        --> Ok      --> Result
                                        |-status: FAILED
                                        ╰-errors:
                                            |-name: ...
                                            ╰-message: ...

            On the last step, it will set the running ID on a return result
        object from the current stage ID before release the final result.

        Args:
            params: A parameter data.
            run_id: A running stage ID. (Default is None)
            event: An event manager that pass to the stage execution.
                (Default is None)

        Returns:
            Result: The execution result with updated status and context.
        """
        ts: float = time.monotonic()
        parent_run_id: str = run_id
        run_id: str = run_id or gen_id(self.iden, unique=True)
        context: DictData = {"status": WAIT}
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        try:
            _id: str = (
                f" with ID: {param2template(self.id, params=params)!r}"
                if self.id
                else ""
            )
            trace.info(
                f"[STAGE]: Handler {to_train(self.__class__.__name__)}: "
                f"{self.name!r}{_id}."
            )

            # NOTE: Show the description of this stage before execution.
            if self.desc:
                trace.debug(f"[STAGE]: Description:||{self.desc}||")

            # VALIDATE: Checking stage condition before execution.
            if self.is_skipped(params):
                raise StageSkipError(
                    f"Skip because condition {self.condition} was valid."
                )

            # NOTE: Start call wrapped execution method that will use custom
            #   execution before the real execution from inherit stage model.
            result_caught: Result = self._execute(
                params,
                run_id=run_id,
                context=context,
                parent_run_id=parent_run_id,
                event=event,
            )
            if result_caught.status == WAIT:  # pragma: no cov
                raise StageError(
                    "Status from execution should not return waiting status."
                )
            return result_caught.make_info(
                {"execution_time": time.monotonic() - ts}
            )

        # NOTE: Catch this error in this line because the execution can raise
        #   this exception class at other location.
        except (
            StageSkipError,
            StageCancelError,
            StageError,
        ) as e:  # pragma: no cov
            trace.info(
                f"[STAGE]: Handler:||{e.__class__.__name__}: {e}||"
                f"{traceback.format_exc()}"
            )
            st: Status = get_status_from_error(e)
            return Result(
                run_id=run_id,
                parent_run_id=parent_run_id,
                status=st,
                context=catch(
                    context,
                    status=st,
                    updated=(
                        None
                        if isinstance(e, StageSkipError)
                        else {"errors": e.to_dict()}
                    ),
                ),
                info={"execution_time": time.monotonic() - ts},
                extras=self.extras,
            )
        except Exception as e:
            trace.error(
                f"[STAGE]: Error Handler:||{e.__class__.__name__}: {e}||"
                f"{traceback.format_exc()}"
            )
            return Result(
                run_id=run_id,
                parent_run_id=parent_run_id,
                status=FAILED,
                context=catch(
                    context, status=FAILED, updated={"errors": to_dict(e)}
                ),
                info={"execution_time": time.monotonic() - ts},
                extras=self.extras,
            )

    def _execute(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Wrapped the process method before returning to handler execution.

        Args:
            params: A parameter data that want to use in this
                execution.
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The wrapped execution result.
        """
        catch(context, status=WAIT)
        return self.process(
            params,
            run_id=run_id,
            context=context,
            parent_run_id=parent_run_id,
            event=event,
        )

    def set_outputs(
        self,
        output: DictData,
        to: DictData,
        **kwargs,
    ) -> DictData:
        """Set an outputs from execution result context to the received context
        with a `to` input parameter. The result context from stage execution
        will be set with `outputs` key in this stage ID key.

            For example of setting output method, If you receive process output
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

        Args:
            output: (DictData) A result data context that want to extract
                and transfer to the `outputs` key in receive context.
            to: (DictData) A received context data.
            kwargs: Any values that want to add to the target context.

        Returns:
            DictData: Return updated the target context with a result context.
        """
        if "stages" not in to:
            to["stages"] = {}

        if self.id is None and not dynamic(
            "stage_default_id", extras=self.extras
        ):
            return to

        _id: str = self.gen_id(params=to)
        output: DictData = copy.deepcopy(output)
        errors: DictData = (
            {"errors": output.pop("errors")} if "errors" in output else {}
        )
        status: dict[str, Status] = (
            {"status": output.pop("status")} if "status" in output else {}
        )
        kwargs: DictData = kwargs or {}
        to["stages"][_id] = {"outputs": output} | errors | status | kwargs
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
        # NOTE: Support for condition value is empty string.
        if not self.condition:
            return False

        if isinstance(self.condition, bool):
            return self.condition

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

        :param params: (DictData) A parameter or context data.

        :rtype: str
        """
        return (
            param2template(self.id, params=params, extras=self.extras)
            if self.id
            else gen_id(
                # NOTE: The name should be non-sensitive case for uniqueness.
                param2template(self.name, params=params, extras=self.extras)
            )
        )

    @property
    def is_nested(self) -> bool:
        """Return true if this stage is nested stage.

        :rtype: bool
        """
        return False

    def docs(self) -> str:  # pragma: no cov
        """Return generated document that will be the interface of this stage.

        :rtype: str
        """
        return self.desc


class BaseAsyncStage(BaseStage, ABC):
    """Base Async Stage model to make any stage model allow async execution for
    optimize CPU and Memory on the current node. If you want to implement any
    custom async stage, you can inherit this class and implement
    `self.axecute()` (async + execute = axecute) method only.

        This class is the abstraction class for any inherit asyncable stage
    model.
    """

    @abstractmethod
    async def async_process(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Async execution method for this Empty stage that only logging out to
        stdout.

        Args:
            params: A parameter data that want to use in this
                execution.
            run_id: A running stage ID.
            context: A context data.
            parent_run_id: A parent running ID. (Default is None)
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The execution result with status and context data.
        """
        raise NotImplementedError(
            "Async Stage should implement `axecute` method."
        )

    async def axecute(
        self,
        params: DictData,
        *,
        run_id: StrOrNone = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Async Handler stage execution result from the stage `execute` method.

        Args:
            params: A parameter data that want to use in this
                execution.
            run_id: A running stage ID. (Default is None)
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The execution result with status and context data.
        """
        ts: float = time.monotonic()
        parent_run_id: StrOrNone = run_id
        run_id: str = run_id or gen_id(self.iden, unique=True)
        context: DictData = {}
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        try:
            _id: str = (
                f" with ID: {param2template(self.id, params=params)!r}"
                if self.id
                else ""
            )
            await trace.ainfo(
                f"[STAGE]: Handler {to_train(self.__class__.__name__)}: "
                f"{self.name!r}{_id}."
            )

            # NOTE: Show the description of this stage before execution.
            if self.desc:
                await trace.adebug(f"[STAGE]: Description:||{self.desc}||")

            # VALIDATE: Checking stage condition before execution.
            if self.is_skipped(params=params):
                raise StageSkipError(
                    f"Skip because condition {self.condition} was valid."
                )

            # NOTE: Start call wrapped execution method that will use custom
            #   execution before the real execution from inherit stage model.
            result_caught: Result = await self._axecute(
                params,
                run_id=run_id,
                context=context,
                parent_run_id=parent_run_id,
                event=event,
            )
            if result_caught.status == WAIT:  # pragma: no cov
                raise StageError(
                    "Status from execution should not return waiting status."
                )
            return result_caught

        # NOTE: Catch this error in this line because the execution can raise
        #   this exception class at other location.
        except (
            StageSkipError,
            StageCancelError,
            StageError,
        ) as e:  # pragma: no cov
            await trace.ainfo(
                f"[STAGE]: Skip Handler:||{e.__class__.__name__}: {e}||"
                f"{traceback.format_exc()}"
            )
            st: Status = get_status_from_error(e)
            return Result(
                run_id=run_id,
                parent_run_id=parent_run_id,
                status=st,
                context=catch(
                    context,
                    status=st,
                    updated=(
                        None
                        if isinstance(e, StageSkipError)
                        else {"status": st, "errors": e.to_dict()}
                    ),
                ),
                info={"execution_time": time.monotonic() - ts},
                extras=self.extras,
            )
        except Exception as e:
            await trace.aerror(
                f"[STAGE]: Error Handler:||{e.__class__.__name__}: {e}||"
                f"{traceback.format_exc()}"
            )
            return Result(
                run_id=run_id,
                parent_run_id=parent_run_id,
                status=FAILED,
                context=catch(
                    context, status=FAILED, updated={"errors": to_dict(e)}
                ),
                info={"execution_time": time.monotonic() - ts},
                extras=self.extras,
            )

    async def _axecute(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Wrapped the axecute method before returning to handler axecute.

        :param params: (DictData) A parameter data that want to use in this
            execution.
        :param event: (Event) An event manager that use to track parent execute
            was not force stopped.

        :rtype: Result
        """
        catch(context, status=WAIT)
        return await self.async_process(
            params,
            run_id=run_id,
            context=context,
            parent_run_id=parent_run_id,
            event=event,
        )


class BaseRetryStage(BaseAsyncStage, ABC):  # pragma: no cov
    """Base Retry Stage model that will execute again when it raises with the
    `StageRetryError`.
    """

    retry: int = Field(
        default=0,
        ge=0,
        lt=20,
        description="A retry number if stage execution get the error.",
    )

    def _execute(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Wrapped the execute method with retry strategy before returning to
        handler execute.

        :param params: (DictData) A parameter data that want to use in this
            execution.
        :param event: (Event) An event manager that use to track parent execute
            was not force stopped.

        :rtype: Result
        """
        current_retry: int = 0
        exception: Exception
        catch(context, status=WAIT)
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )

        # NOTE: First execution for not pass to retry step if it passes.
        try:
            return self.process(
                params | {"retry": current_retry},
                run_id=run_id,
                context=context,
                parent_run_id=parent_run_id,
                event=event,
            )
        except Exception as e:
            current_retry += 1
            exception = e

        if self.retry == 0:
            raise exception

        trace.warning(
            f"[STAGE]: Retry count: {current_retry} ... "
            f"( {exception.__class__.__name__} )"
        )

        while current_retry < (self.retry + 1):
            try:
                catch(
                    context=context,
                    status=WAIT,
                    updated={"retry": current_retry},
                )
                return self.process(
                    params | {"retry": current_retry},
                    run_id=run_id,
                    context=context,
                    parent_run_id=parent_run_id,
                    event=event,
                )
            except Exception as e:
                current_retry += 1
                trace.warning(
                    f"[STAGE]: Retry count: {current_retry} ... "
                    f"( {e.__class__.__name__} )"
                )
                exception = e

        trace.error(
            f"[STAGE]: Reach the maximum of retry number: {self.retry}."
        )
        raise exception

    async def _axecute(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Wrapped the axecute method with retry strategy before returning to
        handler axecute.

        :param params: (DictData) A parameter data that want to use in this
            execution.
        :param event: (Event) An event manager that use to track parent execute
            was not force stopped.

        :rtype: Result
        """
        current_retry: int = 0
        exception: Exception
        catch(context, status=WAIT)
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )

        # NOTE: First execution for not pass to retry step if it passes.
        try:
            return await self.async_process(
                params | {"retry": current_retry},
                run_id=run_id,
                context=context,
                parent_run_id=parent_run_id,
                event=event,
            )
        except Exception as e:
            current_retry += 1
            exception = e

        if self.retry == 0:
            raise exception

        await trace.awarning(
            f"[STAGE]: Retry count: {current_retry} ... "
            f"( {exception.__class__.__name__} )"
        )

        while current_retry < (self.retry + 1):
            try:
                catch(
                    context=context,
                    status=WAIT,
                    updated={"retry": current_retry},
                )
                return await self.async_process(
                    params | {"retry": current_retry},
                    run_id=run_id,
                    context=context,
                    parent_run_id=parent_run_id,
                    event=event,
                )
            except Exception as e:
                current_retry += 1
                await trace.awarning(
                    f"[STAGE]: Retry count: {current_retry} ... "
                    f"( {e.__class__.__name__} )"
                )
                exception = e

        await trace.aerror(
            f"[STAGE]: Reach the maximum of retry number: {self.retry}."
        )
        raise exception


class EmptyStage(BaseAsyncStage):
    """Empty stage for logging and debugging workflows.

    EmptyStage is a utility stage that performs no actual work but provides
    logging output and optional delays. It's commonly used for:
    - Debugging workflow execution flow
    - Adding informational messages to workflows
    - Creating delays between stages
    - Testing template parameter resolution

    The stage outputs the echo message to stdout and can optionally sleep
    for a specified duration, making it useful for workflow timing control
    and debugging scenarios.

    Attributes:
        echo (str, optional): Message to display during execution
        sleep (float): Duration to sleep after logging (0-1800 seconds)

    Example:
        ```yaml
        stages:
          - name: "Workflow Started"
            echo: "Beginning data processing workflow"
            sleep: 2

          - name: "Debug Parameters"
            echo: "Processing file: ${{ params.filename }}"
        ```

        ```python
        stage = EmptyStage(
            name="Status Update",
            echo="Processing completed successfully",
            sleep=1.0
        )
        ```
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

    def process(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Execution method for the Empty stage that do only logging out to
        stdout.

            The result context should be empty and do not process anything
        without calling logging function.

        Args:
            params: A parameter data that want to use in this
                execution.
            run_id: A running stage ID.
            context: A context data.
            parent_run_id: A parent running ID. (Default is None)
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The execution result with status and context data.
        """
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        message: str = (
            param2template(
                dedent(self.echo.strip("\n")), params, extras=self.extras
            )
            if self.echo
            else "..."
        )

        if event and event.is_set():
            raise StageCancelError(
                "Execution was canceled from the event before start parallel."
            )

        trace.info(f"[STAGE]: Message: ( {message} )")
        if self.sleep > 0:
            if self.sleep > 5:
                trace.info(f"[STAGE]: Sleep ... ({self.sleep} sec)")
            time.sleep(self.sleep)
        return Result(
            run_id=run_id,
            parent_run_id=parent_run_id,
            status=SUCCESS,
            context=catch(context=context, status=SUCCESS),
            extras=self.extras,
        )

    async def async_process(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Async execution method for this Empty stage that only logging out to
        stdout.

        Args:
            params: A parameter data that want to use in this
                execution.
            run_id: A running stage ID.
            context: A context data.
            parent_run_id: A parent running ID. (Default is None)
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The execution result with status and context data.
        """
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        message: str = (
            param2template(
                dedent(self.echo.strip("\n")), params, extras=self.extras
            )
            if self.echo
            else "..."
        )

        if event and event.is_set():
            raise StageCancelError(
                "Execution was canceled from the event before start parallel."
            )

        trace.info(f"[STAGE]: Message: ( {message} )")
        if self.sleep > 0:
            if self.sleep > 5:
                await trace.ainfo(f"[STAGE]: Sleep ... ({self.sleep} sec)")
            await asyncio.sleep(self.sleep)
        return Result(
            run_id=run_id,
            parent_run_id=parent_run_id,
            status=SUCCESS,
            context=catch(context=context, status=SUCCESS),
            extras=self.extras,
        )


class BashStage(BaseRetryStage):
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

    @staticmethod
    def prepare_std(value: str) -> Optional[str]:
        """Prepare returned standard string from subprocess."""
        return None if (out := value.strip("\n")) == "" else out

    def process(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Execute bash statement with the Python build-in `subprocess` package.
        It will catch result from the `subprocess.run` returning output like
        `return_code`, `stdout`, and `stderr`.

        Args:
            params: A parameter data that want to use in this
                execution.
            run_id: A running stage ID.
            context: A context data.
            parent_run_id: A parent running ID. (Default is None)
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The execution result with status and context data.
        """
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        bash: str = param2template(
            dedent(self.bash.strip("\n")), params, extras=self.extras
        )
        with self.create_sh_file(
            bash=bash,
            env=param2template(self.env, params, extras=self.extras),
            run_id=run_id,
        ) as sh:
            trace.debug(f"[STAGE]: Create `{sh[1]}` file.")
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
            e_bash: str = bash.replace("\n", "\n\t")
            raise StageError(f"Subprocess: {e}\n\t```bash\n\t{e_bash}\n\t```")
        return Result(
            run_id=run_id,
            parent_run_id=parent_run_id,
            status=SUCCESS,
            context=catch(
                context=context,
                status=SUCCESS,
                updated={
                    "return_code": rs.returncode,
                    "stdout": self.prepare_std(rs.stdout),
                    "stderr": self.prepare_std(rs.stderr),
                },
            ),
            extras=self.extras,
        )

    async def async_process(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Async execution method for this Bash stage that only logging out to
        stdout.

        Args:
            params: A parameter data that want to use in this
                execution.
            run_id: A running stage ID.
            context: A context data.
            parent_run_id: A parent running ID. (Default is None)
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The execution result with status and context data.
        """
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        bash: str = param2template(
            dedent(self.bash.strip("\n")), params, extras=self.extras
        )
        async with self.async_create_sh_file(
            bash=bash,
            env=param2template(self.env, params, extras=self.extras),
            run_id=run_id,
        ) as sh:
            await trace.adebug(f"[STAGE]: Create `{sh[1]}` file.")
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
            e_bash: str = bash.replace("\n", "\n\t")
            raise StageError(f"Subprocess: {e}\n\t```bash\n\t{e_bash}\n\t```")
        return Result(
            run_id=run_id,
            parent_run_id=parent_run_id,
            status=SUCCESS,
            context=catch(
                context=context,
                status=SUCCESS,
                updated={
                    "return_code": rs.returncode,
                    "stdout": self.prepare_std(rs.stdout),
                    "stderr": self.prepare_std(rs.stderr),
                },
            ),
            extras=self.extras,
        )


class PyStage(BaseRetryStage):
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

    def set_outputs(
        self, output: DictData, to: DictData, info: Optional[DictData] = None
    ) -> DictData:
        """Override set an outputs method for the Python execution process that
        extract output from all the locals values.

        :param output: (DictData) An output data that want to extract to an
            output key.
        :param to: (DictData) A context data that want to add output result.
        :param info: (DictData)

        :rtype: DictData
        """
        output: DictData = output.copy()
        lc: DictData = output.pop("locals", {})
        gb: DictData = output.pop("globals", {})
        super().set_outputs(lc | output, to=to)
        to.update({k: gb[k] for k in to if k in gb})
        return to

    def process(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Execute the Python statement that pass all globals and input params
        to globals argument on `exec` build-in function.

        Args:
            params: A parameter data that want to use in this
                execution.
            run_id: A running stage ID.
            context: A context data.
            parent_run_id: A parent running ID. (Default is None)
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The execution result with status and context data.
        """
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        trace.info("[STAGE]: Prepare `globals` and `locals` variables.")
        lc: DictData = {}
        gb: DictData = (
            globals()
            | param2template(self.vars, params, extras=self.extras)
            | {
                "result": Result(
                    run_id=run_id,
                    parent_run_id=parent_run_id,
                    status=WAIT,
                    context=context,
                    extras=self.extras,
                )
            }
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
        return Result(
            run_id=run_id,
            parent_run_id=parent_run_id,
            status=SUCCESS,
            context=catch(
                context=context,
                status=SUCCESS,
                updated={
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
                            and k in params
                        )
                    },
                },
            ),
            extras=self.extras,
        )

    async def async_process(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Async execution method for this Bash stage that only logging out to
        stdout.

        References:
            - https://stackoverflow.com/questions/44859165/async-exec-in-python

        Args:
            params: A parameter data that want to use in this
                execution.
            run_id: A running stage ID.
            context: A context data.
            parent_run_id: A parent running ID. (Default is None)
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The execution result with status and context data.
        """
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        await trace.ainfo("[STAGE]: Prepare `globals` and `locals` variables.")
        lc: DictData = {}
        gb: DictData = (
            globals()
            | param2template(self.vars, params, extras=self.extras)
            | {
                "result": Result(
                    run_id=run_id,
                    parent_run_id=parent_run_id,
                    status=WAIT,
                    context=context,
                    extras=self.extras,
                )
            }
        )
        # WARNING: The exec build-in function is very dangerous. So, it
        #   should use the re module to validate exec-string before running.
        exec(
            param2template(dedent(self.run), params, extras=self.extras),
            gb,
            lc,
        )
        return Result(
            run_id=run_id,
            parent_run_id=parent_run_id,
            status=SUCCESS,
            context=catch(
                context=context,
                status=SUCCESS,
                updated={
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
                            and k in params
                        )
                    },
                },
            ),
            extras=self.extras,
        )


class CallStage(BaseRetryStage):
    """Call stage executor that call the Python function from registry with tag
    decorator function in `reusables` module and run it with input arguments.

        This stage is different with PyStage because the PyStage is just run
    a Python statement with the `exec` function and pass the current locals and
    globals before exec that statement. This stage will import the caller
    function can call it with an input arguments. So, you can create your
    function complexly that you can for your objective to invoked by this stage
    object.

        This stage is the most powerful stage of this package for run every
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

    @field_validator("args", mode="before")
    def __validate_args_key(cls, value: Any) -> Any:
        """Validate argument keys on the ``args`` field should not include the
        special keys.

        :param value: (Any) A value that want to check the special keys.

        :rtype: Any
        """
        if isinstance(value, dict) and any(
            k in value for k in ("result", "extras")
        ):
            raise ValueError(
                "The argument on workflow template for the caller stage "
                "should not pass `result` and `extras`. They are special "
                "arguments."
            )
        return value

    def get_caller(self, params: DictData) -> Callable[[], TagFunc]:
        """Get the lazy TagFuc object from registry."""
        return extract_call(
            param2template(self.uses, params, extras=self.extras),
            registries=self.extras.get("registry_caller"),
        )

    def process(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Execute this caller function with its argument parameter.

        Args:
            params: A parameter data that want to use in this
                execution.
            run_id: A running stage ID.
            context: A context data.
            parent_run_id: A parent running ID. (Default is None)
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The execution result with status and context data.
        """
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        call_func: TagFunc = self.get_caller(params=params)()
        trace.info(f"[STAGE]: Caller Func: '{call_func.name}@{call_func.tag}'")

        # VALIDATE: check input task caller parameters that exists before
        #   calling.
        args: DictData = {
            "result": Result(
                run_id=run_id,
                parent_run_id=parent_run_id,
                status=WAIT,
                context=context,
                extras=self.extras,
            ),
            "extras": self.extras,
        } | param2template(self.args, params, extras=self.extras)
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
            if "result" in necessary_params:
                necessary_params.remove("result")

            if "extras" in necessary_params:
                necessary_params.remove("extras")

            args.pop("result")
            args.pop("extras")
            raise ValueError(
                f"Necessary params, ({', '.join(necessary_params)}, ), "
                f"does not set to args. It already set {list(args.keys())}."
            )

        if "result" not in sig.parameters and not has_keyword:
            args.pop("result")

        if "extras" not in sig.parameters and not has_keyword:
            args.pop("extras")

        if event and event.is_set():
            raise StageCancelError(
                "Execution was canceled from the event before start parallel."
            )

        args: DictData = self.validate_model_args(
            call_func, args, run_id, parent_run_id, extras=self.extras
        )
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
        return Result(
            run_id=run_id,
            parent_run_id=parent_run_id,
            status=SUCCESS,
            context=catch(
                context=context,
                status=SUCCESS,
                updated=dump_all(rs, by_alias=True),
            ),
            extras=self.extras,
        )

    async def async_process(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Async execution method for this Bash stage that only logging out to
        stdout.

        Args:
            params: A parameter data that want to use in this
                execution.
            run_id: A running stage ID.
            context: A context data.
            parent_run_id: A parent running ID. (Default is None)
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The execution result with status and context data.
        """
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        call_func: TagFunc = self.get_caller(params=params)()
        await trace.ainfo(
            f"[STAGE]: Caller Func: '{call_func.name}@{call_func.tag}'"
        )

        # VALIDATE: check input task caller parameters that exists before
        #   calling.
        args: DictData = {
            "result": Result(
                run_id=run_id,
                parent_run_id=parent_run_id,
                status=WAIT,
                context=context,
                extras=self.extras,
            ),
            "extras": self.extras,
        } | param2template(self.args, params, extras=self.extras)
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
            if "result" in necessary_params:
                necessary_params.remove("result")

            if "extras" in necessary_params:
                necessary_params.remove("extras")

            args.pop("result")
            args.pop("extras")
            raise ValueError(
                f"Necessary params, ({', '.join(necessary_params)}, ), "
                f"does not set to args. It already set {list(args.keys())}."
            )
        if "result" not in sig.parameters and not has_keyword:
            args.pop("result")

        if "extras" not in sig.parameters and not has_keyword:
            args.pop("extras")

        if event and event.is_set():
            raise StageCancelError(
                "Execution was canceled from the event before start parallel."
            )

        args: DictData = self.validate_model_args(
            call_func, args, run_id, parent_run_id, extras=self.extras
        )
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
        return Result(
            run_id=run_id,
            parent_run_id=parent_run_id,
            status=SUCCESS,
            context=catch(
                context=context,
                status=SUCCESS,
                updated=dump_all(rs, by_alias=True),
            ),
            extras=self.extras,
        )

    @staticmethod
    def validate_model_args(
        func: TagFunc,
        args: DictData,
        run_id: str,
        parent_run_id: Optional[str] = None,
        extras: Optional[DictData] = None,
    ) -> DictData:
        """Validate an input arguments before passing to the caller function.

        Args:
            func: (TagFunc) A tag function that want to get typing.
            args: (DictData) An arguments before passing to this tag func.
            run_id: A running stage ID.

        :rtype: DictData
        """
        try:
            override: DictData = dict(
                create_model_from_caller(func).model_validate(args)
            )
            args.update(override)

            type_hints: dict[str, Any] = get_type_hints(func)
            for arg in type_hints:

                if arg == "return":
                    continue

                if arg.startswith("_") and arg.removeprefix("_") in args:
                    args[arg] = args.pop(arg.removeprefix("_"))
                    continue

            return args
        except ValidationError as e:
            raise StageError(
                "Validate argument from the caller function raise invalid type."
            ) from e
        except TypeError as e:
            trace: TraceManager = get_trace(
                run_id, parent_run_id=parent_run_id, extras=extras
            )
            trace.warning(
                f"[STAGE]: Get type hint raise TypeError: {e}, so, it skip "
                f"parsing model args process."
            )
            return args


class BaseNestedStage(BaseRetryStage, ABC):
    """Base Nested Stage model. This model is use for checking the child stage
    is the nested stage or not.
    """

    def set_outputs(
        self, output: DictData, to: DictData, info: Optional[DictData] = None
    ) -> DictData:
        """Override the set outputs method that support for nested-stage."""
        return super().set_outputs(output, to=to)

    def get_outputs(self, output: DictData) -> DictData:
        """Override the get outputs method that support for nested-stage"""
        return super().get_outputs(output)

    @property
    def is_nested(self) -> bool:
        """Check if this stage is a nested stage or not.

        :rtype: bool
        """
        return True

    @staticmethod
    def mark_errors(context: DictData, error: StageError) -> None:
        """Make the errors context result with the refs value depends on the nested
        execute func.

        :param context: (DictData) A context data.
        :param error: (StageError) A stage exception object.
        """
        if "errors" in context:
            context["errors"][error.refs] = error.to_dict()
        else:
            context["errors"] = error.to_dict(with_refs=True)

    async def async_process(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Async process for nested-stage do not implement yet.

        Args:
            params: A parameter data that want to use in this
                execution.
            run_id: A running stage ID.
            context: A context data.
            parent_run_id: A parent running ID. (Default is None)
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The execution result with status and context data.
        """
        raise NotImplementedError(
            "The nested-stage does not implement the `axecute` method yet."
        )


class TriggerStage(BaseNestedStage):
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

    def process(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Trigger another workflow execution. It will wait the trigger
        workflow running complete before catching its result and raise error
        when the result status does not be SUCCESS.

        Args:
            params: A parameter data that want to use in this
                execution.
            run_id: A running stage ID.
            context: A context data.
            parent_run_id: A parent running ID. (Default is None)
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The execution result with status and context data.
        """
        from .workflow import Workflow

        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        _trigger: str = param2template(self.trigger, params, extras=self.extras)
        trace.info(f"[STAGE]: Load workflow: {_trigger!r}")
        result: Result = Workflow.from_conf(
            name=pass_env(_trigger),
            extras=self.extras,
        ).execute(
            # NOTE: Should not use the `pass_env` function on this params parameter.
            params=param2template(self.params, params, extras=self.extras),
            run_id=parent_run_id,
            event=event,
        )
        if result.status == FAILED:
            err_msg: StrOrNone = (
                f" with:\n{msg}"
                if (msg := result.context.get("errors", {}).get("message"))
                else "."
            )
            raise StageError(f"Trigger workflow was failed{err_msg}")
        elif result.status == CANCEL:
            raise StageCancelError("Trigger workflow was cancel.")
        elif result.status == SKIP:
            raise StageSkipError("Trigger workflow was skipped.")
        return result


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
        ...             {
        ...                 "name": "Echo second stage",
        ...                 "echo": "Start run with branch 1",
        ...             },
        ...         ],
        ...         "branch02": [
        ...             {
        ...                 "name": "Echo first stage",
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

    def _process_branch(
        self,
        branch: str,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> tuple[Status, DictData]:
        """Execute branch that will execute all nested-stage that was set in
        this stage with specific branch ID.

        :param branch: (str) A branch ID.
        :param params: (DictData) A parameter data.
        :param run_id: (str)
        :param context: (DictData)
        :param parent_run_id: (str | None)
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.
            (Default is None)

        :raise StageCancelError: If event was set.
        :raise StageCancelError: If result from a nested-stage return canceled
            status.
        :raise StageError: If result from a nested-stage return failed status.

        :rtype: tuple[Status, DictData]
        """
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        trace.debug(f"[STAGE]: Execute Branch: {branch!r}")

        # NOTE: Create nested-context
        current_context: DictData = copy.deepcopy(params)
        current_context.update({"branch": branch})
        nestet_context: DictData = {"branch": branch, "stages": {}}

        total_stage: int = len(self.parallel[branch])
        skips: list[bool] = [False] * total_stage
        for i, stage in enumerate(self.parallel[branch], start=0):

            if self.extras:
                stage.extras = self.extras

            if event and event.is_set():
                error_msg: str = (
                    "Branch execution was canceled from the event before "
                    "start branch execution."
                )
                catch(
                    context=context,
                    status=CANCEL,
                    parallel={
                        branch: {
                            "status": CANCEL,
                            "branch": branch,
                            "stages": filter_func(
                                nestet_context.pop("stages", {})
                            ),
                            "errors": StageCancelError(error_msg).to_dict(),
                        }
                    },
                )
                raise StageCancelError(error_msg, refs=branch)

            rs: Result = stage.execute(
                params=current_context,
                run_id=parent_run_id,
                event=event,
            )
            stage.set_outputs(rs.context, to=nestet_context)
            stage.set_outputs(
                stage.get_outputs(nestet_context), to=current_context
            )

            if rs.status == SKIP:
                skips[i] = True
                continue

            elif rs.status == FAILED:  # pragma: no cov
                error_msg: str = (
                    f"Branch execution was break because its nested-stage, "
                    f"{stage.iden!r}, failed."
                )
                catch(
                    context=context,
                    status=FAILED,
                    parallel={
                        branch: {
                            "status": FAILED,
                            "branch": branch,
                            "stages": filter_func(
                                nestet_context.pop("stages", {})
                            ),
                            "errors": StageError(error_msg).to_dict(),
                        },
                    },
                )
                raise StageError(error_msg, refs=branch)

            elif rs.status == CANCEL:
                error_msg: str = (
                    "Branch execution was canceled from the event after "
                    "end branch execution."
                )
                catch(
                    context=context,
                    status=CANCEL,
                    parallel={
                        branch: {
                            "status": CANCEL,
                            "branch": branch,
                            "stages": filter_func(
                                nestet_context.pop("stages", {})
                            ),
                            "errors": StageCancelError(error_msg).to_dict(),
                        }
                    },
                )
                raise StageCancelError(error_msg, refs=branch)

        status: Status = SKIP if sum(skips) == total_stage else SUCCESS
        return status, catch(
            context=context,
            status=status,
            parallel={
                branch: {
                    "status": status,
                    "branch": branch,
                    "stages": filter_func(nestet_context.pop("stages", {})),
                },
            },
        )

    def process(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Execute parallel each branch via multi-threading pool.

        Args:
            params: A parameter data that want to use in this
                execution.
            run_id: A running stage ID.
            context: A context data.
            parent_run_id: A parent running ID. (Default is None)
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The execution result with status and context data.
        """
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        event: Event = event or Event()
        trace.info(f"[STAGE]: Parallel with {self.max_workers} workers.")
        catch(
            context=context,
            status=WAIT,
            updated={"workers": self.max_workers, "parallel": {}},
        )
        len_parallel: int = len(self.parallel)
        if event and event.is_set():
            raise StageCancelError(
                "Execution was canceled from the event before start parallel."
            )

        with ThreadPoolExecutor(self.max_workers, "stp") as executor:
            futures: list[Future] = [
                executor.submit(
                    self._process_branch,
                    branch=branch,
                    params=params,
                    run_id=run_id,
                    context=context,
                    parent_run_id=parent_run_id,
                    event=event,
                )
                for branch in self.parallel
            ]
            errors: DictData = {}
            statuses: list[Status] = [WAIT] * len_parallel
            for i, future in enumerate(as_completed(futures), start=0):
                try:
                    statuses[i], _ = future.result()
                except StageError as e:
                    statuses[i] = get_status_from_error(e)
                    self.mark_errors(errors, e)

        st: Status = validate_statuses(statuses)
        return Result(
            run_id=run_id,
            parent_run_id=parent_run_id,
            status=st,
            context=catch(context, status=st, updated=errors),
            extras=self.extras,
        )


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

    foreach: Union[
        list[str],
        list[int],
        str,
        dict[str, Any],
        dict[int, Any],
    ] = Field(
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

    def _process_item(
        self,
        index: int,
        item: StrOrInt,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> tuple[Status, DictData]:
        """Execute item that will execute all nested-stage that was set in this
        stage with specific foreach item.

            This method will create the nested-context from an input context
        data and use it instead the context data.

        :param index: (int) An index value of foreach loop.
        :param item: (str | int) An item that want to execution.
        :param params: (DictData) A parameter data.
        :param run_id: (str)
        :param context: (DictData)
        :param parent_run_id: (str | None)
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.
            (Default is None)

            This method should raise error when it wants to stop the foreach
        loop such as cancel event or getting the failed status.

        :raise StageCancelError: If event was set.
        :raise StageError: If the stage execution raise any Exception error.
        :raise StageError: If the result from execution has `FAILED` status.

        :rtype: tuple[Status, Result]
        """
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        trace.debug(f"[STAGE]: Execute Item: {item!r}")
        key: StrOrInt = index if self.use_index_as_key else item

        # NOTE: Create nested-context data from the passing context.
        current_context: DictData = copy.deepcopy(params)
        current_context.update({"item": item, "loop": index})
        nestet_context: DictData = {"item": item, "stages": {}}

        total_stage: int = len(self.stages)
        skips: list[bool] = [False] * total_stage
        for i, stage in enumerate(self.stages, start=0):

            if self.extras:
                stage.extras = self.extras

            if event and event.is_set():
                error_msg: str = (
                    "Item execution was canceled from the event before start "
                    "item execution."
                )
                catch(
                    context=context,
                    status=CANCEL,
                    foreach={
                        key: {
                            "status": CANCEL,
                            "item": item,
                            "stages": filter_func(
                                nestet_context.pop("stages", {})
                            ),
                            "errors": StageCancelError(error_msg).to_dict(),
                        }
                    },
                )
                raise StageCancelError(error_msg, refs=key)

            # NOTE: Nested-stage execute will pass only params and context only.
            rs: Result = stage.execute(
                params=current_context,
                run_id=parent_run_id,
                event=event,
            )
            stage.set_outputs(rs.context, to=nestet_context)
            stage.set_outputs(
                stage.get_outputs(nestet_context), to=current_context
            )

            if rs.status == SKIP:
                skips[i] = True
                continue

            elif rs.status == FAILED:  # pragma: no cov
                error_msg: str = (
                    f"Item execution was break because its nested-stage, "
                    f"{stage.iden!r}, failed."
                )
                trace.warning(f"[STAGE]: {error_msg}")
                catch(
                    context=context,
                    status=FAILED,
                    foreach={
                        key: {
                            "status": FAILED,
                            "item": item,
                            "stages": filter_func(
                                nestet_context.pop("stages", {})
                            ),
                            "errors": StageError(error_msg).to_dict(),
                        },
                    },
                )
                raise StageError(error_msg, refs=key)

            elif rs.status == CANCEL:
                error_msg: str = (
                    "Item execution was canceled from the event after "
                    "end item execution."
                )
                catch(
                    context=context,
                    status=CANCEL,
                    foreach={
                        key: {
                            "status": CANCEL,
                            "item": item,
                            "stages": filter_func(
                                nestet_context.pop("stages", {})
                            ),
                            "errors": StageCancelError(error_msg).to_dict(),
                        }
                    },
                )
                raise StageCancelError(error_msg, refs=key)

        status: Status = SKIP if sum(skips) == total_stage else SUCCESS
        return status, catch(
            context=context,
            status=status,
            foreach={
                key: {
                    "status": status,
                    "item": item,
                    "stages": filter_func(nestet_context.pop("stages", {})),
                },
            },
        )

    def process(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Execute the stages that pass each item form the foreach field.

            This stage will use fail-fast strategy if it was set concurrency
        value more than 1. It will cancel all nested-stage execution when it has
        any item loop raise failed or canceled error.

        Args:
            params: A parameter data that want to use in this
                execution.
            run_id: A running stage ID.
            context: A context data.
            parent_run_id: A parent running ID. (Default is None)
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The execution result with status and context data.
        """
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        event: Event = event or Event()
        foreach: Union[list[str], list[int], str] = pass_env(
            param2template(self.foreach, params, extras=self.extras)
        )

        # [NOTE]: Force convert str to list.
        if isinstance(foreach, str):
            try:
                foreach: list[Any] = str2list(foreach)
            except ValueError as e:
                raise TypeError(
                    f"Does not support string foreach: {foreach!r} that can "
                    f"not convert to list."
                ) from e

        # [VALIDATE]: Type of the foreach should be `list` type.
        elif isinstance(foreach, dict):
            raise TypeError(
                f"Does not support dict foreach: {foreach!r} ({type(foreach)}) "
                f"yet."
            )
        # [Validate]: Value in the foreach item should not be duplicate when the
        #   `use_index_as_key` field did not set.
        elif len(set(foreach)) != len(foreach) and not self.use_index_as_key:
            raise ValueError(
                "Foreach item should not duplicate. If this stage must to pass "
                "duplicate item, it should set `use_index_as_key: true`."
            )

        trace.info(f"[STAGE]: Foreach: {foreach!r}.")
        catch(
            context=context,
            status=WAIT,
            updated={"items": foreach, "foreach": {}},
        )
        len_foreach: int = len(foreach)
        if event and event.is_set():
            raise StageCancelError(
                "Execution was canceled from the event before start foreach."
            )

        with ThreadPoolExecutor(self.concurrent, "stf") as executor:
            futures: list[Future] = [
                executor.submit(
                    self._process_item,
                    index=i,
                    item=item,
                    params=params,
                    run_id=run_id,
                    context=context,
                    parent_run_id=parent_run_id,
                    event=event,
                )
                for i, item in enumerate(foreach, start=0)
            ]

            errors: DictData = {}
            statuses: list[Status] = [WAIT] * len_foreach
            fail_fast: bool = False

            done, not_done = wait(futures, return_when=FIRST_EXCEPTION)
            if len(list(done)) != len(futures):
                trace.warning(
                    "[STAGE]: Set the event for stop pending for-each stage."
                )
                event.set()
                for future in not_done:
                    future.cancel()

                time.sleep(0.01)  # Reduced from 0.025 for better responsiveness
                nd: str = (
                    (
                        f", {len(not_done)} item"
                        f"{'s' if len(not_done) > 1 else ''} not run!!!"
                    )
                    if not_done
                    else ""
                )
                trace.debug(f"[STAGE]: ... Foreach-Stage set failed event{nd}")
                done: Iterator[Future] = as_completed(futures)
                fail_fast = True

            for i, future in enumerate(done, start=0):
                try:
                    # NOTE: Ignore returned context because it already updated.
                    statuses[i], _ = future.result()
                except StageError as e:
                    statuses[i] = get_status_from_error(e)
                    self.mark_errors(errors, e)
                except CancelledError:
                    pass

        status: Status = validate_statuses(statuses)

        # NOTE: Prepare status because it does not cancel from parent event but
        #   cancel from failed item execution.
        if fail_fast and status == CANCEL:
            status = FAILED

        return Result(
            run_id=run_id,
            parent_run_id=parent_run_id,
            status=status,
            context=catch(context, status=status, updated=errors),
            extras=self.extras,
        )


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

    def _process_loop(
        self,
        item: T,
        loop: int,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> tuple[Status, DictData, T]:
        """Execute loop that will execute all nested-stage that was set in this
        stage with specific loop and item.

        :param item: (T) An item that want to execution.
        :param loop: (int) A number of loop.
        :param params: (DictData) A parameter data.
        :param run_id: (str)
        :param context: (DictData)
        :param parent_run_id: (str | None)
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :rtype: tuple[Status, DictData, T]
        :return: Return a pair of Result and changed item.
        """
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        trace.debug(f"[STAGE]: Execute Loop: {loop} (Item {item!r})")

        # NOTE: Create nested-context
        current_context: DictData = copy.deepcopy(params)
        current_context.update({"item": item, "loop": loop})
        nestet_context: DictData = {"loop": loop, "item": item, "stages": {}}

        next_item: Optional[T] = None
        total_stage: int = len(self.stages)
        skips: list[bool] = [False] * total_stage
        for i, stage in enumerate(self.stages, start=0):

            if self.extras:
                stage.extras = self.extras

            if event and event.is_set():
                error_msg: str = (
                    "Loop execution was canceled from the event before start "
                    "loop execution."
                )
                catch(
                    context=context,
                    status=CANCEL,
                    until={
                        loop: {
                            "status": CANCEL,
                            "loop": loop,
                            "item": item,
                            "stages": filter_func(
                                nestet_context.pop("stages", {})
                            ),
                            "errors": StageCancelError(error_msg).to_dict(),
                        }
                    },
                )
                raise StageCancelError(error_msg, refs=loop)

            rs: Result = stage.execute(
                params=current_context,
                run_id=parent_run_id,
                event=event,
            )
            stage.set_outputs(rs.context, to=nestet_context)

            if "item" in (_output := stage.get_outputs(nestet_context)):
                next_item = _output["item"]

            stage.set_outputs(_output, to=current_context)

            if rs.status == SKIP:
                skips[i] = True
                continue

            elif rs.status == FAILED:
                error_msg: str = (
                    f"Loop execution was break because its nested-stage, "
                    f"{stage.iden!r}, failed."
                )
                catch(
                    context=context,
                    status=FAILED,
                    until={
                        loop: {
                            "status": FAILED,
                            "loop": loop,
                            "item": item,
                            "stages": filter_func(
                                nestet_context.pop("stages", {})
                            ),
                            "errors": StageError(error_msg).to_dict(),
                        }
                    },
                )
                raise StageError(error_msg, refs=loop)

            elif rs.status == CANCEL:
                error_msg: str = (
                    "Loop execution was canceled from the event after "
                    "end loop execution."
                )
                catch(
                    context=context,
                    status=CANCEL,
                    until={
                        loop: {
                            "status": CANCEL,
                            "loop": loop,
                            "item": item,
                            "stages": filter_func(
                                nestet_context.pop("stages", {})
                            ),
                            "errors": StageCancelError(error_msg).to_dict(),
                        }
                    },
                )
                raise StageCancelError(error_msg, refs=loop)

        status: Status = SKIP if sum(skips) == total_stage else SUCCESS
        return (
            status,
            catch(
                context=context,
                status=status,
                until={
                    loop: {
                        "status": status,
                        "loop": loop,
                        "item": item,
                        "stages": filter_func(nestet_context.pop("stages", {})),
                    }
                },
            ),
            next_item,
        )

    def process(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Execute until loop with checking the until condition before release
        the next loop.

        Args:
            params: A parameter data that want to use in this
                execution.
            run_id: A running stage ID.
            context: A context data.
            parent_run_id: A parent running ID. (Default is None)
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The execution result with status and context data.
        """
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        event: Event = event or Event()
        trace.info(f"[STAGE]: Until: {self.until!r}")
        item: Union[str, int, bool] = pass_env(
            param2template(self.item, params, extras=self.extras)
        )
        loop: int = 1
        until_rs: bool = True
        exceed_loop: bool = False
        catch(context=context, status=WAIT, updated={"until": {}})
        statuses: list[Status] = []
        while until_rs and not (exceed_loop := (loop > self.max_loop)):

            if event and event.is_set():
                raise StageCancelError(
                    "Execution was canceled from the event before start loop."
                )

            status, context, item = self._process_loop(
                item=item,
                loop=loop,
                params=params,
                run_id=run_id,
                context=context,
                parent_run_id=parent_run_id,
                event=event,
            )

            loop += 1
            if item is None:
                item: int = loop
                trace.warning(
                    f"[STAGE]: Return loop not set the item. It uses loop: "
                    f"{loop} by default."
                )

            next_track: bool = eval(
                pass_env(
                    param2template(
                        self.until,
                        params | {"item": item, "loop": loop},
                        extras=self.extras,
                    ),
                ),
                globals() | params | {"item": item},
                {},
            )
            if not isinstance(next_track, bool):
                raise TypeError(
                    "Return type of until condition not be `boolean`, getting"
                    f": {next_track!r}"
                )
            until_rs: bool = not next_track
            statuses.append(status)
            delay(0.005)

        if exceed_loop:
            error_msg: str = (
                f"Loop was exceed the maximum {self.max_loop} "
                f"loop{'s' if self.max_loop > 1 else ''}."
            )
            raise StageError(error_msg)

        st: Status = validate_statuses(statuses)
        return Result(
            run_id=run_id,
            parent_run_id=parent_run_id,
            status=st,
            context=catch(context, status=st),
            extras=self.extras,
        )


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

    def _process_case(
        self,
        case: str,
        stages: list[Stage],
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> tuple[Status, DictData]:
        """Execute case.

        :param case: (str) A case that want to execution.
        :param stages: (list[Stage]) A list of stage.
        :param params: (DictData) A parameter data.
        :param run_id: (str)
        :param context: (DictData)
        :param parent_run_id: (str | None)
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :rtype: DictData
        """
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        trace.debug(f"[STAGE]: Execute Case: {case!r}")
        current_context: DictData = copy.deepcopy(params)
        current_context.update({"case": case})
        output: DictData = {"case": case, "stages": {}}
        for stage in stages:

            if self.extras:
                stage.extras = self.extras

            if event and event.is_set():
                error_msg: str = (
                    "Case-Stage was canceled from event that had set before "
                    "stage case execution."
                )
                return CANCEL, catch(
                    context=context,
                    status=CANCEL,
                    updated={
                        "case": case,
                        "stages": filter_func(output.pop("stages", {})),
                        "errors": StageError(error_msg).to_dict(),
                    },
                )

            rs: Result = stage.execute(
                params=current_context,
                run_id=parent_run_id,
                event=event,
            )
            stage.set_outputs(rs.context, to=output)
            stage.set_outputs(stage.get_outputs(output), to=current_context)

            if rs.status == FAILED:
                error_msg: str = (
                    f"Case-Stage was break because it has a sub stage, "
                    f"{stage.iden}, failed without raise error."
                )
                return FAILED, catch(
                    context=context,
                    status=FAILED,
                    updated={
                        "case": case,
                        "stages": filter_func(output.pop("stages", {})),
                        "errors": StageError(error_msg).to_dict(),
                    },
                )
        return SUCCESS, catch(
            context=context,
            status=SUCCESS,
            updated={
                "case": case,
                "stages": filter_func(output.pop("stages", {})),
            },
        )

    def process(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Execute case-match condition that pass to the case field.

        Args:
            params: A parameter data that want to use in this
                execution.
            run_id: A running stage ID.
            context: A context data.
            parent_run_id: A parent running ID. (Default is None)
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The execution result with status and context data.
        """
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )

        _case: StrOrNone = param2template(self.case, params, extras=self.extras)

        trace.info(f"[STAGE]: Case: {_case!r}.")
        _else: Optional[Match] = None
        stages: Optional[list[Stage]] = None
        for match in self.match:
            if (c := match.case) == "_":
                _else: Match = match
                continue

            _condition: str = param2template(c, params, extras=self.extras)
            if stages is None and pass_env(_case) == pass_env(_condition):
                stages: list[Stage] = match.stages

        if stages is None:
            if _else is None:
                if not self.skip_not_match:
                    raise StageError(
                        "This stage does not set else for support not match "
                        "any case."
                    )
                raise StageSkipError(
                    "Execution was skipped because it does not match any "
                    "case and the else condition does not set too."
                )

            _case: str = "_"
            stages: list[Stage] = _else.stages

        if event and event.is_set():
            raise StageCancelError(
                "Execution was canceled from the event before start "
                "case execution."
            )
        status, context = self._process_case(
            case=_case,
            stages=stages,
            params=params,
            run_id=run_id,
            context=context,
            parent_run_id=parent_run_id,
            event=event,
        )
        return Result(
            run_id=run_id,
            parent_run_id=parent_run_id,
            status=status,
            context=catch(context, status=status),
            extras=self.extras,
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

    def process(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Raise the StageError object with the message field execution.

        Args:
            params: A parameter data that want to use in this
                execution.
            run_id: A running stage ID.
            context: A context data.
            parent_run_id: A parent running ID. (Default is None)
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The execution result with status and context data.
        """
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        message: str = param2template(self.message, params, extras=self.extras)
        trace.info(f"[STAGE]: Message: ( {message} )")
        raise StageError(message)

    async def async_process(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Async execution method for this Empty stage that only logging out to
        stdout.

        Args:
            params: A parameter data that want to use in this
                execution.
            run_id: A running stage ID.
            context: A context data.
            parent_run_id: A parent running ID. (Default is None)
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The execution result with status and context data.
        """
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        message: str = param2template(self.message, params, extras=self.extras)
        await trace.ainfo(f"[STAGE]: Execute Raise-Stage: ( {message} )")
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

    def _process_task(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> DictData:
        """Execute Docker container task.

        :param params: (DictData) A parameter data.
        :param run_id: (str)
        :param context: (DictData)
        :param parent_run_id: (str | None)
        :param event: (Event) An Event manager instance that use to cancel this
            execution if it forces stopped by parent execution.

        :rtype: DictData
        """
        try:
            from docker import DockerClient
            from docker.errors import ContainerError
        except ImportError:
            raise ImportError(
                "Docker stage need the docker package, you should install it "
                "by `pip install docker` first."
            ) from None

        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
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
            trace.info(f"[STAGE]: ... {line}")

        if event and event.is_set():
            error_msg: str = (
                "Docker-Stage was canceled from event that had set before "
                "run the Docker container."
            )
            return catch(
                context=context,
                status=CANCEL,
                updated={"errors": StageError(error_msg).to_dict()},
            )

        unique_image_name: str = f"{self.image}_{datetime.now():%Y%m%d%H%M%S%f}"
        container = client.containers.run(
            image=pass_env(f"{self.image}:{self.tag}"),
            name=unique_image_name,
            environment=pass_env(self.env),
            volumes=pass_env(
                {
                    Path.cwd()
                    / f".docker.{run_id}.logs": {
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
            trace.info(f"[STAGE]: ... {line.strip().decode()}")

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
        output_file: Path = Path(f".docker.{run_id}.logs/outputs.json")
        if not output_file.exists():
            return catch(context=context, status=SUCCESS)
        return catch(
            context=context,
            status=SUCCESS,
            updated=json.loads(output_file.read_text()),
        )

    def process(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Execute the Docker image via Python API.

        Args:
            params: A parameter data that want to use in this
                execution.
            run_id: A running stage ID.
            context: A context data.
            parent_run_id: A parent running ID. (Default is None)
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The execution result with status and context data.
        """
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        trace.info(f"[STAGE]: Docker: {self.image}:{self.tag}")
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

    @staticmethod
    def prepare_std(value: str) -> Optional[str]:
        """Prepare returned standard string from subprocess."""
        return None if (out := value.strip("\n")) == "" else out

    def process(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        """Execute the Python statement via Python virtual environment.

        Steps:
            - Create python file with the `uv` syntax.
            - Execution python file with `uv run` via Python subprocess module.

        Args:
            params: A parameter data that want to use in this
                execution.
            run_id: A running stage ID.
            context: A context data.
            parent_run_id: A parent running ID. (Default is None)
            event: An event manager that use to track parent process
                was not force stopped.

        Returns:
            Result: The execution result with status and context data.
        """
        trace: TraceManager = get_trace(
            run_id, parent_run_id=parent_run_id, extras=self.extras
        )
        run: str = param2template(dedent(self.run), params, extras=self.extras)
        with self.create_py_file(
            py=run,
            values=param2template(self.vars, params, extras=self.extras),
            deps=param2template(self.deps, params, extras=self.extras),
            run_id=run_id,
        ) as py:
            trace.debug(f"[STAGE]: Create `{py}` file.")
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
        return Result(
            run_id=run_id,
            parent_run_id=parent_run_id,
            status=SUCCESS,
            context=catch(
                context=context,
                status=SUCCESS,
                updated={
                    "return_code": rs.returncode,
                    "stdout": self.prepare_std(rs.stdout),
                    "stderr": self.prepare_std(rs.stderr),
                },
            ),
            extras=self.extras,
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
