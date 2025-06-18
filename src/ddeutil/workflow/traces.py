# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Tracing and Logging Module for Workflow Execution.

This module provides comprehensive tracing and logging capabilities for workflow
execution monitoring. It supports multiple trace backends including console output,
file-based logging, and SQLite database storage.

The tracing system captures detailed execution metadata including process IDs,
thread identifiers, timestamps, and contextual information for debugging and
monitoring workflow executions.

Classes:
    Message: Log message model with prefix parsing
    TraceMeta: Metadata model for execution context
    TraceData: Container for trace information
    BaseTrace: Abstract base class for trace implementations
    ConsoleTrace: Console-based trace output
    FileTrace: File-based trace storage
    SQLiteTrace: Database-based trace storage

Functions:
    set_logging: Configure logger with custom formatting
    get_trace: Factory function for trace instances

Example:
    >>> from ddeutil.workflow.traces import get_trace
    >>> # Create file-based trace
    >>> trace = get_trace("running-id-101", parent_run_id="workflow-001")
    >>> trace.info("Workflow execution started")
    >>> trace.debug("Processing stage 1")
"""
from __future__ import annotations

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from functools import lru_cache
from inspect import Traceback, currentframe, getframeinfo
from pathlib import Path
from threading import get_ident
from types import FrameType
from typing import ClassVar, Final, Literal, Optional, Union
from urllib.parse import ParseResult, unquote_plus, urlparse

from pydantic import BaseModel, ConfigDict, Field
from pydantic.functional_serializers import field_serializer
from pydantic.functional_validators import field_validator
from typing_extensions import Self

from .__types import DictData
from .conf import config, dynamic
from .utils import cut_id, get_dt_now, prepare_newline

METADATA: str = "metadata.json"
logger = logging.getLogger("ddeutil.workflow")


@lru_cache
def set_logging(name: str) -> logging.Logger:
    """Configure logger with custom formatting and handlers.

    Creates and configures a logger instance with the custom formatter and
    handlers defined in the package configuration. The logger includes both
    console output and proper formatting for workflow execution tracking.

    Args:
        name: Module name to create logger for

    Returns:
        logging.Logger: Configured logger instance with custom formatting

    Example:
        ```python
        logger = set_logging("ddeutil.workflow.stages")
        logger.info("Stage execution started")
        ```
    """
    _logger = logging.getLogger(name)

    # NOTE: Developers using this package can then disable all logging just for
    #   this package by;
    #
    #   `logging.getLogger('ddeutil.workflow').propagate = False`
    #
    _logger.addHandler(logging.NullHandler())

    formatter = logging.Formatter(
        fmt=config.log_format, datefmt=config.log_datetime_format
    )
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    _logger.addHandler(stream_handler)
    _logger.setLevel(logging.DEBUG if config.debug else logging.INFO)
    return _logger


PREFIX_LOGS: Final[dict[str, dict]] = {
    "CALLER": {
        "emoji": "📍",
        "desc": "logs from any usage from custom caller function.",
    },
    "STAGE": {"emoji": "⚙️", "desc": "logs from stages module."},
    "JOB": {"emoji": "⛓️", "desc": "logs from job module."},
    "WORKFLOW": {"emoji": "🏃", "desc": "logs from workflow module."},
    "RELEASE": {"emoji": "📅", "desc": "logs from release workflow method."},
    "POKING": {"emoji": "⏰", "desc": "logs from poke workflow method."},
}  # pragma: no cov
PREFIX_DEFAULT: Final[str] = "CALLER"
PREFIX_LOGS_REGEX: re.Pattern[str] = re.compile(
    rf"(^\[(?P<name>{'|'.join(PREFIX_LOGS)})]:\s?)?(?P<message>.*)",
    re.MULTILINE | re.DOTALL | re.ASCII | re.VERBOSE,
)  # pragma: no cov


class Message(BaseModel):
    """Prefix Message model for receive grouping dict from searching prefix data
    from logging message.
    """

    name: Optional[str] = Field(default=None, description="A prefix name.")
    message: Optional[str] = Field(default=None, description="A message.")

    @classmethod
    def from_str(cls, msg: str) -> Self:
        """Extract message prefix from an input message.

        Args:
            msg (str): A message that want to extract.

        Returns:
            Message: the validated model from a string message.
        """
        return Message.model_validate(
            obj=PREFIX_LOGS_REGEX.search(msg).groupdict()
        )

    def prepare(self, extras: Optional[DictData] = None) -> str:
        """Prepare message with force add prefix before writing trace log.

        Args:
            extras: An extra parameter that want to get the
                `log_add_emoji` flag.

        Returns:
            str: The prepared message with prefix and optional emoji.
        """
        name: str = self.name or PREFIX_DEFAULT
        emoji: str = (
            f"{PREFIX_LOGS[name]['emoji']} "
            if (extras or {}).get("log_add_emoji", True)
            else ""
        )
        return f"{emoji}[{name}]: {self.message}"


class TraceMeta(BaseModel):  # pragma: no cov
    """Trace Metadata model for making the current metadata of this CPU, Memory
    process, and thread data.
    """

    mode: Literal["stdout", "stderr"] = Field(description="A meta mode.")
    level: str = Field(description="A log level.")
    datetime: str = Field(description="A datetime in string format.")
    process: int = Field(description="A process ID.")
    thread: int = Field(description="A thread ID.")
    message: str = Field(description="A message log.")
    cut_id: Optional[str] = Field(
        default=None, description="A cutting of running ID."
    )
    filename: str = Field(description="A filename of this log.")
    lineno: int = Field(description="A line number of this log.")

    @classmethod
    def dynamic_frame(
        cls, frame: FrameType, *, extras: Optional[DictData] = None
    ) -> Traceback:
        """Dynamic Frame information base on the `logs_trace_frame_layer` config
        value that was set from the extra parameter.

        Args:
            frame: The current frame that want to dynamic.
            extras: An extra parameter that want to get the
                `logs_trace_frame_layer` config value.

        Returns:
            Traceback: The frame information at the specified layer.
        """
        extras: DictData = extras or {}
        layer: int = extras.get("logs_trace_frame_layer", 4)
        for _ in range(layer):
            _frame: Optional[FrameType] = frame.f_back
            if _frame is None:
                raise ValueError(
                    f"Layer value does not valid, the maximum frame is: {_ + 1}"
                )
            frame: FrameType = _frame
        return getframeinfo(frame)

    @classmethod
    def make(
        cls,
        mode: Literal["stdout", "stderr"],
        message: str,
        level: str,
        cutting_id: str,
        *,
        extras: Optional[DictData] = None,
    ) -> Self:
        """Make the current metric for contract this TraceMeta model instance
        that will catch local states like PID, thread identity.

        Args:
            mode: A metadata mode.
            message: A message.
            level: A log level.
            cutting_id: A cutting ID string.
            extras: An extra parameter that want to override core
                config values.

        Returns:
            Self: The constructed TraceMeta instance.
        """
        frame: FrameType = currentframe()
        frame_info: Traceback = cls.dynamic_frame(frame, extras=extras)
        extras: DictData = extras or {}
        return cls(
            mode=mode,
            level=level,
            datetime=(
                get_dt_now(tz=dynamic("tz", extras=extras)).strftime(
                    dynamic("log_datetime_format", extras=extras)
                )
            ),
            process=os.getpid(),
            thread=get_ident(),
            message=message,
            cut_id=cutting_id,
            filename=frame_info.filename.split(os.path.sep)[-1],
            lineno=frame_info.lineno,
        )


class TraceData(BaseModel):  # pragma: no cov
    """Trace Data model for keeping data for any Trace models."""

    stdout: str = Field(description="A standard output trace data.")
    stderr: str = Field(description="A standard error trace data.")
    meta: list[TraceMeta] = Field(
        default_factory=list,
        description=(
            "A metadata mapping of this output and error before making it to "
            "standard value."
        ),
    )

    @classmethod
    def from_path(cls, file: Path) -> Self:
        """Construct this trace data model with a trace path.

        :param file: (Path) A trace path.

        :rtype: Self
        """
        data: DictData = {"stdout": "", "stderr": "", "meta": []}

        for mode in ("stdout", "stderr"):
            if (file / f"{mode}.txt").exists():
                data[mode] = (file / f"{mode}.txt").read_text(encoding="utf-8")

        if (file / METADATA).exists():
            data["meta"] = [
                json.loads(line)
                for line in (
                    (file / METADATA).read_text(encoding="utf-8").splitlines()
                )
            ]

        return cls.model_validate(data)


class BaseTrace(BaseModel, ABC):  # pragma: no cov
    """Base Trace model with abstraction class property."""

    model_config = ConfigDict(frozen=True)

    extras: DictData = Field(
        default_factory=dict,
        description=(
            "An extra parameter that want to override on the core config "
            "values."
        ),
    )
    run_id: str = Field(description="A running ID")
    parent_run_id: Optional[str] = Field(
        default=None,
        description="A parent running ID",
    )

    @abstractmethod
    def writer(
        self,
        message: str,
        level: str,
        is_err: bool = False,
    ) -> None:
        """Write a trace message after making to target pointer object. The
        target can be anything be inherited this class and overwrite this method
        such as file, console, or database.

        :param message: (str) A message after making.
        :param level: (str) A log level.
        :param is_err: (bool) A flag for writing with an error trace or not.
            (Default be False)
        """
        raise NotImplementedError(
            "Create writer logic for this trace object before using."
        )

    @abstractmethod
    async def awriter(
        self,
        message: str,
        level: str,
        is_err: bool = False,
    ) -> None:
        """Async Write a trace message after making to target pointer object.

        :param message: (str) A message after making.
        :param level: (str) A log level.
        :param is_err: (bool) A flag for writing with an error trace or not.
            (Default be False)
        """
        raise NotImplementedError(
            "Create async writer logic for this trace object before using."
        )

    @abstractmethod
    def make_message(self, message: str) -> str:
        """Prepare and Make a message before write and log processes.

        :param message: A message that want to prepare and make before.

        :rtype: str
        """
        raise NotImplementedError(
            "Adjust make message method for this trace object before using."
        )

    @abstractmethod
    def emit(
        self,
        message: str,
        mode: str,
        *,
        is_err: bool = False,
    ):
        """Write trace log with append mode and logging this message with any
        logging level.

        :param message: (str) A message that want to log.
        :param mode: (str)
        :param is_err: (bool)
        """
        raise NotImplementedError(
            "Logging action should be implement for making trace log."
        )

    def debug(self, message: str):
        """Write trace log with append mode and logging this message with the
        DEBUG level.

        :param message: (str) A message that want to log.
        """
        self.emit(message, mode="debug")

    def info(self, message: str) -> None:
        """Write trace log with append mode and logging this message with the
        INFO level.

        :param message: (str) A message that want to log.
        """
        self.emit(message, mode="info")

    def warning(self, message: str) -> None:
        """Write trace log with append mode and logging this message with the
        WARNING level.

        :param message: (str) A message that want to log.
        """
        self.emit(message, mode="warning")

    def error(self, message: str) -> None:
        """Write trace log with append mode and logging this message with the
        ERROR level.

        :param message: (str) A message that want to log.
        """
        self.emit(message, mode="error", is_err=True)

    def exception(self, message: str) -> None:
        """Write trace log with append mode and logging this message with the
        EXCEPTION level.

        :param message: (str) A message that want to log.
        """
        self.emit(message, mode="exception", is_err=True)

    @abstractmethod
    async def amit(
        self,
        message: str,
        mode: str,
        *,
        is_err: bool = False,
    ) -> None:
        """Async write trace log with append mode and logging this message with
        any logging level.

        :param message: (str) A message that want to log.
        :param mode: (str)
        :param is_err: (bool)
        """
        raise NotImplementedError(
            "Async Logging action should be implement for making trace log."
        )

    async def adebug(self, message: str) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the DEBUG level.

        :param message: (str) A message that want to log.
        """
        await self.amit(message, mode="debug")

    async def ainfo(self, message: str) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the INFO level.

        :param message: (str) A message that want to log.
        """
        await self.amit(message, mode="info")

    async def awarning(self, message: str) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the WARNING level.

        :param message: (str) A message that want to log.
        """
        await self.amit(message, mode="warning")

    async def aerror(self, message: str) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the ERROR level.

        :param message: (str) A message that want to log.
        """
        await self.amit(message, mode="error", is_err=True)

    async def aexception(self, message: str) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the EXCEPTION level.

        :param message: (str) A message that want to log.
        """
        await self.amit(message, mode="exception", is_err=True)


