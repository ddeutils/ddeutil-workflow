# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Exception objects for this package do not do anything because I want to
create the lightweight workflow package. So, this module do just an exception
annotate for handle error only.
"""
from __future__ import annotations

from typing import Literal, Optional, TypedDict, Union, overload

from .__types import DictData


class ErrorData(TypedDict):
    """Error data type dict for typing necessary keys of return of to_dict func
    and method.
    """

    name: str
    message: str


def to_dict(exception: Exception, **kwargs) -> ErrorData:  # pragma: no cov
    """Create dict data from exception instance.

    :param exception: An exception object.

    :rtype: ErrorData
    """
    return {
        "name": exception.__class__.__name__,
        "message": str(exception),
        **kwargs,
    }


class BaseError(Exception):
    """Base Workflow exception class will implement the `refs` argument for
    making an error context to the result context.
    """

    def __init__(
        self,
        message: str,
        *,
        refs: Optional[str] = None,
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
        """Return ErrorData data from the current exception object. If with_refs
        flag was set, it will return mapping of refs and itself data.

        :rtype: ErrorData
        """
        data: ErrorData = to_dict(self)
        if with_refs and (self.refs is not None and self.refs != "EMPTY"):
            return {self.refs: data}
        return data | kwargs


class UtilError(BaseError): ...


class ResultError(UtilError): ...


class StageError(BaseError): ...


class StageSkipError(BaseError): ...


class JobError(BaseError): ...


class WorkflowError(BaseError): ...


class ParamError(WorkflowError): ...
