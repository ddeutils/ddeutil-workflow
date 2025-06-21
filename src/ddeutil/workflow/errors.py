# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Exception Classes for Workflow Orchestration.

This module provides a comprehensive exception hierarchy for the workflow system.
The exceptions are designed to be lightweight while providing sufficient context
for error handling and debugging.

Classes:
    BaseError: Base exception class with context support
    StageError: Exceptions related to stage execution
    JobError: Exceptions related to job execution
    WorkflowError: Exceptions related to workflow execution
    ParamError: Exceptions related to parameter validation
    ResultError: Exceptions related to result processing

Functions:
    to_dict: Convert exception instances to dictionary format
"""
from __future__ import annotations

from typing import Literal, Optional, TypedDict, Union, overload

from .__types import DictData, StrOrInt


class ErrorData(TypedDict):
    """Error data structure for exception serialization.

    This TypedDict defines the standard structure for converting exceptions
    to dictionary format for consistent error handling across the system.

    Attributes:
        name: Exception class name
        message: Exception message content
    """

    name: str
    message: str


def to_dict(exception: Exception, **kwargs) -> ErrorData:  # pragma: no cov
    """Create dictionary data from exception instance.

    Converts an exception object to a standardized dictionary format
    for consistent error handling and serialization.

    Args:
        exception: Exception object to convert
        **kwargs: Additional key-value pairs to include in result

    Returns:
        ErrorData: Dictionary containing exception name and message

    Example:
        >>> try:
        >>>     raise ValueError("Something went wrong")
        >>> except Exception as e:
        >>>     error_data = to_dict(e, context="workflow_execution")
        >>>     # Returns: {
        >>>     #   "name": "ValueError", "message": "Something went wrong", "context": "workflow_execution"
        >>>     # }
    """
    return {
        "name": exception.__class__.__name__,
        "message": str(exception),
        **kwargs,
    }


class BaseError(Exception):
    """Base exception class for all workflow-related errors.

    BaseError provides the foundation for all workflow exceptions, offering
    enhanced context management and error tracking capabilities. It supports
    reference IDs for error correlation and maintains context information
    for debugging purposes.

    Attributes:
        refs: Optional reference identifier for error correlation
        context: Additional context data related to the error
        params: Parameter data that was being processed when error occurred

    Example:
        >>> try:
        >>>     # NOTE: Some workflow operation
        >>>     pass
        >>> except BaseError as e:
        >>>     error_dict = e.to_dict(with_refs=True)
        >>>     print(f\"Error in {e.refs}: {error_dict}\")
    """

    def __init__(
        self,
        message: str,
        *,
        refs: Optional[StrOrInt] = None,
        context: Optional[DictData] = None,
        params: Optional[DictData] = None,
    ) -> None:
        super().__init__(message)
        self.refs: Optional[str] = refs
        self.context: DictData = context or {}
        self.params: DictData = params or {}

    @overload
    def to_dict(
        self, with_refs: Literal[True] = ...
    ) -> dict[str, ErrorData]: ...  # pragma: no cov

    @overload
    def to_dict(
        self, with_refs: Literal[False] = ...
    ) -> ErrorData: ...  # pragma: no cov

    def to_dict(
        self,
        with_refs: bool = False,
        **kwargs,
    ) -> Union[ErrorData, dict[str, ErrorData]]:
        """Convert exception to dictionary format.

        Serializes the exception to a standardized dictionary format.
        Optionally includes reference mapping for error correlation.

        Args:
            with_refs: Include reference ID mapping in result
            **kwargs: Additional key-value pairs to include

        Returns:
            ErrorData or dict: Exception data, optionally mapped by reference ID

        Example:
            >>> error = BaseError("Something failed", refs="stage-1")
            >>> # Simple format
            >>> error.to_dict()
            >>> # Returns: {"name": "BaseError", "message": "Something failed"}

            >>> # With reference mapping
            >>> error.to_dict(with_refs=True)
            >>> # Returns: {"stage-1": {"name": "BaseError", "message": "Something failed"}}
            ```
        """
        data: ErrorData = to_dict(self)
        if with_refs and (self.refs is not None and self.refs != "EMPTY"):
            return {self.refs: data}
        return data | kwargs


class UtilError(BaseError): ...


class ResultError(UtilError): ...


class StageError(BaseError): ...


class StageCancelError(StageError): ...


class StageSkipError(StageError): ...


class JobError(BaseError): ...


class JobCancelError(JobError): ...


class JobSkipError(JobError): ...


class WorkflowError(BaseError): ...


class WorkflowCancelError(WorkflowError): ...


class WorkflowTimeoutError(WorkflowError): ...


class ParamError(WorkflowError): ...