class ConsoleTrace(BaseTrace):  # pragma: no cov
    """Console Trace log model."""

    def writer(
        self,
        message: str,
        level: str,
        is_err: bool = False,
    ) -> None:
        """Write a trace message after making to target pointer object. The
        target can be anything be inherited this class and overwrite this method
        such as file, console, or database.

        :param message: (str) A message after making.
        :param level: (str) A log level.
        :param is_err: (bool) A flag for writing with an error trace or not.
            (Default be False)
        """

    async def awriter(
        self,
        message: str,
        level: str,
        is_err: bool = False,
    ) -> None:
        """Async Write a trace message after making to target pointer object.

        :param message: (str) A message after making.
        :param level: (str) A log level.
        :param is_err: (bool) A flag for writing with an error trace or not.
            (Default be False)
        """

    @property
    def cut_id(self) -> str:
        """Combine cutting ID of parent running ID if it set.

        :rtype: str
        """
        cut_run_id: str = cut_id(self.run_id)
        if not self.parent_run_id:
            return f"{cut_run_id}"

        cut_parent_run_id: str = cut_id(self.parent_run_id)
        return f"{cut_parent_run_id} -> {cut_run_id}"

    def make_message(self, message: str) -> str:
        """Prepare and Make a message before write and log steps.

        :param message: (str) A message that want to prepare and make before.

        :rtype: str
        """
        return prepare_newline(Message.from_str(message).prepare(self.extras))

    def emit(self, message: str, mode: str, *, is_err: bool = False) -> None:
        """Write trace log with append mode and logging this message with any
        logging level.

        :param message: (str) A message that want to log.
        :param mode: (str)
        :param is_err: (bool)
        """
        msg: str = self.make_message(message)

        if mode != "debug" or (
            mode == "debug" and dynamic("debug", extras=self.extras)
        ):
            self.writer(msg, level=mode, is_err=is_err)

        getattr(logger, mode)(msg, stacklevel=3, extra={"cut_id": self.cut_id})

    async def amit(
        self, message: str, mode: str, *, is_err: bool = False
    ) -> None:
        """Write trace log with append mode and logging this message with any
        logging level.

        :param message: (str) A message that want to log.
        :param mode: (str)
        :param is_err: (bool)
        """
        msg: str = self.make_message(message)

        if mode != "debug" or (
            mode == "debug" and dynamic("debug", extras=self.extras)
        ):
            await self.awriter(msg, level=mode, is_err=is_err)

        getattr(logger, mode)(msg, stacklevel=3, extra={"cut_id": self.cut_id})


