# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""
Define Errors Object for Node package
"""
from __future__ import annotations

from typing import Union


class BaseError(Exception):
    """Base Error Object that use for catch any errors statement of
    all step in this src
    """


class WorkflowBaseError(BaseError):
    """Core Base Error object"""


class ConfigNotFound(WorkflowBaseError):
    """Error raise for a method not found the config file or data."""


class ConfigArgumentError(WorkflowBaseError):
    """Error raise for a wrong configuration argument."""

    def __init__(self, argument: Union[str, tuple], message: str):
        """Main Initialization that merge the argument and message input values
        with specific content message together like

            `__class__` with `argument`, `message`

        :param argument: Union[str, tuple]
        :param message: str
        """
        if isinstance(argument, tuple):
            _last_arg: str = str(argument[-1])
            _argument: str = (
                (
                    ", ".join([f"{_!r}" for _ in argument[:-1]])
                    + f", and {_last_arg!r}"
                )
                if len(argument) > 1
                else f"{_last_arg!r}"
            )
        else:
            _argument: str = f"{argument!r}"
        _message: str = f"with {_argument}, {message}"
        super().__init__(_message)


class ConnArgumentError(ConfigArgumentError):
    """Error raise for wrong connection argument when loading or parsing"""


class DsArgumentError(ConfigArgumentError):
    """Error raise for wrong catalog argument when loading or parsing"""


class NodeArgumentError(ConfigArgumentError):
    """Error raise for wrong node argument when loading or parsing"""


class ScdlArgumentError(ConfigArgumentError):
    """Error raise for wrong schedule argument when loading or parsing"""


class PipeArgumentError(ConfigArgumentError):
    """Error raise for wrong pipeline argument when loading or parsing"""


class PyException(Exception): ...


class ShellException(Exception): ...
