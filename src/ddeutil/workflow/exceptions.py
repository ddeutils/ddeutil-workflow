# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""
Define Errors Object for Node package
"""
from __future__ import annotations


class BaseError(Exception):
    """Base Error Object that use for catch any errors statement of
    all step in this src
    """


class WorkflowBaseError(BaseError):
    """Core Base Error object"""


class ConfigNotFound(WorkflowBaseError):
    """Error raise for a method not found the config file or data."""


class PyException(Exception): ...


class ShellException(Exception): ...


class TaskException(Exception): ...
