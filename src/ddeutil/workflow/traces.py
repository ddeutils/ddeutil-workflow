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
    Message: Log message model with prefix parsing.
    TraceMeta: Metadata model for execution context.
    TraceData: Container for trace information.
    BaseTrace: Abstract base class for trace implementations.
    ConsoleTrace: Console-based trace output.
    FileTrace: File-based trace storage.
    SQLiteTrace: Database-based trace storage.

Functions:
    set_logging: Configure logger with custom formatting.
    get_trace: Factory function for trace instances.

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
from zoneinfo import ZoneInfo

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
        name: Module name to create logger for.

    Returns:
        logging.Logger: Configured logger instance with custom formatting.

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
        "emoji": "⚙️",
        "desc": "logs from any usage from custom caller function.",
    },
    "STAGE": {"emoji": "🔗", "desc": "logs from stages module."},
    "JOB": {"emoji": "⛓️", "desc": "logs from job module."},
    "WORKFLOW": {"emoji": "🏃", "desc": "logs from workflow module."},
    "RELEASE": {"emoji": "📅", "desc": "logs from release workflow method."},
    "POKING": {"emoji": "⏰", "desc": "logs from poke workflow method."},
    "AUDIT": {"emoji": "📌", "desc": "logs from audit model."},
}  # pragma: no cov
PREFIX_DEFAULT: Final[str] = "CALLER"
PREFIX_LOGS_REGEX: Final[re.Pattern[str]] = re.compile(
    rf"(^\[(?P<name>{'|'.join(PREFIX_LOGS)})]:\s?)?(?P<message>.*)",
    re.MULTILINE | re.DOTALL | re.ASCII | re.VERBOSE,
)  # pragma: no cov


