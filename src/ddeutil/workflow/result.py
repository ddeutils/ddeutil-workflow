# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Result and Status Management Module.

This module provides the core result and status management functionality for
workflow execution tracking. It includes the Status enumeration for execution
states and the Result dataclass for context transfer between workflow components.
"""
from __future__ import annotations

from dataclasses import field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, TypedDict, Union

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass
from typing_extensions import NotRequired, Self

from .__types import DictData
from .errors import (
    ErrorData,
    JobCancelError,
    JobError,
    JobSkipError,
    ResultError,
    StageCancelError,
    StageError,
    StageNestedCancelError,
    StageNestedError,
    StageNestedSkipError,
    StageSkipError,
    WorkflowCancelError,
    WorkflowError,
)
from .traces import Trace, get_trace
from .utils import default_gen_id


class Status(str, Enum):
    """Execution status enumeration for workflow components.

    Status enum provides standardized status values for tracking the execution
    state of workflows, jobs, and stages. Each status includes an emoji
    representation for visual feedback.

    Attributes:
        SUCCESS: Successful execution completion
        FAILED: Execution failed with errors
        WAIT: Waiting for execution or dependencies
        SKIP: Execution was skipped due to conditions
        CANCEL: Execution was cancelled
    """

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    WAIT = "WAIT"
    SKIP = "SKIP"
    CANCEL = "CANCEL"

    @property
    def emoji(self) -> str:  # pragma: no cov
        """Get emoji representation of the status.

        Returns:
            str: Unicode emoji character representing the status
        """
        return {
            "SUCCESS": "✅",
            "FAILED": "❌",
            "WAIT": "🟡",
            "SKIP": "⏩",
            "CANCEL": "🚫",
        }[self.name]

    def __repr__(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.name

    def is_result(self) -> bool:
        """Return True if this status is the status for result object."""
        return self in ResultStatuses


SUCCESS = Status.SUCCESS
FAILED = Status.FAILED
WAIT = Status.WAIT
SKIP = Status.SKIP
CANCEL = Status.CANCEL

ResultStatuses: list[Status] = [SUCCESS, FAILED, CANCEL, SKIP]


def validate_statuses(statuses: list[Status]) -> Status:
    """Determine final status from multiple status values.

    Applies workflow logic to determine the overall status based on a collection
    of individual status values. Follows priority order:

        CANCEL > FAILED > WAIT > individual status consistency.

    Args:
        statuses: List of status values to evaluate

    Returns:
        Status: Final consolidated status based on workflow logic

    Example:
        >>> # Mixed statuses - FAILED takes priority
        >>> validate_statuses([SUCCESS, FAILED, SUCCESS])
        >>> # Returns: FAILED

        >>> # All same status
        >>> validate_statuses([SUCCESS, SUCCESS, SUCCESS])
        >>> # Returns: SUCCESS
    """
    if any(s == FAILED for s in statuses):
        return FAILED
    elif any(s == CANCEL for s in statuses):
        return CANCEL
    elif any(s == WAIT for s in statuses):
        return WAIT
    for status in (SUCCESS, SKIP):
        if all(s == status for s in statuses):
            return status
    return SUCCESS


def get_status_from_error(
    error: Union[
        StageError,
        StageCancelError,
        StageSkipError,
        StageNestedCancelError,
        StageNestedError,
        StageNestedSkipError,
        JobError,
        JobCancelError,
        JobSkipError,
        WorkflowError,
        WorkflowCancelError,
        Exception,
        BaseException,
    ]
) -> Status:
    """Get the Status from the error object.

    Args:
        error: An error object.

    Returns:
        Status: The status from the specific exception class.
    """
    if isinstance(error, (StageNestedSkipError, StageSkipError, JobSkipError)):
        return SKIP
    elif isinstance(
        error,
        (
            StageNestedCancelError,
            StageCancelError,
            JobCancelError,
            WorkflowCancelError,
        ),
    ):
        return CANCEL
    return FAILED


@dataclass(
    config=ConfigDict(arbitrary_types_allowed=True, use_enum_values=True),
)
class Result:
    """Result Pydantic Model for passing and receiving data context from any
    module execution process like stage execution, job execution, or workflow
    execution.

        For comparison property, this result will use ``status``, ``context``,
    and ``_run_id`` fields to comparing with other result instance.

    Warning:
        I use dataclass object instead of Pydantic model object because context
    field that keep dict value change its ID when update new value to it.
    """

    extras: DictData = field(default_factory=dict, compare=False, repr=False)
    status: Status = field(default=WAIT)
    context: Optional[DictData] = field(default=None)
    run_id: str = field(default_factory=default_gen_id)
    parent_run_id: Optional[str] = field(default=None)

    @classmethod
    def from_trace(cls, trace: Trace):
        """Construct the result model from trace for clean code objective."""
        return cls(
            run_id=trace.run_id,
            parent_run_id=trace.parent_run_id,
            extras=trace.extras,
        )

    def gen_trace(self) -> Trace:
        return get_trace(
            self.run_id,
            parent_run_id=self.parent_run_id,
            extras=self.extras,
        )

    def catch(
        self,
        status: Union[int, Status],
        context: DictData | None = None,
        **kwargs,
    ) -> Self:
        """Catch the status and context to this Result object. This method will
        use between a child execution return a result, and it wants to pass
        status and context to this object.

        :param status: A status enum object.
        :param context: A context data that will update to the current context.

        :rtype: Self
        """
        if self.__dict__["context"] is None:
            self.__dict__["context"] = context
        else:
            self.__dict__["context"].update(context or {})

        self.__dict__["status"] = (
            Status(status) if isinstance(status, int) else status
        )
        self.__dict__["context"]["status"] = self.status

        # NOTE: Update other context data.
        if kwargs:
            for k in kwargs:
                if k in self.__dict__["context"]:
                    self.__dict__["context"][k].update(kwargs[k])
                # NOTE: Exclude the `info` key for update information data.
                elif k == "info":
                    if "info" in self.__dict__["context"]:
                        self.__dict__["context"].update(kwargs[k])
                    else:
                        self.__dict__["context"]["info"] = kwargs[k]
                else:
                    raise ResultError(
                        f"The key {k!r} does not exists on context data."
                    )
        return self


def catch(
    context: DictData,
    status: Union[int, Status],
    updated: DictData | None = None,
    **kwargs,
) -> DictData:
    """Catch updated context to the current context.

    Args:
        context: A context data that want to be the current context.
        status: A status enum object.
        updated: A updated data that will update to the current context.

    Returns:
        DictData: A catch context data.
    """
    context.update(updated or {})
    context["status"] = Status(status) if isinstance(status, int) else status

    if not kwargs:
        return context

    # NOTE: Update other context data.
    for k in kwargs:
        if k in context:
            context[k].update(kwargs[k])
        # NOTE: Exclude the `info` key for update information data.
        elif k == "info":
            if "info" in context:
                context.update(kwargs[k])
            else:
                context["info"] = kwargs[k]
        # ARCHIVE:
        # else:
        #     raise ResultError(f"The key {k!r} does not exist on context data.")
    return context


class Info(TypedDict):
    exec_start: datetime
    exec_end: NotRequired[datetime]
    exec_latency: NotRequired[float]


class Context(TypedDict):
    """Context dict typed."""

    status: Status
    context: NotRequired[DictData]
    errors: NotRequired[Union[list[ErrorData], ErrorData]]
    info: NotRequired[DictData]


class Layer(str, Enum):
    WORKFLOW = "workflow"
    JOB = "job"
    STRATEGY = "strategy"
    STAGE = "stage"


def get_context_by_layer(
    context: DictData,
    key: str,
    layer: Layer,
    context_key: str,
    *,
    default: Optional[Any] = None,
) -> Any:  # pragma: no cov
    if layer == Layer.WORKFLOW:
        return context.get("jobs", {}).get(key, {}).get(context_key, default)
    elif layer == Layer.JOB:
        return context.get("stages", {}).get(key, {}).get(context_key, default)
    elif layer == Layer.STRATEGY:
        return (
            context.get("strategies", {}).get(key, {}).get(context_key, default)
        )
    return context.get(key, {}).get(context_key, default)


def get_status(
    context: DictData,
    key: str,
    layer: Layer,
) -> Status:  # pragma: no cov
    """Get status from context by a specific key and context layer."""
    return get_context_by_layer(
        context, key, layer, context_key="status", default=WAIT
    )
