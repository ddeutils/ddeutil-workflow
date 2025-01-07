# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Exception objects for this package do not do anything because I want to
create the lightweight workflow package. So, this module do just a exception
annotate for handle error only.
"""
from __future__ import annotations


class BaseWorkflowException(Exception): ...


class UtilException(BaseWorkflowException): ...


class StageException(BaseWorkflowException): ...


class JobException(BaseWorkflowException): ...


class WorkflowException(BaseWorkflowException): ...


class WorkflowFailException(WorkflowException): ...


class ParamValueException(WorkflowException): ...