class Message(BaseModel):
    """Prefix Message model for receive grouping dict from searching prefix data.

    This model handles prefix parsing and message formatting for logging
    with emoji support and categorization.
    """

    name: Optional[str] = Field(default=None, description="A prefix name.")
    message: Optional[str] = Field(default=None, description="A message.")

    @classmethod
    def from_str(cls, msg: str) -> Self:
        """Extract message prefix from an input message.

        Args:
            msg: A message that want to extract.

        Returns:
            Message: The validated model from a string message.
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
    """Trace Metadata model for making the current metadata of this CPU, Memory.

    This model captures comprehensive execution context including process IDs,
    thread identifiers, timestamps, and contextual information for debugging
    and monitoring workflow executions.
    """

    mode: Literal["stdout", "stderr"] = Field(description="A meta mode.")
    level: str = Field(description="A log level.")
    datetime: str = Field(
        description="A datetime string with the specific config format."
    )
    process: int = Field(description="A process ID.")
    thread: int = Field(description="A thread ID.")
    message: str = Field(description="A message log.")
    cut_id: Optional[str] = Field(
        default=None, description="A cutting of running ID."
    )
    filename: str = Field(description="A filename of this log.")
    lineno: int = Field(description="A line number of this log.")

    # Enhanced observability fields
    workflow_name: Optional[str] = Field(
        default=None, description="Name of the workflow being executed."
    )
    stage_name: Optional[str] = Field(
        default=None, description="Name of the current stage being executed."
    )
    job_name: Optional[str] = Field(
        default=None, description="Name of the current job being executed."
    )

    # Performance metrics
    duration_ms: Optional[float] = Field(
        default=None, description="Execution duration in milliseconds."
    )
    memory_usage_mb: Optional[float] = Field(
        default=None, description="Memory usage in MB at log time."
    )
    cpu_usage_percent: Optional[float] = Field(
        default=None, description="CPU usage percentage at log time."
    )

    # Distributed tracing support
    trace_id: Optional[str] = Field(
        default=None,
        description="OpenTelemetry trace ID for distributed tracing.",
    )
    span_id: Optional[str] = Field(
        default=None,
        description="OpenTelemetry span ID for distributed tracing.",
    )
    parent_span_id: Optional[str] = Field(
        default=None, description="Parent span ID for correlation."
    )

    # Error context
    exception_type: Optional[str] = Field(
        default=None, description="Exception class name if error occurred."
    )
    exception_message: Optional[str] = Field(
        default=None, description="Exception message if error occurred."
    )
    stack_trace: Optional[str] = Field(
        default=None, description="Full stack trace if error occurred."
    )
    error_code: Optional[str] = Field(
        default=None, description="Custom error code for categorization."
    )

    # Business context
    user_id: Optional[str] = Field(
        default=None, description="User ID who triggered the workflow."
    )
    tenant_id: Optional[str] = Field(
        default=None, description="Tenant ID for multi-tenant environments."
    )
    environment: Optional[str] = Field(
        default=None, description="Environment (dev, staging, prod)."
    )

    # System context
    hostname: Optional[str] = Field(
        default=None, description="Hostname where workflow is running."
    )
    ip_address: Optional[str] = Field(
        default=None, description="IP address of the execution host."
    )
    python_version: Optional[str] = Field(
        default=None, description="Python version running the workflow."
    )
    package_version: Optional[str] = Field(
        default=None, description="Workflow package version."
    )

    # Custom metadata
    tags: Optional[list[str]] = Field(
        default_factory=list, description="Custom tags for categorization."
    )
    metadata: Optional[DictData] = Field(
        default_factory=dict, description="Additional custom metadata."
    )

    @classmethod
    def dynamic_frame(
        cls, frame: FrameType, *, extras: Optional[DictData] = None
    ) -> Traceback:
        """Dynamic Frame information base on the `logs_trace_frame_layer` config.

        Args:
            frame: The current frame that want to dynamic.
            extras: An extra parameter that want to get the
                `logs_trace_frame_layer` config value.

        Returns:
            Traceback: The frame information at the specified layer.
        """
        extras_data: DictData = extras or {}
        layer: int = extras_data.get("logs_trace_frame_layer", 4)
        current_frame: FrameType = frame
        for _ in range(layer):
            _frame: Optional[FrameType] = current_frame.f_back
            if _frame is None:
                raise ValueError(
                    f"Layer value does not valid, the maximum frame is: {_ + 1}"
                )
            current_frame = _frame
        return getframeinfo(current_frame)

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
        """Make the current metric for contract this TraceMeta model instance.

        This method captures local states like PID, thread identity, and system
        information to create a comprehensive trace metadata instance.

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
        import socket
        import sys

        frame: Optional[FrameType] = currentframe()
        if frame is None:
            raise ValueError("Cannot get current frame")

        frame_info: Traceback = cls.dynamic_frame(frame, extras=extras)
        extras_data: DictData = extras or {}

        # Get system information
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        # Get datetime format with fallback
        datetime_format = (
            dynamic("log_datetime_format", extras=extras_data)
            or "%Y-%m-%d %H:%M:%S"
        )
        timezone = dynamic("log_tz", extras=extras_data)
        if timezone is None:
            timezone = ZoneInfo("UTC")

        return cls(
            mode=mode,
            level=level,
            datetime=(
                get_dt_now().astimezone(timezone).strftime(datetime_format)
            ),
            process=os.getpid(),
            thread=get_ident(),
            message=message,
            cut_id=cutting_id,
            filename=frame_info.filename.split(os.path.sep)[-1],
            lineno=frame_info.lineno,
            # Enhanced observability fields
            workflow_name=extras_data.get("workflow_name"),
            stage_name=extras_data.get("stage_name"),
            job_name=extras_data.get("job_name"),
            # Performance metrics
            duration_ms=extras_data.get("duration_ms"),
            memory_usage_mb=extras_data.get("memory_usage_mb"),
            cpu_usage_percent=extras_data.get("cpu_usage_percent"),
            # Distributed tracing support
            trace_id=extras_data.get("trace_id"),
            span_id=extras_data.get("span_id"),
            parent_span_id=extras_data.get("parent_span_id"),
            # Error context
            exception_type=extras_data.get("exception_type"),
            exception_message=extras_data.get("exception_message"),
            stack_trace=extras_data.get("stack_trace"),
            error_code=extras_data.get("error_code"),
            # Business context
            user_id=extras_data.get("user_id"),
            tenant_id=extras_data.get("tenant_id"),
            environment=extras_data.get("environment"),
            # System context
            hostname=hostname,
            ip_address=ip_address,
            python_version=python_version,
            package_version=extras_data.get("package_version"),
            # Custom metadata
            tags=extras_data.get("tags", []),
            metadata=extras_data.get("metadata", {}),
        )


class TraceData(BaseModel):  # pragma: no cov
    """Trace Data model for keeping data for any Trace models.

    This model serves as a container for trace information including stdout,
    stderr, and metadata for comprehensive logging and monitoring.
    """

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

        Args:
            file: A trace path.

        Returns:
            Self: The constructed TraceData instance.
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


