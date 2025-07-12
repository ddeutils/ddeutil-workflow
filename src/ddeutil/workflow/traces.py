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
    WorkflowFileHandler: High-performance file logging handler.

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
from threading import Lock, get_ident
from types import FrameType
from typing import Final, Literal, Optional, Union
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


class WorkflowFileHandler(logging.Handler):
    """High-performance file logging handler for workflow traces.

    This handler provides optimized file-based logging with buffering,
    thread safety, and structured metadata storage. It replaces the FileTrace
    model with better performance characteristics.
    """

    def __init__(
        self,
        run_id: str,
        parent_run_id: Optional[str] = None,
        base_path: Optional[Path] = None,
        extras: Optional[DictData] = None,
        buffer_size: int = 8192,
        flush_interval: float = 1.0,
    ):
        """Initialize the workflow file handler.

        Args:
            run_id: The running ID for this trace session.
            parent_run_id: Optional parent running ID.
            base_path: Base path for log files.
            extras: Extra configuration parameters.
            buffer_size: Buffer size for file operations.
            flush_interval: Interval in seconds to flush buffers.
        """
        super().__init__()

        self.run_id = run_id
        self.parent_run_id = parent_run_id
        self.extras = extras or {}
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval

        # Determine base path
        if base_path is None:
            url = dynamic("trace_url", extras=self.extras)
            if (
                url is not None
                and hasattr(url, "path")
                and getattr(url, "path", None)
            ):
                base_path = Path(url.path)
            else:
                base_path = Path("./logs")

        # Create log directory
        self.log_dir = base_path / f"run_id={self.parent_run_id or self.run_id}"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # File handles with buffering
        self.stdout_file = None
        self.stderr_file = None
        self.metadata_file = None

        # Thread safety
        self._lock = Lock()

        # Buffers for performance
        self.stdout_buffer = []
        self.stderr_buffer = []
        self.metadata_buffer = []

        # Initialize files
        self._init_files()

    def _init_files(self):
        """Initialize file handles with buffering."""
        try:
            self.stdout_file = open(
                self.log_dir / "stdout.txt",
                mode="a",
                encoding="utf-8",
                buffering=self.buffer_size,
            )
            self.stderr_file = open(
                self.log_dir / "stderr.txt",
                mode="a",
                encoding="utf-8",
                buffering=self.buffer_size,
            )
            self.metadata_file = open(
                self.log_dir / METADATA,
                mode="a",
                encoding="utf-8",
                buffering=self.buffer_size,
            )
        except Exception as e:
            logger.error(f"Failed to initialize log files: {e}")
            raise

    def _get_cut_id(self) -> str:
        """Get the cutting ID for this trace session."""
        cut_run_id = cut_id(self.run_id)
        if not self.parent_run_id:
            return cut_run_id

        cut_parent_run_id = cut_id(self.parent_run_id)
        return f"{cut_parent_run_id} -> {cut_run_id}"

    def _create_trace_meta(
        self, record: logging.LogRecord, is_err: bool = False
    ) -> TraceMeta:
        """Create trace metadata from log record."""
        mode: Literal["stdout", "stderr"] = "stderr" if is_err else "stdout"

        # Extract additional context from record
        extras_data = self.extras.copy()
        extras_data.update(
            {
                "workflow_name": getattr(record, "workflow_name", None),
                "stage_name": getattr(record, "stage_name", None),
                "job_name": getattr(record, "job_name", None),
                "trace_id": getattr(record, "trace_id", None),
                "span_id": getattr(record, "span_id", None),
                "user_id": getattr(record, "user_id", None),
                "tenant_id": getattr(record, "tenant_id", None),
            }
        )

        return TraceMeta.make(
            mode=mode,
            level=record.levelname.lower(),
            message=record.getMessage(),
            cutting_id=self._get_cut_id(),
            extras=extras_data,
        )

    def _write_buffered(self, file_handle, content: str, buffer_list: list):
        """Write content with buffering for performance."""
        buffer_list.append(content)

        # Flush if buffer is full or contains newlines
        if len(buffer_list) >= 10 or "\n" in content:
            with self._lock:
                for buffered_content in buffer_list:
                    try:
                        file_handle.write(buffered_content)
                    except Exception as e:
                        logger.error(f"Failed to write to log file: {e}")
                file_handle.flush()
                buffer_list.clear()

    def emit(self, record: logging.LogRecord):
        """Emit a log record to the appropriate files."""
        if not dynamic("enable_write_log", extras=self.extras):
            return

        try:
            # Determine if this is an error
            is_err = record.levelno >= logging.ERROR

            # Create trace metadata
            trace_meta = self._create_trace_meta(record, is_err)

            # Format log message
            fmt = (
                dynamic("log_format_file", extras=self.extras)
                or "{datetime} ({process:5d}, {thread:5d}) ({cut_id}) {message:120s} ({filename}:{lineno})"
            )
            formatted_message = fmt.format(**trace_meta.model_dump()) + "\n"

            # Write to appropriate file
            if is_err:
                self._write_buffered(
                    self.stderr_file, formatted_message, self.stderr_buffer
                )
            else:
                self._write_buffered(
                    self.stdout_file, formatted_message, self.stdout_buffer
                )

            # Write metadata
            metadata_json = trace_meta.model_dump_json() + "\n"
            self._write_buffered(
                self.metadata_file, metadata_json, self.metadata_buffer
            )

        except Exception as e:
            logger.error(f"Failed to emit log record: {e}")

    def flush(self):
        """Flush all buffers."""
        with self._lock:
            # Flush stdout buffer
            if self.stdout_buffer and self.stdout_file:
                for content in self.stdout_buffer:
                    self.stdout_file.write(content)
                self.stdout_file.flush()
                self.stdout_buffer.clear()

            # Flush stderr buffer
            if self.stderr_buffer and self.stderr_file:
                for content in self.stderr_buffer:
                    self.stderr_file.write(content)
                self.stderr_file.flush()
                self.stderr_buffer.clear()

            # Flush metadata buffer
            if self.metadata_buffer and self.metadata_file:
                for content in self.metadata_buffer:
                    self.metadata_file.write(content)
                self.metadata_file.flush()
                self.metadata_buffer.clear()

    def close(self):
        """Close the handler and flush all buffers."""
        self.flush()

        if self.stdout_file:
            self.stdout_file.close()
        if self.stderr_file:
            self.stderr_file.close()
        if self.metadata_file:
            self.metadata_file.close()

        super().close()

    @classmethod
    def find_traces(
        cls,
        path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> Iterator[TraceData]:
        """Find trace logs using the same interface as FileTrace."""
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
        force_raise: bool = True,
        *,
        path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> TraceData:
        """Find trace log with specific run ID."""
        base_path = path or Path(dynamic("trace_url", extras=extras).path)
        file = base_path / f"run_id={run_id}"
        if file.exists():
            return TraceData.from_path(file)
        elif force_raise:
            raise FileNotFoundError(
                f"Trace log on path {base_path}, does not found trace "
                f"'run_id={run_id}'."
            )
        return TraceData(stdout="", stderr="")


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


class OptimizedFileTrace(BaseTrace):  # pragma: no cov
    """Optimized File Trace that uses WorkflowFileHandler for better performance.

    This class provides high-performance file-based trace logging using Python's
    built-in logging system with buffering and thread safety.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._handler = None
        self._logger = None
        self._setup_handler()

    def _setup_handler(self):
        """Setup the WorkflowFileHandler for this trace instance."""
        # Create a dedicated logger for this trace session
        self._logger = logging.getLogger(
            f"ddeutil.workflow.trace.{self.run_id}"
        )
        self._logger.setLevel(logging.DEBUG)

        # Remove existing handlers to avoid duplicates
        for handler in self._logger.handlers[:]:
            self._logger.removeHandler(handler)

        # Create and add the file handler
        self._handler = WorkflowFileHandler(
            run_id=self.run_id,
            parent_run_id=self.parent_run_id,
            extras=self.extras,
        )
        self._logger.addHandler(self._handler)

        # Prevent propagation to avoid duplicate logs
        self._logger.propagate = False

    @classmethod
    def find_traces(
        cls,
        path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> Iterator[TraceData]:
        """Find trace logs using WorkflowFileHandler."""
        return WorkflowFileHandler.find_traces(path=path, extras=extras)

    @classmethod
    def find_trace_with_id(
        cls,
        run_id: str,
        force_raise: bool = True,
        *,
        path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> TraceData:
        """Find trace log with specific run ID using WorkflowFileHandler."""
        return WorkflowFileHandler.find_trace_with_id(
            run_id=run_id,
            force_raise=force_raise,
            path=path,
            extras=extras,
        )

    def writer(
        self,
        message: str,
        level: str,
        is_err: bool = False,
    ) -> None:
        """Write using the optimized handler."""
        if not dynamic("enable_write_log", extras=self.extras):
            return

        # Create a log record
        record = logging.LogRecord(
            name=self._logger.name,
            level=getattr(logging, level.upper(), logging.INFO),
            pathname="",
            lineno=0,
            msg=message,
            args=(),
            exc_info=None,
        )

        # Add custom attributes for context
        record.workflow_name = self.extras.get("workflow_name")
        record.stage_name = self.extras.get("stage_name")
        record.job_name = self.extras.get("job_name")
        record.trace_id = self.extras.get("trace_id")
        record.span_id = self.extras.get("span_id")
        record.user_id = self.extras.get("user_id")
        record.tenant_id = self.extras.get("tenant_id")

        # Emit the record
        self._logger.handle(record)

    async def awriter(
        self,
        message: str,
        level: str,
        is_err: bool = False,
    ) -> None:
        """Async write using the optimized handler."""
        # For async operations, we'll use the same synchronous approach
        # since the handler itself handles the I/O efficiently
        self.writer(message, level, is_err)

    def make_message(self, message: str) -> str:
        """Prepare message using the same logic as ConsoleTrace."""
        return prepare_newline(Message.from_str(message).prepare(self.extras))

    def close(self):
        """Close the handler and cleanup."""
        if self._handler:
            self._handler.close()
        if self._logger:
            # Remove the handler from the logger
            for handler in self._logger.handlers[:]:
                self._logger.removeHandler(handler)


class RestAPIHandler(logging.Handler):
    """High-performance REST API logging handler for external monitoring services.

    This handler provides optimized REST API-based logging for external monitoring
    services like Datadog, Grafana, AWS CloudWatch, and other logging platforms.
    It supports batch sending, retry logic, and authentication.
    """

    def __init__(
        self,
        run_id: str,
        parent_run_id: Optional[str] = None,
        api_url: str = "",
        api_key: Optional[str] = None,
        service_type: Literal[
            "datadog", "grafana", "cloudwatch", "generic"
        ] = "generic",
        extras: Optional[DictData] = None,
        buffer_size: int = 50,
        flush_interval: float = 2.0,
        timeout: float = 10.0,
        max_retries: int = 3,
    ):
        """Initialize the REST API logging handler.

        Args:
            run_id: The running ID for this trace session.
            parent_run_id: Optional parent running ID.
            api_url: The REST API endpoint URL.
            api_key: API key for authentication.
            service_type: Type of monitoring service.
            extras: Extra configuration parameters.
            buffer_size: Number of records to buffer before sending.
            flush_interval: Interval in seconds to flush buffers.
            timeout: HTTP request timeout in seconds.
            max_retries: Maximum number of retry attempts.
        """
        super().__init__()

        self.run_id = run_id
        self.parent_run_id = parent_run_id
        self.api_url = api_url
        self.api_key = api_key
        self.service_type = service_type
        self.extras = extras or {}
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.timeout = timeout
        self.max_retries = max_retries

        # Thread safety
        self._lock = Lock()

        # Buffers for performance
        self.log_buffer = []

        # Initialize HTTP session
        self._init_session()

    def _init_session(self):
        """Initialize HTTP session with proper configuration."""
        try:
            import requests

            self.session = requests.Session()

            # Set default headers
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "ddeutil-workflow/1.0",
            }

            # Add service-specific headers
            if self.service_type == "datadog":
                if self.api_key:
                    headers["DD-API-KEY"] = self.api_key
                headers["Content-Type"] = "application/json"
            elif self.service_type == "grafana":
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
            elif self.service_type == "cloudwatch":
                if self.api_key:
                    headers["X-Amz-Target"] = "Logs_20140328.PutLogEvents"
                    headers["Authorization"] = (
                        f"AWS4-HMAC-SHA256 {self.api_key}"
                    )

            self.session.headers.update(headers)

        except ImportError as e:
            raise ImportError(
                "REST API handler requires 'requests' package"
            ) from e

    def _get_cut_id(self) -> str:
        """Get the cutting ID for this trace session."""
        cut_run_id = cut_id(self.run_id)
        if not self.parent_run_id:
            return cut_run_id

        cut_parent_run_id = cut_id(self.parent_run_id)
        return f"{cut_parent_run_id} -> {cut_run_id}"

    def _create_trace_meta(
        self, record: logging.LogRecord, is_err: bool = False
    ) -> TraceMeta:
        """Create trace metadata from log record."""
        mode: Literal["stdout", "stderr"] = "stderr" if is_err else "stdout"

        # Extract additional context from record
        extras_data = self.extras.copy()
        extras_data.update(
            {
                "workflow_name": getattr(record, "workflow_name", None),
                "stage_name": getattr(record, "stage_name", None),
                "job_name": getattr(record, "job_name", None),
                "trace_id": getattr(record, "trace_id", None),
                "span_id": getattr(record, "span_id", None),
                "user_id": getattr(record, "user_id", None),
                "tenant_id": getattr(record, "tenant_id", None),
            }
        )

        return TraceMeta.make(
            mode=mode,
            level=record.levelname.lower(),
            message=record.getMessage(),
            cutting_id=self._get_cut_id(),
            extras=extras_data,
        )

    def _format_for_service(self, trace_meta: TraceMeta) -> dict:
        """Format trace metadata for specific service."""
        base_data = trace_meta.model_dump()

        if self.service_type == "datadog":
            return {
                "message": base_data["message"],
                "level": base_data["level"],
                "timestamp": base_data["datetime"],
                "service": "ddeutil-workflow",
                "source": "python",
                "tags": [
                    f"run_id:{self.run_id}",
                    (
                        f"parent_run_id:{self.parent_run_id}"
                        if self.parent_run_id
                        else None
                    ),
                    f"mode:{base_data['mode']}",
                    f"filename:{base_data['filename']}",
                    f"lineno:{base_data['lineno']}",
                    f"process:{base_data['process']}",
                    f"thread:{base_data['thread']}",
                ]
                + (base_data.get("tags", []) or []),
                "dd": {
                    "source": "python",
                    "service": "ddeutil-workflow",
                    "tags": base_data.get("tags", []) or [],
                },
                "workflow": {
                    "run_id": self.run_id,
                    "parent_run_id": self.parent_run_id,
                    "workflow_name": base_data.get("workflow_name"),
                    "stage_name": base_data.get("stage_name"),
                    "job_name": base_data.get("job_name"),
                },
                "trace": {
                    "trace_id": base_data.get("trace_id"),
                    "span_id": base_data.get("span_id"),
                    "parent_span_id": base_data.get("parent_span_id"),
                },
            }

        elif self.service_type == "grafana":
            return {
                "streams": [
                    {
                        "stream": {
                            "run_id": self.run_id,
                            "parent_run_id": self.parent_run_id,
                            "level": base_data["level"],
                            "mode": base_data["mode"],
                            "service": "ddeutil-workflow",
                        },
                        "values": [
                            [
                                str(
                                    int(
                                        trace_meta.datetime.replace(
                                            " ", "T"
                                        ).replace(":", "")
                                    )
                                ),
                                base_data["message"],
                            ]
                        ],
                    }
                ]
            }

        elif self.service_type == "cloudwatch":
            return {
                "logGroupName": f"/ddeutil/workflow/{self.run_id}",
                "logStreamName": f"workflow-{self.run_id}",
                "logEvents": [
                    {
                        "timestamp": int(
                            trace_meta.datetime.replace(" ", "T").replace(
                                ":", ""
                            )
                        ),
                        "message": json.dumps(
                            {
                                "message": base_data["message"],
                                "level": base_data["level"],
                                "run_id": self.run_id,
                                "parent_run_id": self.parent_run_id,
                                "mode": base_data["mode"],
                                "filename": base_data["filename"],
                                "lineno": base_data["lineno"],
                                "process": base_data["process"],
                                "thread": base_data["thread"],
                                "workflow_name": base_data.get("workflow_name"),
                                "stage_name": base_data.get("stage_name"),
                                "job_name": base_data.get("job_name"),
                                "trace_id": base_data.get("trace_id"),
                                "span_id": base_data.get("span_id"),
                            }
                        ),
                    }
                ],
            }

        else:  # generic
            return {
                "timestamp": base_data["datetime"],
                "level": base_data["level"],
                "message": base_data["message"],
                "run_id": self.run_id,
                "parent_run_id": self.parent_run_id,
                "mode": base_data["mode"],
                "filename": base_data["filename"],
                "lineno": base_data["lineno"],
                "process": base_data["process"],
                "thread": base_data["thread"],
                "workflow_name": base_data.get("workflow_name"),
                "stage_name": base_data.get("stage_name"),
                "job_name": base_data.get("job_name"),
                "trace_id": base_data.get("trace_id"),
                "span_id": base_data.get("span_id"),
                "tags": base_data.get("tags", []),
                "metadata": base_data.get("metadata", {}),
            }

    def _send_batch(self, records: list[TraceMeta]) -> bool:
        """Send a batch of records to the REST API."""
        if not records:
            return True

        try:
            # Format records for the service
            formatted_records = [
                self._format_for_service(record) for record in records
            ]

            # Prepare payload based on service type
            if self.service_type == "datadog":
                payload = formatted_records
            elif self.service_type == "grafana":
                # Merge all streams
                all_streams = []
                for record in formatted_records:
                    all_streams.extend(record["streams"])
                payload = {"streams": all_streams}
            elif self.service_type == "cloudwatch":
                # CloudWatch expects individual log events
                payload = formatted_records[0]  # Take first record
            else:
                payload = formatted_records

            # Send with retry logic
            for attempt in range(self.max_retries):
                try:
                    response = self.session.post(
                        self.api_url, json=payload, timeout=self.timeout
                    )
                    response.raise_for_status()
                    return True

                except Exception as e:
                    if attempt == self.max_retries - 1:
                        logger.error(
                            f"Failed to send logs to REST API after {self.max_retries} attempts: {e}"
                        )
                        return False
                    else:
                        import time

                        time.sleep(2**attempt)  # Exponential backoff

        except Exception as e:
            logger.error(f"Failed to send logs to REST API: {e}")
            return False

    def _write_buffered(self, trace_meta: TraceMeta):
        """Write trace metadata to buffer."""
        self.log_buffer.append(trace_meta)

        # Flush if buffer is full
        if len(self.log_buffer) >= self.buffer_size:
            self.flush()

    def emit(self, record: logging.LogRecord):
        """Emit a log record to REST API."""
        if not dynamic("enable_write_log", extras=self.extras):
            return

        try:
            # Determine if this is an error
            is_err = record.levelno >= logging.ERROR

            # Create trace metadata
            trace_meta = self._create_trace_meta(record, is_err)

            # Write to buffer
            self._write_buffered(trace_meta)

        except Exception as e:
            logger.error(f"Failed to emit log record: {e}")

    def flush(self):
        """Flush all buffered records to REST API."""
        if not self.log_buffer:
            return

        with self._lock:
            records_to_send = self.log_buffer.copy()
            self.log_buffer.clear()

            if records_to_send:
                self._send_batch(records_to_send)

    def close(self):
        """Close the handler and flush all buffers."""
        self.flush()
        if hasattr(self, "session"):
            self.session.close()
        super().close()


class ElasticsearchHandler(logging.Handler):
    """High-performance Elasticsearch logging handler for workflow traces.

    This handler provides optimized Elasticsearch-based logging with connection
    pooling, bulk indexing, and structured metadata storage for scalable
    log aggregation and search capabilities.
    """

    def __init__(
        self,
        run_id: str,
        parent_run_id: Optional[str] = None,
        es_hosts: Union[str, list[str]] = "http://localhost:9200",
        index_name: str = "workflow-traces",
        username: Optional[str] = None,
        password: Optional[str] = None,
        extras: Optional[DictData] = None,
        buffer_size: int = 100,
        flush_interval: float = 2.0,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """Initialize the Elasticsearch logging handler.

        Args:
            run_id: The running ID for this trace session.
            parent_run_id: Optional parent running ID.
            es_hosts: Elasticsearch hosts (string or list).
            index_name: Elasticsearch index name.
            username: Elasticsearch username.
            password: Elasticsearch password.
            extras: Extra configuration parameters.
            buffer_size: Number of records to buffer before indexing.
            flush_interval: Interval in seconds to flush buffers.
            timeout: Elasticsearch request timeout in seconds.
            max_retries: Maximum number of retry attempts.
        """
        super().__init__()

        self.run_id = run_id
        self.parent_run_id = parent_run_id
        self.es_hosts = es_hosts
        self.index_name = index_name
        self.username = username
        self.password = password
        self.extras = extras or {}
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.timeout = timeout
        self.max_retries = max_retries

        # Thread safety
        self._lock = Lock()

        # Buffers for performance
        self.log_buffer = []

        # Initialize Elasticsearch client
        self._init_client()

    def _init_client(self):
        """Initialize Elasticsearch client."""
        try:
            from elasticsearch import Elasticsearch

            # Parse hosts
            if isinstance(self.es_hosts, str):
                hosts = [self.es_hosts]
            else:
                hosts = self.es_hosts

            # Create client
            self.client = Elasticsearch(
                hosts=hosts,
                basic_auth=(
                    (self.username, self.password)
                    if self.username and self.password
                    else None
                ),
                timeout=self.timeout,
                max_retries=self.max_retries,
                retry_on_timeout=True,
            )

            # Test connection
            if not self.client.ping():
                raise ConnectionError("Failed to connect to Elasticsearch")

            # Create index if it doesn't exist
            self._create_index()

        except ImportError as e:
            raise ImportError(
                "Elasticsearch handler requires 'elasticsearch' package"
            ) from e

    def _create_index(self):
        """Create Elasticsearch index with proper mapping."""
        try:
            if not self.client.indices.exists(index=self.index_name):
                mapping = {
                    "mappings": {
                        "properties": {
                            "run_id": {"type": "keyword"},
                            "parent_run_id": {"type": "keyword"},
                            "level": {"type": "keyword"},
                            "message": {"type": "text"},
                            "mode": {"type": "keyword"},
                            "datetime": {"type": "date"},
                            "process": {"type": "integer"},
                            "thread": {"type": "integer"},
                            "filename": {"type": "keyword"},
                            "lineno": {"type": "integer"},
                            "cut_id": {"type": "keyword"},
                            "workflow_name": {"type": "keyword"},
                            "stage_name": {"type": "keyword"},
                            "job_name": {"type": "keyword"},
                            "duration_ms": {"type": "float"},
                            "memory_usage_mb": {"type": "float"},
                            "cpu_usage_percent": {"type": "float"},
                            "trace_id": {"type": "keyword"},
                            "span_id": {"type": "keyword"},
                            "parent_span_id": {"type": "keyword"},
                            "exception_type": {"type": "keyword"},
                            "exception_message": {"type": "text"},
                            "stack_trace": {"type": "text"},
                            "error_code": {"type": "keyword"},
                            "user_id": {"type": "keyword"},
                            "tenant_id": {"type": "keyword"},
                            "environment": {"type": "keyword"},
                            "hostname": {"type": "keyword"},
                            "ip_address": {"type": "ip"},
                            "python_version": {"type": "keyword"},
                            "package_version": {"type": "keyword"},
                            "tags": {"type": "keyword"},
                            "metadata": {"type": "object"},
                            "created_at": {"type": "date"},
                        }
                    },
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0,
                        "refresh_interval": "1s",
                    },
                }

                self.client.indices.create(index=self.index_name, body=mapping)

        except Exception as e:
            logger.error(f"Failed to create Elasticsearch index: {e}")

    def _get_cut_id(self) -> str:
        """Get the cutting ID for this trace session."""
        cut_run_id = cut_id(self.run_id)
        if not self.parent_run_id:
            return cut_run_id

        cut_parent_run_id = cut_id(self.parent_run_id)
        return f"{cut_parent_run_id} -> {cut_run_id}"

    def _create_trace_meta(
        self, record: logging.LogRecord, is_err: bool = False
    ) -> TraceMeta:
        """Create trace metadata from log record."""
        mode: Literal["stdout", "stderr"] = "stderr" if is_err else "stdout"

        # Extract additional context from record
        extras_data = self.extras.copy()
        extras_data.update(
            {
                "workflow_name": getattr(record, "workflow_name", None),
                "stage_name": getattr(record, "stage_name", None),
                "job_name": getattr(record, "job_name", None),
                "trace_id": getattr(record, "trace_id", None),
                "span_id": getattr(record, "span_id", None),
                "user_id": getattr(record, "user_id", None),
                "tenant_id": getattr(record, "tenant_id", None),
            }
        )

        return TraceMeta.make(
            mode=mode,
            level=record.levelname.lower(),
            message=record.getMessage(),
            cutting_id=self._get_cut_id(),
            extras=extras_data,
        )

    def _format_for_elasticsearch(self, trace_meta: TraceMeta) -> dict:
        """Format trace metadata for Elasticsearch indexing."""
        base_data = trace_meta.model_dump()

        # Convert datetime to ISO format for Elasticsearch
        from datetime import datetime

        try:
            dt = datetime.strptime(base_data["datetime"], "%Y-%m-%d %H:%M:%S")
            iso_datetime = dt.isoformat()
        except:
            iso_datetime = base_data["datetime"]

        return {
            "run_id": self.run_id,
            "parent_run_id": self.parent_run_id,
            "level": base_data["level"],
            "message": base_data["message"],
            "mode": base_data["mode"],
            "datetime": iso_datetime,
            "process": base_data["process"],
            "thread": base_data["thread"],
            "filename": base_data["filename"],
            "lineno": base_data["lineno"],
            "cut_id": base_data["cut_id"],
            "workflow_name": base_data.get("workflow_name"),
            "stage_name": base_data.get("stage_name"),
            "job_name": base_data.get("job_name"),
            "duration_ms": base_data.get("duration_ms"),
            "memory_usage_mb": base_data.get("memory_usage_mb"),
            "cpu_usage_percent": base_data.get("cpu_usage_percent"),
            "trace_id": base_data.get("trace_id"),
            "span_id": base_data.get("span_id"),
            "parent_span_id": base_data.get("parent_span_id"),
            "exception_type": base_data.get("exception_type"),
            "exception_message": base_data.get("exception_message"),
            "stack_trace": base_data.get("stack_trace"),
            "error_code": base_data.get("error_code"),
            "user_id": base_data.get("user_id"),
            "tenant_id": base_data.get("tenant_id"),
            "environment": base_data.get("environment"),
            "hostname": base_data.get("hostname"),
            "ip_address": base_data.get("ip_address"),
            "python_version": base_data.get("python_version"),
            "package_version": base_data.get("package_version"),
            "tags": base_data.get("tags", []),
            "metadata": base_data.get("metadata", {}),
            "created_at": iso_datetime,
        }

    def _index_batch(self, records: list[TraceMeta]) -> bool:
        """Index a batch of records to Elasticsearch."""
        if not records:
            return True

        try:
            # Format records for Elasticsearch
            formatted_records = [
                self._format_for_elasticsearch(record) for record in records
            ]

            # Prepare bulk operations
            bulk_data = []
            for record in formatted_records:
                bulk_data.append(
                    {
                        "index": {
                            "_index": self.index_name,
                            "_id": f"{self.run_id}_{record['datetime']}_{record['thread']}",
                        }
                    }
                )
                bulk_data.append(record)

            # Execute bulk indexing
            response = self.client.bulk(body=bulk_data, refresh=True)

            # Check for errors
            if response.get("errors", False):
                for item in response.get("items", []):
                    if "index" in item and "error" in item["index"]:
                        logger.error(
                            f"Elasticsearch indexing error: {item['index']['error']}"
                        )
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to index logs to Elasticsearch: {e}")
            return False

    def _write_buffered(self, trace_meta: TraceMeta):
        """Write trace metadata to buffer."""
        self.log_buffer.append(trace_meta)

        # Flush if buffer is full
        if len(self.log_buffer) >= self.buffer_size:
            self.flush()

    def emit(self, record: logging.LogRecord):
        """Emit a log record to Elasticsearch."""
        if not dynamic("enable_write_log", extras=self.extras):
            return

        try:
            # Determine if this is an error
            is_err = record.levelno >= logging.ERROR

            # Create trace metadata
            trace_meta = self._create_trace_meta(record, is_err)

            # Write to buffer
            self._write_buffered(trace_meta)

        except Exception as e:
            logger.error(f"Failed to emit log record: {e}")

    def flush(self):
        """Flush all buffered records to Elasticsearch."""
        if not self.log_buffer:
            return

        with self._lock:
            records_to_index = self.log_buffer.copy()
            self.log_buffer.clear()

            if records_to_index:
                self._index_batch(records_to_index)

    def close(self):
        """Close the handler and flush all buffers."""
        self.flush()
        if hasattr(self, "client"):
            self.client.close()
        super().close()

    @classmethod
    def find_traces(
        cls,
        es_hosts: Union[str, list[str]] = "http://localhost:9200",
        index_name: str = "workflow-traces",
        username: Optional[str] = None,
        password: Optional[str] = None,
        extras: Optional[DictData] = None,
    ) -> Iterator[TraceData]:
        """Find trace logs from Elasticsearch."""
        try:
            from elasticsearch import Elasticsearch

            # Create client
            client = Elasticsearch(
                hosts=es_hosts if isinstance(es_hosts, list) else [es_hosts],
                basic_auth=(
                    (username, password) if username and password else None
                ),
            )

            # Search for all unique run IDs
            search_body = {
                "size": 0,
                "aggs": {
                    "unique_runs": {"terms": {"field": "run_id", "size": 1000}}
                },
            }

            response = client.search(index=index_name, body=search_body)

            for bucket in response["aggregations"]["unique_runs"]["buckets"]:
                run_id = bucket["key"]

                # Get all records for this run
                search_body = {
                    "query": {"term": {"run_id": run_id}},
                    "sort": [{"created_at": {"order": "asc"}}],
                    "size": 1000,
                }

                response = client.search(index=index_name, body=search_body)

                # Convert to TraceData format
                stdout_lines = []
                stderr_lines = []
                meta_list = []

                for hit in response["hits"]["hits"]:
                    source = hit["_source"]

                    # Convert to TraceMeta
                    trace_meta = TraceMeta(
                        mode=source["mode"],
                        level=source["level"],
                        datetime=source["datetime"],
                        process=source["process"],
                        thread=source["thread"],
                        message=source["message"],
                        cut_id=source.get("cut_id"),
                        filename=source["filename"],
                        lineno=source["lineno"],
                        workflow_name=source.get("workflow_name"),
                        stage_name=source.get("stage_name"),
                        job_name=source.get("job_name"),
                        duration_ms=source.get("duration_ms"),
                        memory_usage_mb=source.get("memory_usage_mb"),
                        cpu_usage_percent=source.get("cpu_usage_percent"),
                        trace_id=source.get("trace_id"),
                        span_id=source.get("span_id"),
                        parent_span_id=source.get("parent_span_id"),
                        exception_type=source.get("exception_type"),
                        exception_message=source.get("exception_message"),
                        stack_trace=source.get("stack_trace"),
                        error_code=source.get("error_code"),
                        user_id=source.get("user_id"),
                        tenant_id=source.get("tenant_id"),
                        environment=source.get("environment"),
                        hostname=source.get("hostname"),
                        ip_address=source.get("ip_address"),
                        python_version=source.get("python_version"),
                        package_version=source.get("package_version"),
                        tags=source.get("tags", []),
                        metadata=source.get("metadata", {}),
                    )

                    meta_list.append(trace_meta)

                    # Add to stdout/stderr based on mode
                    fmt = (
                        dynamic("log_format_file", extras=extras)
                        or "{datetime} ({process:5d}, {thread:5d}) ({cut_id}) {message:120s} ({filename}:{lineno})"
                    )
                    formatted_line = fmt.format(**trace_meta.model_dump())

                    if trace_meta.mode == "stdout":
                        stdout_lines.append(formatted_line)
                    else:
                        stderr_lines.append(formatted_line)

                yield TraceData(
                    stdout="\n".join(stdout_lines),
                    stderr="\n".join(stderr_lines),
                    meta=meta_list,
                )

            client.close()

        except Exception as e:
            logger.error(f"Failed to read from Elasticsearch: {e}")

    @classmethod
    def find_trace_with_id(
        cls,
        run_id: str,
        force_raise: bool = True,
        *,
        es_hosts: Union[str, list[str]] = "http://localhost:9200",
        index_name: str = "workflow-traces",
        username: Optional[str] = None,
        password: Optional[str] = None,
        extras: Optional[DictData] = None,
    ) -> TraceData:
        """Find trace log with specific run ID from Elasticsearch."""
        try:
            from elasticsearch import Elasticsearch

            # Create client
            client = Elasticsearch(
                hosts=es_hosts if isinstance(es_hosts, list) else [es_hosts],
                basic_auth=(
                    (username, password) if username and password else None
                ),
            )

            # Search for specific run ID
            search_body = {
                "query": {"term": {"run_id": run_id}},
                "sort": [{"created_at": {"order": "asc"}}],
                "size": 1000,
            }

            response = client.search(index=index_name, body=search_body)

            if not response["hits"]["hits"]:
                if force_raise:
                    raise FileNotFoundError(
                        f"Trace log with run_id '{run_id}' not found in Elasticsearch"
                    )
                return TraceData(stdout="", stderr="")

            # Convert to TraceData format
            stdout_lines = []
            stderr_lines = []
            meta_list = []

            for hit in response["hits"]["hits"]:
                source = hit["_source"]

                # Convert to TraceMeta
                trace_meta = TraceMeta(
                    mode=source["mode"],
                    level=source["level"],
                    datetime=source["datetime"],
                    process=source["process"],
                    thread=source["thread"],
                    message=source["message"],
                    cut_id=source.get("cut_id"),
                    filename=source["filename"],
                    lineno=source["lineno"],
                    workflow_name=source.get("workflow_name"),
                    stage_name=source.get("stage_name"),
                    job_name=source.get("job_name"),
                    duration_ms=source.get("duration_ms"),
                    memory_usage_mb=source.get("memory_usage_mb"),
                    cpu_usage_percent=source.get("cpu_usage_percent"),
                    trace_id=source.get("trace_id"),
                    span_id=source.get("span_id"),
                    parent_span_id=source.get("parent_span_id"),
                    exception_type=source.get("exception_type"),
                    exception_message=source.get("exception_message"),
                    stack_trace=source.get("stack_trace"),
                    error_code=source.get("error_code"),
                    user_id=source.get("user_id"),
                    tenant_id=source.get("tenant_id"),
                    environment=source.get("environment"),
                    hostname=source.get("hostname"),
                    ip_address=source.get("ip_address"),
                    python_version=source.get("python_version"),
                    package_version=source.get("package_version"),
                    tags=source.get("tags", []),
                    metadata=source.get("metadata", {}),
                )

                meta_list.append(trace_meta)

                # Add to stdout/stderr based on mode
                fmt = (
                    dynamic("log_format_file", extras=extras)
                    or "{datetime} ({process:5d}, {thread:5d}) ({cut_id}) {message:120s} ({filename}:{lineno})"
                )
                formatted_line = fmt.format(**trace_meta.model_dump())

                if trace_meta.mode == "stdout":
                    stdout_lines.append(formatted_line)
                else:
                    stderr_lines.append(formatted_line)

            client.close()

            return TraceData(
                stdout="\n".join(stdout_lines),
                stderr="\n".join(stderr_lines),
                meta=meta_list,
            )

        except Exception as e:
            logger.error(f"Failed to read from Elasticsearch: {e}")
            if force_raise:
                raise
            return TraceData(stdout="", stderr="")


class SQLiteHandler(logging.Handler):
    """High-performance SQLite logging handler for workflow traces.

    This handler provides optimized SQLite-based logging with connection pooling,
    thread safety, and structured metadata storage. It replaces the placeholder
    SQLiteTrace implementation with a fully functional database-backed system.
    """

    def __init__(
        self,
        run_id: str,
        parent_run_id: Optional[str] = None,
        db_path: Optional[Path] = None,
        extras: Optional[DictData] = None,
        buffer_size: int = 100,
        flush_interval: float = 1.0,
    ):
        """Initialize the SQLite logging handler.

        Args:
            run_id: The running ID for this trace session.
            parent_run_id: Optional parent running ID.
            db_path: Path to SQLite database file.
            extras: Extra configuration parameters.
            buffer_size: Number of records to buffer before writing.
            flush_interval: Interval in seconds to flush buffers.
        """
        super().__init__()

        self.run_id = run_id
        self.parent_run_id = parent_run_id
        self.extras = extras or {}
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval

        # Determine database path
        if db_path is None:
            url = dynamic("trace_url", extras=self.extras)
            if (
                url is not None
                and hasattr(url, "path")
                and getattr(url, "path", None)
            ):
                db_path = Path(url.path)
            else:
                db_path = Path("./logs/workflow_traces.db")

        # Ensure directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path

        # Thread safety
        self._lock = Lock()

        # Buffers for performance
        self.log_buffer = []

        # Initialize database
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database with proper schema."""
        import sqlite3

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Create traces table if it doesn't exist
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS traces (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id TEXT NOT NULL,
                        parent_run_id TEXT,
                        level TEXT NOT NULL,
                        message TEXT NOT NULL,
                        mode TEXT NOT NULL,
                        datetime TEXT NOT NULL,
                        process INTEGER NOT NULL,
                        thread INTEGER NOT NULL,
                        filename TEXT NOT NULL,
                        lineno INTEGER NOT NULL,
                        cut_id TEXT,
                        workflow_name TEXT,
                        stage_name TEXT,
                        job_name TEXT,
                        duration_ms REAL,
                        memory_usage_mb REAL,
                        cpu_usage_percent REAL,
                        trace_id TEXT,
                        span_id TEXT,
                        parent_span_id TEXT,
                        exception_type TEXT,
                        exception_message TEXT,
                        stack_trace TEXT,
                        error_code TEXT,
                        user_id TEXT,
                        tenant_id TEXT,
                        environment TEXT,
                        hostname TEXT,
                        ip_address TEXT,
                        python_version TEXT,
                        package_version TEXT,
                        tags TEXT,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                # Create indexes for better performance
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_traces_run_id
                    ON traces(run_id)
                """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_traces_parent_run_id
                    ON traces(parent_run_id)
                """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_traces_datetime
                    ON traces(datetime)
                """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_traces_level
                    ON traces(level)
                """
                )

                conn.commit()

        except Exception as e:
            logger.error(f"Failed to initialize SQLite database: {e}")
            raise

    def _get_cut_id(self) -> str:
        """Get the cutting ID for this trace session."""
        cut_run_id = cut_id(self.run_id)
        if not self.parent_run_id:
            return cut_run_id

        cut_parent_run_id = cut_id(self.parent_run_id)
        return f"{cut_parent_run_id} -> {cut_run_id}"

    def _create_trace_meta(
        self, record: logging.LogRecord, is_err: bool = False
    ) -> TraceMeta:
        """Create trace metadata from log record."""
        mode: Literal["stdout", "stderr"] = "stderr" if is_err else "stdout"

        # Extract additional context from record
        extras_data = self.extras.copy()
        extras_data.update(
            {
                "workflow_name": getattr(record, "workflow_name", None),
                "stage_name": getattr(record, "stage_name", None),
                "job_name": getattr(record, "job_name", None),
                "trace_id": getattr(record, "trace_id", None),
                "span_id": getattr(record, "span_id", None),
                "user_id": getattr(record, "user_id", None),
                "tenant_id": getattr(record, "tenant_id", None),
            }
        )

        return TraceMeta.make(
            mode=mode,
            level=record.levelname.lower(),
            message=record.getMessage(),
            cutting_id=self._get_cut_id(),
            extras=extras_data,
        )

    def _write_buffered(self, trace_meta: TraceMeta):
        """Write trace metadata to buffer."""
        self.log_buffer.append(trace_meta)

        # Flush if buffer is full
        if len(self.log_buffer) >= self.buffer_size:
            self.flush()

    def emit(self, record: logging.LogRecord):
        """Emit a log record to SQLite database."""
        if not dynamic("enable_write_log", extras=self.extras):
            return

        try:
            # Determine if this is an error
            is_err = record.levelno >= logging.ERROR

            # Create trace metadata
            trace_meta = self._create_trace_meta(record, is_err)

            # Write to buffer
            self._write_buffered(trace_meta)

        except Exception as e:
            logger.error(f"Failed to emit log record: {e}")

    def flush(self):
        """Flush all buffered records to database."""
        if not self.log_buffer:
            return

        import sqlite3

        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()

                    # Prepare batch insert
                    records = []
                    for trace_meta in self.log_buffer:
                        records.append(
                            (
                                self.run_id,
                                self.parent_run_id,
                                trace_meta.level,
                                trace_meta.message,
                                trace_meta.mode,
                                trace_meta.datetime,
                                trace_meta.process,
                                trace_meta.thread,
                                trace_meta.filename,
                                trace_meta.lineno,
                                trace_meta.cut_id,
                                trace_meta.workflow_name,
                                trace_meta.stage_name,
                                trace_meta.job_name,
                                trace_meta.duration_ms,
                                trace_meta.memory_usage_mb,
                                trace_meta.cpu_usage_percent,
                                trace_meta.trace_id,
                                trace_meta.span_id,
                                trace_meta.parent_span_id,
                                trace_meta.exception_type,
                                trace_meta.exception_message,
                                trace_meta.stack_trace,
                                trace_meta.error_code,
                                trace_meta.user_id,
                                trace_meta.tenant_id,
                                trace_meta.environment,
                                trace_meta.hostname,
                                trace_meta.ip_address,
                                trace_meta.python_version,
                                trace_meta.package_version,
                                (
                                    json.dumps(trace_meta.tags)
                                    if trace_meta.tags
                                    else None
                                ),
                                (
                                    json.dumps(trace_meta.metadata)
                                    if trace_meta.metadata
                                    else None
                                ),
                            )
                        )

                    # Batch insert
                    cursor.executemany(
                        """
                        INSERT INTO traces (
                            run_id, parent_run_id, level, message, mode, datetime,
                            process, thread, filename, lineno, cut_id, workflow_name,
                            stage_name, job_name, duration_ms, memory_usage_mb,
                            cpu_usage_percent, trace_id, span_id, parent_span_id,
                            exception_type, exception_message, stack_trace, error_code,
                            user_id, tenant_id, environment, hostname, ip_address,
                            python_version, package_version, tags, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        records,
                    )

                    conn.commit()

            except Exception as e:
                logger.error(f"Failed to flush to SQLite database: {e}")
            finally:
                self.log_buffer.clear()

    def close(self):
        """Close the handler and flush all buffers."""
        self.flush()
        super().close()

    @classmethod
    def find_traces(
        cls,
        db_path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> Iterator[TraceData]:
        """Find trace logs from SQLite database."""
        if db_path is None:
            url = dynamic("trace_url", extras=extras)
            if (
                url is not None
                and hasattr(url, "path")
                and getattr(url, "path", None)
            ):
                db_path = Path(url.path)
            else:
                db_path = Path("./logs/workflow_traces.db")

        if not db_path.exists():
            return

        import sqlite3

        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                # Get all unique run IDs
                cursor.execute(
                    """
                    SELECT DISTINCT run_id, parent_run_id, created_at
                    FROM traces
                    ORDER BY created_at DESC
                """
                )

                for run_id, parent_run_id, created_at in cursor.fetchall():
                    # Get all records for this run
                    cursor.execute(
                        """
                        SELECT * FROM traces
                        WHERE run_id = ?
                        ORDER BY created_at
                    """,
                        (run_id,),
                    )

                    records = cursor.fetchall()

                    # Convert to TraceData format
                    stdout_lines = []
                    stderr_lines = []
                    meta_list = []

                    for record in records:
                        # Convert record to TraceMeta
                        trace_meta = TraceMeta(
                            mode=record[5],  # mode
                            level=record[3],  # level
                            datetime=record[6],  # datetime
                            process=record[7],  # process
                            thread=record[8],  # thread
                            message=record[4],  # message
                            cut_id=record[11],  # cut_id
                            filename=record[9],  # filename
                            lineno=record[10],  # lineno
                            workflow_name=record[12],  # workflow_name
                            stage_name=record[13],  # stage_name
                            job_name=record[14],  # job_name
                            duration_ms=record[15],  # duration_ms
                            memory_usage_mb=record[16],  # memory_usage_mb
                            cpu_usage_percent=record[17],  # cpu_usage_percent
                            trace_id=record[18],  # trace_id
                            span_id=record[19],  # span_id
                            parent_span_id=record[20],  # parent_span_id
                            exception_type=record[21],  # exception_type
                            exception_message=record[22],  # exception_message
                            stack_trace=record[23],  # stack_trace
                            error_code=record[24],  # error_code
                            user_id=record[25],  # user_id
                            tenant_id=record[26],  # tenant_id
                            environment=record[27],  # environment
                            hostname=record[28],  # hostname
                            ip_address=record[29],  # ip_address
                            python_version=record[30],  # python_version
                            package_version=record[31],  # package_version
                            tags=json.loads(record[32]) if record[32] else [],
                            metadata=(
                                json.loads(record[33]) if record[33] else {}
                            ),
                        )

                        meta_list.append(trace_meta)

                        # Add to stdout/stderr based on mode
                        fmt = (
                            dynamic("log_format_file", extras=extras)
                            or "{datetime} ({process:5d}, {thread:5d}) ({cut_id}) {message:120s} ({filename}:{lineno})"
                        )
                        formatted_line = fmt.format(**trace_meta.model_dump())

                        if trace_meta.mode == "stdout":
                            stdout_lines.append(formatted_line)
                        else:
                            stderr_lines.append(formatted_line)

                    yield TraceData(
                        stdout="\n".join(stdout_lines),
                        stderr="\n".join(stderr_lines),
                        meta=meta_list,
                    )

        except Exception as e:
            logger.error(f"Failed to read from SQLite database: {e}")

    @classmethod
    def find_trace_with_id(
        cls,
        run_id: str,
        force_raise: bool = True,
        *,
        db_path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> TraceData:
        """Find trace log with specific run ID from SQLite database."""
        if db_path is None:
            url = dynamic("trace_url", extras=extras)
            if (
                url is not None
                and hasattr(url, "path")
                and getattr(url, "path", None)
            ):
                db_path = Path(url.path)
            else:
                db_path = Path("./logs/workflow_traces.db")

        if not db_path.exists():
            if force_raise:
                raise FileNotFoundError(f"SQLite database not found: {db_path}")
            return TraceData(stdout="", stderr="")

        import sqlite3

        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                # Get all records for this run ID
                cursor.execute(
                    """
                    SELECT * FROM traces
                    WHERE run_id = ?
                    ORDER BY created_at
                """,
                    (run_id,),
                )

                records = cursor.fetchall()

                if not records:
                    if force_raise:
                        raise FileNotFoundError(
                            f"Trace log with run_id '{run_id}' not found in database"
                        )
                    return TraceData(stdout="", stderr="")

                # Convert to TraceData format
                stdout_lines = []
                stderr_lines = []
                meta_list = []

                for record in records:
                    # Convert record to TraceMeta
                    trace_meta = TraceMeta(
                        mode=record[5],  # mode
                        level=record[3],  # level
                        datetime=record[6],  # datetime
                        process=record[7],  # process
                        thread=record[8],  # thread
                        message=record[4],  # message
                        cut_id=record[11],  # cut_id
                        filename=record[9],  # filename
                        lineno=record[10],  # lineno
                        workflow_name=record[12],  # workflow_name
                        stage_name=record[13],  # stage_name
                        job_name=record[14],  # job_name
                        duration_ms=record[15],  # duration_ms
                        memory_usage_mb=record[16],  # memory_usage_mb
                        cpu_usage_percent=record[17],  # cpu_usage_percent
                        trace_id=record[18],  # trace_id
                        span_id=record[19],  # span_id
                        parent_span_id=record[20],  # parent_span_id
                        exception_type=record[21],  # exception_type
                        exception_message=record[22],  # exception_message
                        stack_trace=record[23],  # stack_trace
                        error_code=record[24],  # error_code
                        user_id=record[25],  # user_id
                        tenant_id=record[26],  # tenant_id
                        environment=record[27],  # environment
                        hostname=record[28],  # hostname
                        ip_address=record[29],  # ip_address
                        python_version=record[30],  # python_version
                        package_version=record[31],  # package_version
                        tags=json.loads(record[32]) if record[32] else [],
                        metadata=json.loads(record[33]) if record[33] else {},
                    )

                    meta_list.append(trace_meta)

                    # Add to stdout/stderr based on mode
                    fmt = (
                        dynamic("log_format_file", extras=extras)
                        or "{datetime} ({process:5d}, {thread:5d}) ({cut_id}) {message:120s} ({filename}:{lineno})"
                    )
                    formatted_line = fmt.format(**trace_meta.model_dump())

                    if trace_meta.mode == "stdout":
                        stdout_lines.append(formatted_line)
                    else:
                        stderr_lines.append(formatted_line)

                return TraceData(
                    stdout="\n".join(stdout_lines),
                    stderr="\n".join(stderr_lines),
                    meta=meta_list,
                )

        except Exception as e:
            logger.error(f"Failed to read from SQLite database: {e}")
            if force_raise:
                raise
            return TraceData(stdout="", stderr="")


class SQLiteTrace(BaseTrace):  # pragma: no cov
    """SQLite Trace that uses SQLiteHandler for database-backed logging.

    This class provides SQLite-based trace logging implementation using
    the optimized SQLiteHandler for scalable deployments with database-backed storage.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._handler = None
        self._logger = None
        self._setup_handler()

    def _setup_handler(self):
        """Setup the SQLiteHandler for this trace instance."""
        # Create a dedicated logger for this trace session
        self._logger = logging.getLogger(
            f"ddeutil.workflow.sqlite.{self.run_id}"
        )
        self._logger.setLevel(logging.DEBUG)

        # Remove existing handlers to avoid duplicates
        for handler in self._logger.handlers[:]:
            self._logger.removeHandler(handler)

        # Create and add the SQLite handler
        self._handler = SQLiteHandler(
            run_id=self.run_id,
            parent_run_id=self.parent_run_id,
            extras=self.extras,
        )
        self._logger.addHandler(self._handler)

        # Prevent propagation to avoid duplicate logs
        self._logger.propagate = False

    @classmethod
    def find_traces(
        cls,
        path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> Iterator[TraceData]:
        """Find trace logs using SQLiteHandler."""
        return SQLiteHandler.find_traces(db_path=path, extras=extras)

    @classmethod
    def find_trace_with_id(
        cls,
        run_id: str,
        force_raise: bool = True,
        *,
        path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> TraceData:
        """Find trace log with specific run ID using SQLiteHandler."""
        return SQLiteHandler.find_trace_with_id(
            run_id=run_id,
            force_raise=force_raise,
            db_path=path,
            extras=extras,
        )

    def writer(
        self,
        message: str,
        level: str,
        is_err: bool = False,
    ) -> None:
        """Write using the optimized SQLite handler."""
        if not dynamic("enable_write_log", extras=self.extras):
            return

        # Create a log record
        record = logging.LogRecord(
            name=self._logger.name,
            level=getattr(logging, level.upper(), logging.INFO),
            pathname="",
            lineno=0,
            msg=message,
            args=(),
            exc_info=None,
        )

        # Add custom attributes for context
        record.workflow_name = self.extras.get("workflow_name")
        record.stage_name = self.extras.get("stage_name")
        record.job_name = self.extras.get("job_name")
        record.trace_id = self.extras.get("trace_id")
        record.span_id = self.extras.get("span_id")
        record.user_id = self.extras.get("user_id")
        record.tenant_id = self.extras.get("tenant_id")

        # Emit the record
        self._logger.handle(record)

    async def awriter(
        self,
        message: str,
        level: str,
        is_err: bool = False,
    ) -> None:
        """Async write using the optimized SQLite handler."""
        # For async operations, we'll use the same synchronous approach
        # since the handler itself handles the I/O efficiently
        self.writer(message, level, is_err)

    def make_message(self, message: str) -> str:
        """Prepare message using the same logic as ConsoleTrace."""
        return prepare_newline(Message.from_str(message).prepare(self.extras))

    def close(self):
        """Close the handler and cleanup."""
        if self._handler:
            self._handler.close()
        if self._logger:
            # Remove the handler from the logger
            for handler in self._logger.handlers[:]:
                self._logger.removeHandler(handler)


class RestAPITrace(BaseTrace):  # pragma: no cov
    """REST API Trace that uses RestAPIHandler for external monitoring services.

    This class provides REST API-based trace logging implementation using
    the optimized RestAPIHandler for integration with external monitoring
    services like Datadog, Grafana, AWS CloudWatch, and other platforms.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._handler = None
        self._logger = None
        self._setup_handler()

    def _setup_handler(self):
        """Setup the RestAPIHandler for this trace instance."""
        # Create a dedicated logger for this trace session
        self._logger = logging.getLogger(
            f"ddeutil.workflow.restapi.{self.run_id}"
        )
        self._logger.setLevel(logging.DEBUG)

        # Remove existing handlers to avoid duplicates
        for handler in self._logger.handlers[:]:
            self._logger.removeHandler(handler)

        # Extract API configuration from URL or extras
        api_url = self.extras.get("api_url", "")
        api_key = self.extras.get("api_key")
        service_type = self.extras.get("service_type", "generic")

        # Create and add the REST API handler
        self._handler = RestAPIHandler(
            run_id=self.run_id,
            parent_run_id=self.parent_run_id,
            api_url=api_url,
            api_key=api_key,
            service_type=service_type,
            extras=self.extras,
        )
        self._logger.addHandler(self._handler)

        # Prevent propagation to avoid duplicate logs
        self._logger.propagate = False

    def writer(
        self,
        message: str,
        level: str,
        is_err: bool = False,
    ) -> None:
        """Write using the optimized REST API handler."""
        if not dynamic("enable_write_log", extras=self.extras):
            return

        # Create a log record
        record = logging.LogRecord(
            name=self._logger.name,
            level=getattr(logging, level.upper(), logging.INFO),
            pathname="",
            lineno=0,
            msg=message,
            args=(),
            exc_info=None,
        )

        # Add custom attributes for context
        record.workflow_name = self.extras.get("workflow_name")
        record.stage_name = self.extras.get("stage_name")
        record.job_name = self.extras.get("job_name")
        record.trace_id = self.extras.get("trace_id")
        record.span_id = self.extras.get("span_id")
        record.user_id = self.extras.get("user_id")
        record.tenant_id = self.extras.get("tenant_id")

        # Emit the record
        self._logger.handle(record)

    async def awriter(
        self,
        message: str,
        level: str,
        is_err: bool = False,
    ) -> None:
        """Async write using the optimized REST API handler."""
        # For async operations, we'll use the same synchronous approach
        # since the handler itself handles the I/O efficiently
        self.writer(message, level, is_err)

    def make_message(self, message: str) -> str:
        """Prepare message using the same logic as ConsoleTrace."""
        return prepare_newline(Message.from_str(message).prepare(self.extras))

    def close(self):
        """Close the handler and cleanup."""
        if self._handler:
            self._handler.close()
        if self._logger:
            # Remove the handler from the logger
            for handler in self._logger.handlers[:]:
                self._logger.removeHandler(handler)


class ElasticsearchTrace(BaseTrace):  # pragma: no cov
    """Elasticsearch Trace that uses ElasticsearchHandler for database-backed logging.

    This class provides Elasticsearch-based trace logging implementation using
    the optimized ElasticsearchHandler for scalable deployments with searchable
    log storage and aggregation capabilities.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._handler = None
        self._logger = None
        self._setup_handler()

    def _setup_handler(self):
        """Setup the ElasticsearchHandler for this trace instance."""
        # Create a dedicated logger for this trace session
        self._logger = logging.getLogger(
            f"ddeutil.workflow.elasticsearch.{self.run_id}"
        )
        self._logger.setLevel(logging.DEBUG)

        # Remove existing handlers to avoid duplicates
        for handler in self._logger.handlers[:]:
            self._logger.removeHandler(handler)

        # Extract Elasticsearch configuration from URL or extras
        es_hosts = self.extras.get("es_hosts", "http://localhost:9200")
        index_name = self.extras.get("index_name", "workflow-traces")
        username = self.extras.get("username")
        password = self.extras.get("password")

        # Create and add the Elasticsearch handler
        self._handler = ElasticsearchHandler(
            run_id=self.run_id,
            parent_run_id=self.parent_run_id,
            es_hosts=es_hosts,
            index_name=index_name,
            username=username,
            password=password,
            extras=self.extras,
        )
        self._logger.addHandler(self._handler)

        # Prevent propagation to avoid duplicate logs
        self._logger.propagate = False

    @classmethod
    def find_traces(
        cls,
        path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> Iterator[TraceData]:
        """Find trace logs using ElasticsearchHandler."""
        es_hosts = (extras or {}).get("es_hosts", "http://localhost:9200")
        index_name = (extras or {}).get("index_name", "workflow-traces")
        username = (extras or {}).get("username")
        password = (extras or {}).get("password")

        return ElasticsearchHandler.find_traces(
            es_hosts=es_hosts,
            index_name=index_name,
            username=username,
            password=password,
            extras=extras,
        )

    @classmethod
    def find_trace_with_id(
        cls,
        run_id: str,
        force_raise: bool = True,
        *,
        path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> TraceData:
        """Find trace log with specific run ID using ElasticsearchHandler."""
        es_hosts = (extras or {}).get("es_hosts", "http://localhost:9200")
        index_name = (extras or {}).get("index_name", "workflow-traces")
        username = (extras or {}).get("username")
        password = (extras or {}).get("password")

        return ElasticsearchHandler.find_trace_with_id(
            run_id=run_id,
            force_raise=force_raise,
            es_hosts=es_hosts,
            index_name=index_name,
            username=username,
            password=password,
            extras=extras,
        )

    def writer(
        self,
        message: str,
        level: str,
        is_err: bool = False,
    ) -> None:
        """Write using the optimized Elasticsearch handler."""
        if not dynamic("enable_write_log", extras=self.extras):
            return

        # Create a log record
        record = logging.LogRecord(
            name=self._logger.name,
            level=getattr(logging, level.upper(), logging.INFO),
            pathname="",
            lineno=0,
            msg=message,
            args=(),
            exc_info=None,
        )

        # Add custom attributes for context
        record.workflow_name = self.extras.get("workflow_name")
        record.stage_name = self.extras.get("stage_name")
        record.job_name = self.extras.get("job_name")
        record.trace_id = self.extras.get("trace_id")
        record.span_id = self.extras.get("span_id")
        record.user_id = self.extras.get("user_id")
        record.tenant_id = self.extras.get("tenant_id")

        # Emit the record
        self._logger.handle(record)

    async def awriter(
        self,
        message: str,
        level: str,
        is_err: bool = False,
    ) -> None:
        """Async write using the optimized Elasticsearch handler."""
        # For async operations, we'll use the same synchronous approach
        # since the handler itself handles the I/O efficiently
        self.writer(message, level, is_err)

    def make_message(self, message: str) -> str:
        """Prepare message using the same logic as ConsoleTrace."""
        return prepare_newline(Message.from_str(message).prepare(self.extras))

    def close(self):
        """Close the handler and cleanup."""
        if self._handler:
            self._handler.close()
        if self._logger:
            # Remove the handler from the logger
            for handler in self._logger.handlers[:]:
                self._logger.removeHandler(handler)


class MultiHandler(logging.Handler):
    """Multi-handler logging handler that combines multiple handlers.

    This handler allows using multiple logging handlers simultaneously,
    enabling logging to multiple destinations (file, SQLite, REST API,
    Elasticsearch, etc.) at the same time.
    """

    def __init__(
        self,
        run_id: str,
        parent_run_id: Optional[str] = None,
        handlers: Optional[list[logging.Handler]] = None,
        extras: Optional[DictData] = None,
        fail_silently: bool = True,
    ):
        """Initialize the multi-handler.

        Args:
            run_id: The running ID for this trace session.
            parent_run_id: Optional parent running ID.
            handlers: List of logging handlers to use.
            extras: Extra configuration parameters.
            fail_silently: Whether to continue if individual handlers fail.
        """
        super().__init__()

        self.run_id = run_id
        self.parent_run_id = parent_run_id
        self.extras = extras or {}
        self.fail_silently = fail_silently

        # Initialize handlers
        self.handlers = handlers or []
        self._init_handlers()

    def _init_handlers(self):
        """Initialize all handlers with proper configuration."""
        for handler in self.handlers:
            try:
                # Set common attributes if the handler supports them
                if hasattr(handler, "run_id"):
                    handler.run_id = self.run_id
                if hasattr(handler, "parent_run_id"):
                    handler.parent_run_id = self.parent_run_id
                if hasattr(handler, "extras"):
                    handler.extras = self.extras
            except Exception as e:
                if not self.fail_silently:
                    raise
                logger.error(
                    f"Failed to initialize handler {type(handler).__name__}: {e}"
                )

    def add_handler(self, handler: logging.Handler):
        """Add a new handler to the multi-handler.

        Args:
            handler: The handler to add.
        """
        try:
            # Set common attributes
            if hasattr(handler, "run_id"):
                handler.run_id = self.run_id
            if hasattr(handler, "parent_run_id"):
                handler.parent_run_id = self.parent_run_id
            if hasattr(handler, "extras"):
                handler.extras = self.extras

            self.handlers.append(handler)
        except Exception as e:
            if not self.fail_silently:
                raise
            logger.error(f"Failed to add handler {type(handler).__name__}: {e}")

    def remove_handler(self, handler: logging.Handler):
        """Remove a handler from the multi-handler.

        Args:
            handler: The handler to remove.
        """
        if handler in self.handlers:
            self.handlers.remove(handler)
            try:
                handler.close()
            except Exception as e:
                if not self.fail_silently:
                    raise
                logger.error(
                    f"Failed to close handler {type(handler).__name__}: {e}"
                )

    def emit(self, record: logging.LogRecord):
        """Emit a log record to all handlers."""
        for handler in self.handlers:
            try:
                handler.emit(record)
            except Exception as e:
                if not self.fail_silently:
                    raise
                logger.error(
                    f"Failed to emit to handler {type(handler).__name__}: {e}"
                )

    def flush(self):
        """Flush all handlers."""
        for handler in self.handlers:
            try:
                handler.flush()
            except Exception as e:
                if not self.fail_silently:
                    raise
                logger.error(
                    f"Failed to flush handler {type(handler).__name__}: {e}"
                )

    def close(self):
        """Close all handlers."""
        for handler in self.handlers:
            try:
                handler.close()
            except Exception as e:
                if not self.fail_silently:
                    raise
                logger.error(
                    f"Failed to close handler {type(handler).__name__}: {e}"
                )
        super().close()

    def get_handler_by_type(
        self, handler_type: type
    ) -> Optional[logging.Handler]:
        """Get a handler by its type.

        Args:
            handler_type: The type of handler to find.

        Returns:
            The handler of the specified type, or None if not found.
        """
        for handler in self.handlers:
            if isinstance(handler, handler_type):
                return handler
        return None

    def get_handlers_by_type(self, handler_type: type) -> list[logging.Handler]:
        """Get all handlers of a specific type.

        Args:
            handler_type: The type of handlers to find.

        Returns:
            List of handlers of the specified type.
        """
        return [
            handler
            for handler in self.handlers
            if isinstance(handler, handler_type)
        ]

    @property
    def handler_count(self) -> int:
        """Get the number of handlers."""
        return len(self.handlers)

    @property
    def handler_types(self) -> list[str]:
        """Get the types of all handlers."""
        return [type(handler).__name__ for handler in self.handlers]


class MultiTrace(BaseTrace):  # pragma: no cov
    """Multi-handler Trace that uses multiple handlers simultaneously.

    This class provides multi-destination trace logging implementation using
    multiple handlers to log to different destinations at the same time.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._handler = None
        self._logger = None
        self._setup_handler()

    def _setup_handler(self):
        """Setup the MultiHandler for this trace instance."""
        # Create a dedicated logger for this trace session
        self._logger = logging.getLogger(
            f"ddeutil.workflow.multi.{self.run_id}"
        )
        self._logger.setLevel(logging.DEBUG)

        # Remove existing handlers to avoid duplicates
        for handler in self._logger.handlers[:]:
            self._logger.removeHandler(handler)

        # Get handlers configuration from extras
        handlers_config = self.extras.get("handlers", [])
        handlers = []

        # Create handlers based on configuration
        for handler_config in handlers_config:
            try:
                handler = self._create_handler(handler_config)
                if handler:
                    handlers.append(handler)
            except Exception as e:
                logger.error(
                    f"Failed to create handler {handler_config.get('type', 'unknown')}: {e}"
                )

        # Create and add the multi handler
        self._handler = MultiHandler(
            run_id=self.run_id,
            parent_run_id=self.parent_run_id,
            handlers=handlers,
            extras=self.extras,
            fail_silently=self.extras.get("fail_silently", True),
        )
        self._logger.addHandler(self._handler)

        # Prevent propagation to avoid duplicate logs
        self._logger.propagate = False

    def _create_handler(self, config: DictData) -> Optional[logging.Handler]:
        """Create a handler based on configuration.

        Args:
            config: Handler configuration dictionary.

        Returns:
            The created handler, or None if creation failed.
        """
        handler_type = config.get("type")

        if handler_type == "file":
            return WorkflowFileHandler(
                run_id=self.run_id,
                parent_run_id=self.parent_run_id,
                base_path=Path(config.get("path", "./logs")),
                extras=self.extras,
                buffer_size=config.get("buffer_size", 8192),
                flush_interval=config.get("flush_interval", 1.0),
            )

        elif handler_type == "sqlite":
            return SQLiteHandler(
                run_id=self.run_id,
                parent_run_id=self.parent_run_id,
                db_path=Path(config.get("path", "./logs/workflow_traces.db")),
                extras=self.extras,
                buffer_size=config.get("buffer_size", 100),
                flush_interval=config.get("flush_interval", 2.0),
            )

        elif handler_type == "restapi":
            return RestAPIHandler(
                run_id=self.run_id,
                parent_run_id=self.parent_run_id,
                api_url=config.get("api_url", ""),
                api_key=config.get("api_key"),
                service_type=config.get("service_type", "generic"),
                extras=self.extras,
                buffer_size=config.get("buffer_size", 50),
                flush_interval=config.get("flush_interval", 2.0),
                timeout=config.get("timeout", 10.0),
                max_retries=config.get("max_retries", 3),
            )

        elif handler_type == "elasticsearch":
            return ElasticsearchHandler(
                run_id=self.run_id,
                parent_run_id=self.parent_run_id,
                es_hosts=config.get("es_hosts", "http://localhost:9200"),
                index_name=config.get("index_name", "workflow-traces"),
                username=config.get("username"),
                password=config.get("password"),
                extras=self.extras,
                buffer_size=config.get("buffer_size", 100),
                flush_interval=config.get("flush_interval", 2.0),
                timeout=config.get("timeout", 30.0),
                max_retries=config.get("max_retries", 3),
            )

        else:
            logger.warning(f"Unknown handler type: {handler_type}")
            return None

    def add_handler(self, handler: logging.Handler):
        """Add a new handler to the multi-trace.

        Args:
            handler: The handler to add.
        """
        if self._handler:
            self._handler.add_handler(handler)

    def remove_handler(self, handler: logging.Handler):
        """Remove a handler from the multi-trace.

        Args:
            handler: The handler to remove.
        """
        if self._handler:
            self._handler.remove_handler(handler)

    def get_handler_by_type(
        self, handler_type: type
    ) -> Optional[logging.Handler]:
        """Get a handler by its type.

        Args:
            handler_type: The type of handler to find.

        Returns:
            The handler of the specified type, or None if not found.
        """
        if self._handler:
            return self._handler.get_handler_by_type(handler_type)
        return None

    def get_handlers_by_type(self, handler_type: type) -> list[logging.Handler]:
        """Get all handlers of a specific type.

        Args:
            handler_type: The type of handlers to find.

        Returns:
            List of handlers of the specified type.
        """
        if self._handler:
            return self._handler.get_handlers_by_type(handler_type)
        return []

    @property
    def handler_count(self) -> int:
        """Get the number of handlers."""
        if self._handler:
            return self._handler.handler_count
        return 0

    @property
    def handler_types(self) -> list[str]:
        """Get the types of all handlers."""
        if self._handler:
            return self._handler.handler_types
        return []

    def writer(
        self,
        message: str,
        level: str,
        is_err: bool = False,
    ) -> None:
        """Write using the multi-handler."""
        if not dynamic("enable_write_log", extras=self.extras):
            return

        # Create a log record
        record = logging.LogRecord(
            name=self._logger.name,
            level=getattr(logging, level.upper(), logging.INFO),
            pathname="",
            lineno=0,
            msg=message,
            args=(),
            exc_info=None,
        )

        # Add custom attributes for context
        record.workflow_name = self.extras.get("workflow_name")
        record.stage_name = self.extras.get("stage_name")
        record.job_name = self.extras.get("job_name")
        record.trace_id = self.extras.get("trace_id")
        record.span_id = self.extras.get("span_id")
        record.user_id = self.extras.get("user_id")
        record.tenant_id = self.extras.get("tenant_id")

        # Emit the record
        self._logger.handle(record)

    async def awriter(
        self,
        message: str,
        level: str,
        is_err: bool = False,
    ) -> None:
        """Async write using the multi-handler."""
        # For async operations, we'll use the same synchronous approach
        # since the handlers themselves handle the I/O efficiently
        self.writer(message, level, is_err)

    def make_message(self, message: str) -> str:
        """Prepare message using the same logic as ConsoleTrace."""
        return prepare_newline(Message.from_str(message).prepare(self.extras))

    def close(self):
        """Close the handler and cleanup."""
        if self._handler:
            self._handler.close()
        if self._logger:
            # Remove the handler from the logger
            for handler in self._logger.handlers[:]:
                self._logger.removeHandler(handler)


Trace = Union[
    FileTrace,
    OptimizedFileTrace,
    SQLiteTrace,
    RestAPITrace,
    ElasticsearchTrace,
    MultiTrace,
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
    url: Optional[ParseResult] = dynamic("trace_url", extras=extras)

    # Check for specific trace types in extras
    if extras and "trace_type" in extras:
        trace_type = extras["trace_type"]
        if trace_type == "multi":
            return map_trace_models.get("multi", MultiTrace)(
                url=url or urlparse("multi://"),
                run_id=run_id,
                parent_run_id=parent_run_id,
                extras=(extras or {}),
            )
        elif trace_type == "restapi":
            return map_trace_models.get("restapi", RestAPITrace)(
                url=url or urlparse("restapi://"),
                run_id=run_id,
                parent_run_id=parent_run_id,
                extras=(extras or {}),
            )
        elif trace_type == "elasticsearch":
            return map_trace_models.get("elasticsearch", ElasticsearchTrace)(
                url=url or urlparse("elasticsearch://"),
                run_id=run_id,
                parent_run_id=parent_run_id,
                extras=(extras or {}),
            )

    if url is not None and url.scheme:
        if url.scheme == "sqlite":
            return map_trace_models.get("sqlite", SQLiteTrace)(
                url=url,
                run_id=run_id,
                parent_run_id=parent_run_id,
                extras=(extras or {}),
            )
        elif url.scheme == "elasticsearch":
            return map_trace_models.get("elasticsearch", ElasticsearchTrace)(
                url=url,
                run_id=run_id,
                parent_run_id=parent_run_id,
                extras=(extras or {}),
            )
        elif url.scheme == "restapi":
            return map_trace_models.get("restapi", RestAPITrace)(
                url=url,
                run_id=run_id,
                parent_run_id=parent_run_id,
                extras=(extras or {}),
            )
        elif url.scheme == "file" and Path(url.path).is_file():
            return map_trace_models.get("sqlite", SQLiteTrace)(
                url=url,
                run_id=run_id,
                parent_run_id=parent_run_id,
                extras=(extras or {}),
            )
        elif url.scheme not in ["file", "sqlite", "elasticsearch", "restapi"]:
            raise NotImplementedError(
                f"Does not implement the outside trace model support for URL: {url}"
            )

    return map_trace_models.get("file", OptimizedFileTrace)(
        url=url or urlparse("file://./logs"),
        run_id=run_id,
        parent_run_id=parent_run_id,
        extras=(extras or {}),
    )