class OutsideTrace(ConsoleTrace, ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    url: ParseResult = Field(description="An URL for create pointer.")

    @field_validator(
        "url", mode="before", json_schema_input_type=Union[ParseResult, str]
    )
    def __parse_url(cls, value: Union[ParseResult, str]) -> ParseResult:
        if isinstance(value, str):
            return urlparse(value)
        return value

    @field_serializer("url")
    def __serialize_url(self, value: ParseResult) -> str:
        return value.geturl()

    @classmethod
    @abstractmethod
    def find_traces(
        cls,
        path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> Iterator[TraceData]:  # pragma: no cov
        """Return iterator of TraceData models from the target pointer.

        Args:
            path (:obj:`Path`, optional): A pointer path that want to override.
            extras (:obj:`DictData`, optional): An extras parameter that want to
                override default engine config.

        Returns:
            Iterator[TracData]: An iterator object that generate a TracData
                model.
        """
        raise NotImplementedError(
            "Trace dataclass should implement `find_traces` class-method."
        )

    @classmethod
    @abstractmethod
    def find_trace_with_id(
        cls,
        run_id: str,
        force_raise: bool = True,
        *,
        path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> TraceData:
        raise NotImplementedError(
            "Trace dataclass should implement `find_trace_with_id` "
            "class-method."
        )


class FileTrace(OutsideTrace):  # pragma: no cov
    """File Trace dataclass that write file to the local storage."""

    @classmethod
    def find_traces(
        cls,
        path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> Iterator[TraceData]:  # pragma: no cov
        """Find trace logs.

        :param path: (Path) A trace path that want to find.
        :param extras: An extra parameter that want to override core config.
        """
        for file in sorted(
            (path or Path(dynamic("trace_url", extras=extras).path)).glob(
                "./run_id=*"
            ),
            key=lambda f: f.lstat().st_mtime,
        ):
            yield TraceData.from_path(file)

    @classmethod
    def find_trace_with_id(
        cls,
        run_id: str,
        *,
        force_raise: bool = True,
        path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> TraceData:
        """Find trace log with an input specific run ID.

        :param run_id: A running ID of trace log.
        :param force_raise: (bool)
        :param path: (Path)
        :param extras: An extra parameter that want to override core config.
        """
        base_path: Path = path or Path(dynamic("trace_url", extras=extras).path)
        file: Path = base_path / f"run_id={run_id}"
        if file.exists():
            return TraceData.from_path(file)
        elif force_raise:
            raise FileNotFoundError(
                f"Trace log on path {base_path}, does not found trace "
                f"'run_id={run_id}'."
            )
        return TraceData(stdout="", stderr="")

    @property
    def pointer(self) -> Path:
        """Pointer of the target path that use to writing trace log or searching
        trace log.

            This running ID folder that use to keeping trace log data will use
        a parent running ID first. If it does not set, it will use running ID
        instead.

        :rtype: Path
        """
        log_file: Path = (
            Path(unquote_plus(self.url.path))
            / f"run_id={self.parent_run_id or self.run_id}"
        )
        if not log_file.exists():
            log_file.mkdir(parents=True)
        return log_file

    def writer(
        self,
        message: str,
        level: str,
        is_err: bool = False,
    ) -> None:
        """Write a trace message after making to target file and write metadata
        in the same path of standard files.

            The path of logging data will store by format:

            ... ./logs/run_id=<run-id>/metadata.json
            ... ./logs/run_id=<run-id>/stdout.txt
            ... ./logs/run_id=<run-id>/stderr.txt

        :param message: (str) A message after making.
        :param level: (str) A log level.
        :param is_err: A flag for writing with an error trace or not.
        """
        if not dynamic("enable_write_log", extras=self.extras):
            return

        mode: Literal["stdout", "stderr"] = "stderr" if is_err else "stdout"
        trace_meta: TraceMeta = TraceMeta.make(
            mode=mode,
            level=level,
            message=message,
            cutting_id=self.cut_id,
            extras=self.extras,
        )

        with (self.pointer / f"{mode}.txt").open(
            mode="at", encoding="utf-8"
        ) as f:
            fmt: str = dynamic("log_format_file", extras=self.extras)
            f.write(f"{fmt}\n".format(**trace_meta.model_dump()))

        with (self.pointer / METADATA).open(mode="at", encoding="utf-8") as f:
            f.write(trace_meta.model_dump_json() + "\n")

    async def awriter(
        self,
        message: str,
        level: str,
        is_err: bool = False,
    ) -> None:  # pragma: no cov
        """Write with async mode."""
        if not dynamic("enable_write_log", extras=self.extras):
            return

        try:
            import aiofiles
        except ImportError as e:
            raise ImportError("Async mode need aiofiles package") from e

        mode: Literal["stdout", "stderr"] = "stderr" if is_err else "stdout"
        trace_meta: TraceMeta = TraceMeta.make(
            mode=mode,
            level=level,
            message=message,
            cutting_id=self.cut_id,
            extras=self.extras,
        )

        async with aiofiles.open(
            self.pointer / f"{mode}.txt", mode="at", encoding="utf-8"
        ) as f:
            fmt: str = dynamic("log_format_file", extras=self.extras)
            await f.write(f"{fmt}\n".format(**trace_meta.model_dump()))

        async with aiofiles.open(
            self.pointer / METADATA, mode="at", encoding="utf-8"
        ) as f:
            await f.write(trace_meta.model_dump_json() + "\n")


class SQLiteTrace(OutsideTrace):  # pragma: no cov
    """SQLite Trace dataclass that write trace log to the SQLite database file."""

    table_name: ClassVar[str] = "audits"
    schemas: ClassVar[
        str
    ] = """
        run_id              str
        , parent_run_id     str
        , type              str
        , text              str
        , metadata          JSON
        , created_at        datetime
        , updated_at        datetime
        primary key ( run_id )
        """

    @classmethod
    def find_traces(
        cls,
        path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> Iterator[TraceData]:
        raise NotImplementedError("SQLiteTrace does not implement yet.")

    @classmethod
    def find_trace_with_id(
        cls,
        run_id: str,
        force_raise: bool = True,
        *,
        path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> TraceData:
        raise NotImplementedError("SQLiteTrace does not implement yet.")

    def make_message(self, message: str) -> str:
        raise NotImplementedError("SQLiteTrace does not implement yet.")

    def writer(
        self,
        message: str,
        level: str,
        is_err: bool = False,
    ) -> None:
        raise NotImplementedError("SQLiteTrace does not implement yet.")

    def awriter(
        self,
        message: str,
        level: str,
        is_err: bool = False,
    ) -> None:
        raise NotImplementedError("SQLiteTrace does not implement yet.")


Trace = Union[
    FileTrace,
    SQLiteTrace,
    OutsideTrace,
]


def get_trace(
    run_id: str,
    *,
    parent_run_id: Optional[str] = None,
    extras: Optional[DictData] = None,
) -> Trace:  # pragma: no cov
    """Get dynamic Trace instance from the core config (it can override by an
    extras argument) that passing running ID and parent running ID.

    :param run_id: (str) A running ID.
    :param parent_run_id: (str) A parent running ID.
    :param extras: (DictData) An extra parameter that want to override the core
        config values.

    :rtype: Trace
    """
    # NOTE: Allow you to override trace model by the extra parameter.
    map_trace_models: dict[str, type[Trace]] = extras.get(
        "trace_model_mapping", {}
    )
    url: ParseResult
    if (url := dynamic("trace_url", extras=extras)).scheme and (
        url.scheme == "sqlite"
        or (url.scheme == "file" and Path(url.path).is_file())
    ):
        return map_trace_models.get("sqlite", SQLiteTrace)(
            url=url,
            run_id=run_id,
            parent_run_id=parent_run_id,
            extras=(extras or {}),
        )
    elif url.scheme and url.scheme != "file":
        raise NotImplementedError(
            f"Does not implement the outside trace model support for URL: {url}"
        )

    return map_trace_models.get("file", FileTrace)(
        url=url,
        run_id=run_id,
        parent_run_id=parent_run_id,
        extras=(extras or {}),
    )