class BaseEmitTrace(BaseModel, ABC):  # pragma: no cov
    """Base Trace model with abstraction class property.

    This abstract base class provides the foundation for all trace implementations
    with common logging methods and abstract methods that must be implemented
    by concrete trace classes.
    """

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
        """Write a trace message after making to target pointer object.

        The target can be anything be inherited this class and overwrite this method
        such as file, console, or database.

        Args:
            message: A message after making.
            level: A log level.
            is_err: A flag for writing with an error trace or not.
                Defaults to False.
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

        Args:
            message: A message after making.
            level: A log level.
            is_err: A flag for writing with an error trace or not.
                Defaults to False.
        """
        raise NotImplementedError(
            "Create async writer logic for this trace object before using."
        )

    @abstractmethod
    def make_message(self, message: str) -> str:
        """Prepare and Make a message before write and log processes.

        Args:
            message: A message that want to prepare and make before.

        Returns:
            str: The prepared message.
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

        Args:
            message: A message that want to log.
            mode: A logging mode.
            is_err: A flag indicating if this is an error log.
        """
        raise NotImplementedError(
            "Logging action should be implement for making trace log."
        )

    def debug(self, message: str):
        """Write trace log with append mode and logging this message with the
        DEBUG level.

        Args:
            message: A message that want to log.
        """
        self.emit(message, mode="debug")

    def info(self, message: str) -> None:
        """Write trace log with append mode and logging this message with the
        INFO level.

        Args:
            message: A message that want to log.
        """
        self.emit(message, mode="info")

    def warning(self, message: str) -> None:
        """Write trace log with append mode and logging this message with the
        WARNING level.

        Args:
            message: A message that want to log.
        """
        self.emit(message, mode="warning")

    def error(self, message: str) -> None:
        """Write trace log with append mode and logging this message with the
        ERROR level.

        Args:
            message: A message that want to log.
        """
        self.emit(message, mode="error", is_err=True)

    def exception(self, message: str) -> None:
        """Write trace log with append mode and logging this message with the
        EXCEPTION level.

        Args:
            message: A message that want to log.
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

        Args:
            message: A message that want to log.
            mode: A logging mode.
            is_err: A flag indicating if this is an error log.
        """
        raise NotImplementedError(
            "Async Logging action should be implement for making trace log."
        )

    async def adebug(self, message: str) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the DEBUG level.

        Args:
            message: A message that want to log.
        """
        await self.amit(message, mode="debug")

    async def ainfo(self, message: str) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the INFO level.

        Args:
            message: A message that want to log.
        """
        await self.amit(message, mode="info")

    async def awarning(self, message: str) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the WARNING level.

        Args:
            message: A message that want to log.
        """
        await self.amit(message, mode="warning")

    async def aerror(self, message: str) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the ERROR level.

        Args:
            message: A message that want to log.
        """
        await self.amit(message, mode="error", is_err=True)

    async def aexception(self, message: str) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the EXCEPTION level.

        Args:
            message: A message that want to log.
        """
        await self.amit(message, mode="exception", is_err=True)


class ConsoleTrace(BaseEmitTrace):  # pragma: no cov
    """Console Trace log model.

    This class provides console-based trace logging implementation that outputs
    to stdout/stderr with proper formatting and metadata handling.
    """

    def writer(
        self,
        message: str,
        level: str,
        is_err: bool = False,
    ) -> None:
        """Write a trace message after making to target pointer object.

        The target can be anything be inherited this class and overwrite this method
        such as file, console, or database.

        Args:
            message: A message after making.
            level: A log level.
            is_err: A flag for writing with an error trace or not.
                Defaults to False.
        """

    async def awriter(
        self,
        message: str,
        level: str,
        is_err: bool = False,
    ) -> None:
        """Async Write a trace message after making to target pointer object.

        Args:
            message: A message after making.
            level: A log level.
            is_err: A flag for writing with an error trace or not.
                Defaults to False.
        """

    @property
    def cut_id(self) -> str:
        """Combine cutting ID of parent running ID if it set.

        Returns:
            str: The combined cutting ID string.
        """
        cut_run_id: str = cut_id(self.run_id)
        if not self.parent_run_id:
            return f"{cut_run_id}"

        cut_parent_run_id: str = cut_id(self.parent_run_id)
        return f"{cut_parent_run_id} -> {cut_run_id}"

    def make_message(self, message: str) -> str:
        """Prepare and Make a message before write and log steps.

        Args:
            message: A message that want to prepare and make before.

        Returns:
            str: The prepared message.
        """
        return prepare_newline(Message.from_str(message).prepare(self.extras))

    def emit(self, message: str, mode: str, *, is_err: bool = False) -> None:
        """Write trace log with append mode and logging this message with any
        logging level.

        Args:
            message: A message that want to log.
            mode: A logging mode.
            is_err: A flag indicating if this is an error log.
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

        Args:
            message: A message that want to log.
            mode: A logging mode.
            is_err: A flag indicating if this is an error log.
        """
        msg: str = self.make_message(message)

        if mode != "debug" or (
            mode == "debug" and dynamic("debug", extras=self.extras)
        ):
            await self.awriter(msg, level=mode, is_err=is_err)

        getattr(logger, mode)(msg, stacklevel=3, extra={"cut_id": self.cut_id})


class BaseTrace(ConsoleTrace, ABC):
    """A Base Trace model that will use for override writing or sending trace
    log to any service type.

    This abstract base class extends ConsoleTrace and provides additional
    functionality for URL-based trace implementations with file and database
    support.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    url: ParseResult = Field(description="An URL for create pointer.")

    @field_validator(
        "url", mode="before", json_schema_input_type=Union[ParseResult, str]
    )
    def __parse_url(cls, value: Union[ParseResult, str]) -> ParseResult:
        """Parse an URL value.

        Args:
            value: URL value to parse.

        Returns:
            ParseResult: Parsed URL object.
        """
        return urlparse(value) if isinstance(value, str) else value

    @field_serializer("url")
    def __serialize_url(self, value: ParseResult) -> str:
        """Serialize URL to string.

        Args:
            value: ParseResult object to serialize.

        Returns:
            str: URL string representation.
        """
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
            path: A pointer path that want to override.
            extras: An extras parameter that want to override default engine config.

        Returns:
            Iterator[TraceData]: An iterator object that generate a TraceData
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
        """Find trace data by run ID.

        Args:
            run_id: The run ID to search for.
            force_raise: Whether to raise an exception if not found.
            path: Optional path override.
            extras: Optional extras parameter.

        Returns:
            TraceData: The found trace data.

        Raises:
            NotImplementedError: If not implemented by subclass.
        """
        raise NotImplementedError(
            "Trace dataclass should implement `find_trace_with_id` "
            "class-method."
        )


