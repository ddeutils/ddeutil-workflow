# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations


class WorkflowException(Exception): ...


class UtilException(WorkflowException): ...


class StageException(WorkflowException): ...


class JobException(WorkflowException): ...


class PipelineException(WorkflowException): ...


class PipelineFailException(WorkflowException): ...


class ParamValueException(WorkflowException): ...
