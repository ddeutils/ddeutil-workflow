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

from typing import Any


def to_dict(exception: Exception) -> dict[str, Any]:  # pragma: no cov
    return {
        "class": exception,
        "name": exception.__class__.__name__,
        "message": str(exception),
    }


class BaseWorkflowException(Exception):

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self)


class UtilException(BaseWorkflowException): ...


class StageException(BaseWorkflowException): ...


class JobException(BaseWorkflowException): ...


class WorkflowException(BaseWorkflowException): ...


class WorkflowFailException(WorkflowException): ...


class ParamValueException(WorkflowException): ...


class ScheduleException(BaseWorkflowException): ...