class FileTrace(BaseTrace):  # pragma: no cov
    """File Trace dataclass that write file to the local storage.

    This class provides file-based trace logging implementation that persists
    logs to the local filesystem with structured metadata storage.
    """

    @classmethod
    def find_traces(
        cls,
        path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> Iterator[TraceData]:  # pragma: no cov
        """Find trace logs.

        Args:
            path: A trace path that want to find.
            extras: An extra parameter that want to override core config.
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

        Args:
            run_id: A running ID of trace log.
            force_raise: Whether to raise an exception if not found.
            path: Optional path override.
            extras: An extra parameter that want to override core config.
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

        Returns:
            Path: The target path for trace log operations.
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

        Args:
            message: A message after making.
            level: A log level.
            is_err: A flag for writing with an error trace or not.
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
        """Write with async mode.

        Args:
            message: A message after making.
            level: A log level.
            is_err: A flag for writing with an error trace or not.
        """
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


class SQLiteTrace(BaseTrace):  # pragma: no cov
    """SQLite Trace dataclass that write trace log to the SQLite database file.

    This class provides SQLite-based trace logging implementation for scalable
    deployments with database-backed storage.
    """

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
        primary key ( parent_run_id )
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
    BaseTrace,
]


def get_trace(
    run_id: str,
    *,
    parent_run_id: Optional[str] = None,
    extras: Optional[DictData] = None,
) -> Trace:  # pragma: no cov
    """Get dynamic Trace instance from the core config.

    This factory function returns the appropriate trace implementation based on
    configuration. It can be overridden by extras argument and accepts running ID
    and parent running ID.

    Args:
        run_id: A running ID.
        parent_run_id: A parent running ID.
        extras: An extra parameter that want to override the core
            config values.

    Returns:
        Trace: The appropriate trace instance.
    """
    # NOTE: Allow you to override trace model by the extra parameter.
    map_trace_models: dict[str, type[Trace]] = (extras or {}).get(
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
