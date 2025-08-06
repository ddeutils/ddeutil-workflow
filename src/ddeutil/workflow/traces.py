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

Functions:
    set_logging: Configure logger with custom formatting.
    get_trace: Factory function for trace instances.
"""
import contextlib
import json
import logging
import os
import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime
from functools import lru_cache
from inspect import Traceback, currentframe, getframeinfo
from pathlib import Path
from threading import Lock, get_ident
from types import FrameType
from typing import (
    Annotated,
    Any,
    ClassVar,
    Final,
    Literal,
    Optional,
    TypeVar,
    Union,
    cast,
)
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, PrivateAttr
from pydantic.functional_validators import field_validator
from typing_extensions import Self

from .__types import DictData
from .conf import config, dynamic
from .utils import cut_id, get_dt_now, prepare_newline

logger = logging.getLogger("ddeutil.workflow")
Level = Literal["debug", "info", "warning", "error", "exception"]
EMJ_ALERT: str = "🚨"
EMJ_SKIP: str = "⏭️"


@lru_cache
def set_logging(
    name: str,
    *,
    message_fmt: Optional[str] = None,
    datetime_fmt: Optional[str] = None,
) -> logging.Logger:
    """Configure logger with custom formatting and handlers.

    Creates and configures a logger instance with the custom formatter and
    handlers defined in the package configuration. The logger includes both
    console output and proper formatting for workflow execution tracking.

    Args:
        name (str): A module name to create logger for.
        message_fmt: (str, default None)
        datetime_fmt: (str, default None)

    Returns:
        logging.Logger: Configured logger instance with custom formatting.

    Example:
        >>> log = set_logging("ddeutil.workflow.stages")
        >>> log.info("Stage execution started")
    """
    _logger = logging.getLogger(name)

    # NOTE: Developers using this package can then disable all logging just for
    #   this package by;
    #
    #   `logging.getLogger('ddeutil.workflow').propagate = False`
    #
    _logger.addHandler(logging.NullHandler())
    formatter = logging.Formatter(
        fmt=message_fmt,
        datefmt=datetime_fmt,
    )
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    _logger.addHandler(stream_handler)
    _logger.setLevel(logging.DEBUG if config.debug else logging.INFO)
    return _logger


PrefixType = Literal[
    "caller",
    "nested",
    "stage",
    "job",
    "workflow",
    "release",
    "schedule",
    "audit",
]
PREFIX_LOGS: Final[dict[str, dict]] = {
    "caller": {
        "emoji": "⚙️",
        "desc": "logs from any usage from custom caller function.",
    },
    "nested": {"emoji": "⛓️", "desc": "logs from stages module."},
    "stage": {"emoji": "🔗", "desc": "logs from stages module."},
    "job": {"emoji": "🏗", "desc": "logs from job module."},
    "workflow": {"emoji": "👟", "desc": "logs from workflow module."},
    "release": {"emoji": "📅", "desc": "logs from release workflow method."},
    "schedule": {"emoji": "⏰", "desc": "logs from poke workflow method."},
    "audit": {"emoji": "📌", "desc": "logs from audit model."},
}  # pragma: no cov
PREFIX_LOGS_UPPER: Final[Iterator[str]] = (p.upper() for p in PREFIX_LOGS)
PREFIX_DEFAULT: Final[Literal["caller"]] = "caller"
PREFIX_EMOJI_DEFAULT: Final[str] = "⚙️"
PREFIX_LOGS_REGEX: Final[re.Pattern[str]] = re.compile(
    rf"(^\[(?P<module>{'|'.join(PREFIX_LOGS_UPPER)})]:\s?)?(?P<message>.*)",
    re.MULTILINE | re.DOTALL | re.ASCII | re.VERBOSE,
)  # pragma: no cov


class Message(BaseModel):
    """Prefix Message model for receive grouping dict from searching prefix data.

    This model handles prefix parsing and message formatting for logging
    with emoji support and categorization.
    """

    module: Optional[PrefixType] = Field(
        default=None,
        description="A prefix module of message it allow to be None.",
    )
    message: Optional[str] = Field(default=None, description="A message.")

    @field_validator("module", mode="before", json_schema_input_type=str)
    def __prepare_module(cls, data: Optional[str]) -> Optional[str]:
        return data.lower() if data is not None else data

    @classmethod
    def from_str(cls, msg: str, module: Optional[PrefixType] = None) -> Self:
        """Extract message prefix from an input message.

        Args:
            msg (str): A message that want to extract.
            module (PrefixType, default None): A prefix module type.

        Returns:
            Message: The validated model from a string message.
        """
        msg = cls.model_validate(PREFIX_LOGS_REGEX.search(msg).groupdict())
        if msg.module is None and module:
            msg.module = module
        return msg

    def prepare(self, extras: Optional[DictData] = None) -> str:
        """Prepare message with force add prefix before writing trace log.

        Args:
            extras (DictData, default None): An extra parameter that want to
                get the `log_add_emoji` flag.

        Returns:
            str: The prepared message with prefix and optional emoji.
        """
        module = cast(PrefixType, self.module or PREFIX_DEFAULT)
        module_data: dict[str, str] = PREFIX_LOGS.get(
            module, {"emoji": PREFIX_EMOJI_DEFAULT}
        )
        emoji: str = (
            f"{module_data['emoji']} "
            if (extras or {}).get("log_add_emoji", True)
            else ""
        )
        return f"{emoji}[{module.upper()}]: {self.message}"


class Metric(BaseModel):  # pragma: no cov
    """Trace Metric model that will validate data from current logging."""

    execution_time: float


class Metadata(BaseModel):  # pragma: no cov
    """Trace Metadata model for making the current metadata of this CPU, Memory.

    This model captures comprehensive execution context including process IDs,
    thread identifiers, timestamps, and contextual information for debugging
    and monitoring workflow executions.
    """

    error_flag: bool = Field(default=False, description="A meta error flag.")
    level: Level = Field(description="A log level.")
    datetime: str = Field(
        description="A datetime string with the specific config format."
    )
    process: int = Field(description="A process ID.")
    thread: int = Field(description="A thread ID.")
    module: Optional[PrefixType] = Field(
        default=None, description="A prefix module type."
    )
    message: str = Field(description="A message log.")
    cut_id: Optional[str] = Field(
        default=None, description="A cutting of running ID."
    )
    run_id: str
    parent_run_id: Optional[str] = None
    filename: str = Field(description="A filename of this log.")
    lineno: int = Field(description="A line number of this log.")

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

    # NOTE: System context
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

    # NOTE: Custom metadata
    tags: Optional[list[str]] = Field(
        default_factory=list, description="Custom tags for categorization."
    )
    metric: Optional[DictData] = Field(
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
        error_flag: bool,
        message: str,
        level: Level,
        cutting_id: str,
        run_id: str,
        parent_run_id: Optional[str],
        *,
        metric: Optional[DictData] = None,
        module: Optional[PrefixType] = None,
        extras: Optional[DictData] = None,
    ) -> Self:
        """Make the current metric for contract this Metadata model instance.

        This method captures local states like PID, thread identity, and system
        information to create a comprehensive trace metadata instance.

        Args:
            error_flag: A metadata mode.
            message: A message.
            level: A log level.
            cutting_id: A cutting ID string.
            run_id:
            parent_run_id:
            metric:
            module:
            extras: An extra parameter that want to override core
                config values.

        Returns:
            Self: The constructed Metadata instance.
        """
        import socket
        import sys

        from .__about__ import __version__

        frame: Optional[FrameType] = currentframe()
        if frame is None:
            raise ValueError("Cannot get current frame")

        frame_info: Traceback = cls.dynamic_frame(frame, extras=extras)
        extras_data: DictData = extras or {}

        # NOTE: Get system information
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        python_version: str = (
            f"{sys.version_info.major}"
            f".{sys.version_info.minor}"
            f".{sys.version_info.micro}"
        )

        # Get datetime format with fallback
        datetime_format = (
            dynamic("log_datetime_format", extras=extras_data)
            or "%Y-%m-%d %H:%M:%S"
        )
        timezone = dynamic("log_tz", extras=extras_data)
        if timezone is None:
            timezone = ZoneInfo("UTC")

        return cls(
            error_flag=error_flag,
            level=level,
            datetime=(
                get_dt_now().astimezone(timezone).strftime(datetime_format)
            ),
            process=os.getpid(),
            thread=get_ident(),
            module=module,
            message=message,
            cut_id=cutting_id,
            run_id=run_id,
            parent_run_id=parent_run_id,
            filename=frame_info.filename.split(os.path.sep)[-1],
            lineno=frame_info.lineno,
            # NOTE: Performance metrics
            duration_ms=extras_data.get("duration_ms"),
            memory_usage_mb=extras_data.get("memory_usage_mb"),
            cpu_usage_percent=extras_data.get("cpu_usage_percent"),
            # NOTE: System context
            hostname=hostname,
            ip_address=ip_address,
            python_version=python_version,
            package_version=__version__,
            # NOTE: Custom metadata
            tags=extras_data.get("tags", []),
            metric=metric,
        )

    @property
    def pointer_id(self) -> str:
        """Pointer ID of trace metadata.

        Returns:
            str: A pointer ID that will choose from parent running ID or running
                ID.
        """
        return self.parent_run_id or self.run_id


class TraceData(BaseModel):  # pragma: no cov
    """Trace Data model for keeping data for any Trace models.

    This model serves as a container for trace information including stdout,
    stderr, and metadata for comprehensive logging and monitoring.
    """

    stdout: str = Field(description="A standard output trace data.")
    stderr: str = Field(description="A standard error trace data.")
    meta: list[Metadata] = Field(
        default_factory=list,
        description=(
            "A metadata mapping of this output and error before making it to "
            "standard value."
        ),
    )


class BaseHandler(BaseModel, ABC):
    """Base Handler model"""

    @abstractmethod
    def emit(
        self,
        metadata: Metadata,
        *,
        extra: Optional[DictData] = None,
    ): ...

    @abstractmethod
    async def amit(
        self,
        metadata: Metadata,
        *,
        extra: Optional[DictData] = None,
    ) -> None: ...

    @abstractmethod
    def flush(
        self, metadata: list[Metadata], *, extra: Optional[DictData] = None
    ) -> None: ...

    def pre(self) -> None:
        """Pre-process of handler that will execute when start create trance."""


class ConsoleHandler(BaseHandler):
    """Console Handler model."""

    type: Literal["console"] = "console"
    name: str = "ddeutil.workflow"
    format: str = Field(
        default=(
            "%(asctime)s.%(msecs)03d (%(process)-5d, "
            "%(thread)-5d) [%(levelname)-7s] (%(cut_id)s) %(message)-120s "
            "(%(filename)s:%(lineno)s) (%(name)-10s)"
        ),
        description="A log format that will use with logging package.",
    )
    datetime_format: str = Field(
        default="%Y-%m-%d %H:%M:%S",
        description="A log datetime format.",
    )

    def pre(self) -> None:
        """Pre-process."""
        set_logging(
            self.name,
            message_fmt=self.format,
            datetime_fmt=self.datetime_format,
        )

    def emit(
        self, metadata: Metadata, *, extra: Optional[DictData] = None
    ) -> None:
        getattr(logger, metadata.level)(
            metadata.message,
            stacklevel=3,
            extra=(extra or {}) | {"cut_id": metadata.cut_id},
        )

    async def amit(
        self, metadata: Metadata, *, extra: Optional[DictData] = None
    ) -> None:
        self.emit(metadata, extra=extra)

    def flush(
        self, metadata: list[Metadata], *, extra: Optional[DictData] = None
    ) -> None:
        for meta in metadata:
            self.emit(meta, extra=extra)


class FileHandler(BaseHandler):
    """File Handler model."""

    metadata_filename: ClassVar[str] = "metadata.txt"

    type: Literal["file"] = "file"
    path: str = Field(
        description=(
            "A file path that use to save all trace log files that include "
            "stdout, stderr, and metadata."
        )
    )
    format: str = Field(
        default=(
            "{datetime} ({process:5d}, {thread:5d}) ({cut_id}) {message:120s} "
            "({filename}:{lineno})"
        ),
        description="A trace log format that write on stdout and stderr files.",
    )
    buffer_size: int = Field(default=8192)

    # NOTE: Private attrs for the internal process.
    _lock: Lock = PrivateAttr(default_factory=Lock)

    def pointer(self, run_id: str) -> Path:
        """Pointer of the target path that use to writing trace log or searching
        trace log.

        This running ID folder that use to keeping trace log data will use
        a parent running ID first. If it does not set, it will use running ID
        instead.

        Returns:
            Path: The target path for trace log operations.
        """
        log_file: Path = Path(self.path) / f"run_id={run_id}"
        if not log_file.exists():
            log_file.mkdir(parents=True)
        return log_file

    def pre(self) -> None:  # pragma: no cov
        """Pre-method that will call from getting trace model factory function.
        This method will create filepath of this parent log.
        """
        if not (p := Path(self.path)).exists():
            p.mkdir(parents=True)

    def emit(
        self,
        metadata: Metadata,
        *,
        extra: Optional[DictData] = None,
    ) -> None:
        """Emit trace log to the file with a specific pointer path.

        Args:
            metadata (Metadata):
            extra (DictData, default None):
        """
        pointer: Path = self.pointer(metadata.pointer_id)
        std_file = "stderr" if metadata.error_flag else "stdout"
        with self._lock:
            with (pointer / f"{std_file}.txt").open(
                mode="at", encoding="utf-8"
            ) as f:
                f.write(f"{self.format}\n".format(**metadata.model_dump()))

            with (pointer / self.metadata_filename).open(
                mode="at", encoding="utf-8"
            ) as f:
                f.write(metadata.model_dump_json() + "\n")

    async def amit(
        self,
        metadata: Metadata,
        *,
        extra: Optional[DictData] = None,
    ) -> None:  # pragma: no cove
        """Async emit trace log."""
        try:
            import aiofiles
        except ImportError as e:
            raise ImportError(
                "Async mode need to install `aiofiles` package first"
            ) from e

        with self._lock:
            pointer: Path = self.pointer(metadata.pointer_id)
            std_file = "stderr" if metadata.error_flag else "stdout"
            async with aiofiles.open(
                pointer / f"{std_file}.txt", mode="at", encoding="utf-8"
            ) as f:
                await f.write(
                    f"{self.format}\n".format(**metadata.model_dump())
                )

            async with aiofiles.open(
                pointer / self.metadata_filename, mode="at", encoding="utf-8"
            ) as f:
                await f.write(metadata.model_dump_json() + "\n")

    def flush(
        self, metadata: list[Metadata], *, extra: Optional[DictData] = None
    ) -> None:
        """Flush logs."""
        with self._lock:
            pointer: Path = self.pointer(metadata[0].pointer_id)
            stdout_file = open(
                pointer / "stdout.txt",
                mode="a",
                encoding="utf-8",
                buffering=self.buffer_size,
            )
            stderr_file = open(
                pointer / "stderr.txt",
                mode="a",
                encoding="utf-8",
                buffering=self.buffer_size,
            )
            metadata_file = open(
                pointer / self.metadata_filename,
                mode="a",
                encoding="utf-8",
                buffering=self.buffer_size,
            )

            for meta in metadata:
                if meta.error_flag:
                    stderr_file.write(
                        f"{self.format}\n".format(**meta.model_dump())
                    )
                else:
                    stdout_file.write(
                        f"{self.format}\n".format(**meta.model_dump())
                    )

                metadata_file.write(meta.model_dump_json() + "\n")

            stdout_file.flush()
            stderr_file.flush()
            metadata_file.flush()
            stdout_file.close()
            stderr_file.close()
            metadata_file.close()

    @classmethod
    def from_path(cls, file: Path) -> TraceData:  # pragma: no cov
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

        if (file / cls.metadata_filename).exists():
            data["meta"] = [
                json.loads(line)
                for line in (
                    (file / cls.metadata_filename)
                    .read_text(encoding="utf-8")
                    .splitlines()
                )
            ]

        return TraceData.model_validate(data)

    def find_traces(
        self,
        path: Optional[Path] = None,
    ) -> Iterator[TraceData]:  # pragma: no cov
        """Find trace logs.

        Args:
            path (Path | None, default None): A trace path that want to find.
        """
        for file in sorted(
            (path or Path(self.path)).glob("./run_id=*"),
            key=lambda f: f.lstat().st_mtime,
        ):
            yield self.from_path(file)

    def find_trace_with_id(
        self,
        run_id: str,
        *,
        force_raise: bool = True,
        path: Optional[Path] = None,
    ) -> TraceData:  # pragma: no cov
        """Find trace log with an input specific run ID.

        Args:
            run_id: A running ID of trace log.
            force_raise: Whether to raise an exception if not found.
            path: Optional path override.

        Returns:
            TraceData: A TranceData instance that already passed searching data.
        """
        base_path: Path = path or self.path
        file: Path = base_path / f"run_id={run_id}"
        if file.exists():
            return self.from_path(file)
        elif force_raise:
            raise FileNotFoundError(
                f"Trace log on path {base_path}, does not found trace "
                f"'run_id={run_id}'."
            )
        return TraceData(stdout="", stderr="")


class SQLiteHandler(BaseHandler):  # pragma: no cov
    """High-performance SQLite logging handler for workflow traces.

    This handler provides optimized SQLite-based logging with connection pooling,
    thread safety, and structured metadata storage. It replaces the placeholder
    SQLiteTrace implementation with a fully functional database-backed system.
    """

    type: Literal["sqlite"] = "sqlite"
    path: str
    table_name: str = Field(default="traces")

    # NOTE: Private attrs for the internal process.
    _lock: Lock = PrivateAttr(default_factory=Lock)

    def pre(self) -> None:
        import sqlite3

        try:
            with sqlite3.connect(self.path) as conn:
                cursor = conn.cursor()

                # Create traces table if it doesn't exist
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self.table_name} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id TEXT NOT NULL,
                        parent_run_id TEXT,
                        level TEXT NOT NULL,
                        message TEXT NOT NULL,
                        error_flag BOOLEAN NOT NULL,
                        datetime TEXT NOT NULL,
                        process INTEGER NOT NULL,
                        thread INTEGER NOT NULL,
                        filename TEXT NOT NULL,
                        lineno INTEGER NOT NULL,
                        cut_id TEXT,
                        duration_ms REAL,
                        memory_usage_mb REAL,
                        cpu_usage_percent REAL,
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

    def emit(
        self,
        metadata: Metadata,
        *,
        extra: Optional[DictData] = None,
    ) -> None:
        self.flush([metadata], extra=extra)

    def amit(
        self,
        metadata: Metadata,
        *,
        extra: Optional[DictData] = None,
    ) -> None:
        raise NotImplementedError("Does not implement async emit yet.")

    def flush(
        self, metadata: list[Metadata], *, extra: Optional[DictData] = None
    ) -> None:
        """Flush all buffered records to database."""
        if not self._buffer:
            return

        import sqlite3

        with self._lock:
            try:
                with sqlite3.connect(self.path) as conn:
                    cursor = conn.cursor()
                    records = []
                    for meta in self._buffer:
                        records.append(
                            (
                                meta.run_id,
                                meta.parent_run_id,
                                meta.level,
                                meta.message,
                                meta.error_flag,
                                meta.datetime,
                                meta.process,
                                meta.thread,
                                meta.filename,
                                meta.lineno,
                                meta.cut_id,
                                meta.workflow_name,
                                meta.stage_name,
                                meta.job_name,
                                meta.duration_ms,
                                meta.memory_usage_mb,
                                meta.cpu_usage_percent,
                                meta.trace_id,
                                meta.span_id,
                                meta.parent_span_id,
                                meta.exception_type,
                                meta.exception_message,
                                meta.stack_trace,
                                meta.error_code,
                                meta.user_id,
                                meta.tenant_id,
                                meta.environment,
                                meta.hostname,
                                meta.ip_address,
                                meta.python_version,
                                meta.package_version,
                                (json.dumps(meta.tags) if meta.tags else None),
                                (
                                    json.dumps(meta.metadata)
                                    if meta.metadata
                                    else None
                                ),
                            )
                        )

                    # NOTE: Batch insert
                    cursor.executemany(
                        f"""
                        INSERT INTO {self.table_name} (
                            run_id, parent_run_id, level, message, error_flag, datetime,
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
                self._buffer.clear()

    def find_traces(
        self,
        path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> Iterator[TraceData]:
        """Find trace logs from SQLite database."""
        if path is None:
            url = self.path
            if (
                url is not None
                and hasattr(url, "path")
                and getattr(url, "path", None)
            ):
                path = Path(url.path)
            else:
                path = Path("./logs/workflow_traces.db")

        if not path.exists():
            return

        import sqlite3

        try:
            with sqlite3.connect(path) as conn:
                cursor = conn.cursor()

                # NOTE: Get all unique run IDs
                cursor.execute(
                    """
                    SELECT DISTINCT run_id, parent_run_id, created_at
                    FROM traces
                    ORDER BY created_at DESC
                """
                )

                for run_id, _, _ in cursor.fetchall():
                    # NOTE: Get all records for this run
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
                        trace_meta = Metadata(
                            run_id=record[1],
                            parent_run_id=record[2],
                            error_flag=record[5],
                            level=record[3],
                            message=record[4],
                            datetime=record[6],
                            process=record[7],
                            thread=record[8],
                            cut_id=record[11],
                            filename=record[9],
                            lineno=record[10],
                            duration_ms=record[15],
                            memory_usage_mb=record[16],
                            cpu_usage_percent=record[17],
                            hostname=record[28],
                            ip_address=record[29],
                            python_version=record[30],
                            package_version=record[31],
                            tags=json.loads(record[32]) if record[32] else [],
                            metric=(
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

                        if trace_meta.error_flag:
                            stderr_lines.append(formatted_line)
                        else:
                            stdout_lines.append(formatted_line)

                    yield TraceData(
                        stdout="\n".join(stdout_lines),
                        stderr="\n".join(stderr_lines),
                        meta=meta_list,
                    )

        except Exception as e:
            logger.error(f"Failed to read from SQLite database: {e}")

    def find_trace_with_id(
        self,
        run_id: str,
        force_raise: bool = True,
        *,
        path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> TraceData:
        """Find trace log with specific run ID from SQLite database."""
        path = path or Path(self.path)
        if not path.exists():
            if force_raise:
                raise FileNotFoundError(f"SQLite database not found: {path}")
            return TraceData(stdout="", stderr="")

        import sqlite3

        try:
            with sqlite3.connect(path) as conn:
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
                    trace_meta = Metadata(
                        run_id=record[1],
                        parent_run_id=record[2],
                        error_flag=record[5],
                        level=record[3],
                        datetime=record[6],
                        process=record[7],
                        thread=record[8],
                        message=record[4],
                        cut_id=record[11],
                        filename=record[9],
                        lineno=record[10],
                        duration_ms=record[15],
                        memory_usage_mb=record[16],
                        cpu_usage_percent=record[17],
                        hostname=record[28],
                        ip_address=record[29],
                        python_version=record[30],
                        package_version=record[31],
                        tags=json.loads(record[32]) if record[32] else [],
                        metric=json.loads(record[33]) if record[33] else {},
                    )

                    meta_list.append(trace_meta)

                    # Add to stdout/stderr based on mode
                    fmt = (
                        dynamic("log_format_file", extras=extras)
                        or "{datetime} ({process:5d}, {thread:5d}) ({cut_id}) {message:120s} ({filename}:{lineno})"
                    )
                    formatted_line = fmt.format(**trace_meta.model_dump())

                    if trace_meta.error_flag:
                        stderr_lines.append(formatted_line)
                    else:
                        stdout_lines.append(formatted_line)

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


class RestAPIHandler(BaseHandler):  # pragma: no cov
    type: Literal["restapi"] = "restapi"
    service_type: Literal["datadog", "grafana", "cloudwatch", "generic"] = (
        "generic"
    )
    api_url: str = ""
    api_key: Optional[str] = None
    timeout: float = 10.0
    max_retries: int = 3

    def _format_for_service(self, meta: Metadata) -> dict:
        """Format trace metadata for specific service."""
        base_data = meta.model_dump()

        if self.service_type == "datadog":
            return {
                "message": base_data["message"],
                "level": base_data["level"],
                "timestamp": base_data["datetime"],
                "service": "ddeutil-workflow",
                "source": "python",
                "tags": [
                    f"run_id:{meta.run_id}",
                    (
                        f"parent_run_id:{meta.parent_run_id}"
                        if meta.parent_run_id
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
                    "run_id": meta.run_id,
                    "parent_run_id": meta.parent_run_id,
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
                            "run_id": meta.run_id,
                            "parent_run_id": meta.parent_run_id,
                            "level": base_data["level"],
                            "mode": base_data["mode"],
                            "service": "ddeutil-workflow",
                        },
                        "values": [
                            [
                                str(
                                    int(
                                        meta.datetime.replace(" ", "T").replace(
                                            ":", ""
                                        )
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
                "logGroupName": f"/ddeutil/workflow/{meta.run_id}",
                "logStreamName": f"workflow-{meta.run_id}",
                "logEvents": [
                    {
                        "timestamp": int(
                            meta.datetime.replace(" ", "T").replace(":", "")
                        ),
                        "message": json.dumps(
                            {
                                "message": base_data["message"],
                                "level": base_data["level"],
                                "run_id": meta.run_id,
                                "parent_run_id": meta.parent_run_id,
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

        else:
            return {
                "timestamp": base_data["datetime"],
                "level": base_data["level"],
                "message": base_data["message"],
                "run_id": meta.run_id,
                "parent_run_id": meta.parent_run_id,
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

    def session(self):
        try:
            import requests

            session = requests.Session()

            # NOTE: Set default headers
            headers: dict[str, Any] = {
                "Content-Type": "application/json",
                "User-Agent": "ddeutil-workflow/1.0",
            }

            # NOTE: Add service-specific headers
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

            session.headers.update(headers)
            return session
        except ImportError as e:
            raise ImportError(
                "REST API handler requires 'requests' package"
            ) from e

    def emit(
        self,
        metadata: Metadata,
        *,
        extra: Optional[DictData] = None,
    ): ...

    async def amit(
        self,
        metadata: Metadata,
        *,
        extra: Optional[DictData] = None,
    ) -> None: ...

    def flush(
        self, metadata: list[Metadata], *, extra: Optional[DictData] = None
    ) -> None:
        session = self.session()
        try:
            formatted_records = [
                self._format_for_service(meta) for meta in metadata
            ]

            # NOTE: Prepare payload based on service type
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
                    response = session.post(
                        self.api_url, json=payload, timeout=self.timeout
                    )
                    response.raise_for_status()
                except Exception as e:
                    if attempt == self.max_retries - 1:
                        logger.error(
                            f"Failed to send logs to REST API after {self.max_retries} attempts: {e}"
                        )
                    else:
                        import time

                        time.sleep(2**attempt)  # Exponential backoff

        except Exception as e:
            logger.error(f"Failed to send logs to REST API: {e}")
        finally:
            session.close()


class ElasticHandler(BaseHandler):  # pragma: no cov
    """High-performance Elasticsearch logging handler for workflow traces.

    This handler provides optimized Elasticsearch-based logging with connection
    pooling, bulk indexing, and structured metadata storage for scalable
    log aggregation and search capabilities.
    """

    type: Literal["elastic"] = "elastic"
    hosts: Union[str, list[str]]
    username: Optional[str] = None
    password: Optional[str] = None
    index: str
    timeout: float = 30.0
    max_retries: int = 3

    @field_validator(
        "hosts", mode="before", json_schema_input_type=Union[str, list[str]]
    )
    def __prepare_hosts(cls, data: Any) -> Any:
        if isinstance(data, str):
            return [data]
        return data

    def client(self):
        """Initialize Elasticsearch client."""
        try:
            from elasticsearch import Elasticsearch

            client = Elasticsearch(
                hosts=self.hosts,
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
            if not client.ping():
                raise ConnectionError("Failed to connect to Elasticsearch")

            # NOTE: Create index if it doesn't exist
            self._create_index(client)
            return client
        except ImportError as e:
            raise ImportError(
                "Elasticsearch handler requires 'elasticsearch' package"
            ) from e

    def _create_index(self, client):
        try:
            if not client.indices.exists(index=self.index):
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
                            "duration_ms": {"type": "float"},
                            "memory_usage_mb": {"type": "float"},
                            "cpu_usage_percent": {"type": "float"},
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

                client.indices.create(index=self.index, body=mapping)

        except Exception as e:
            logger.error(f"Failed to create Elasticsearch index: {e}")

    @staticmethod
    def _format_for_elastic(metadata: Metadata) -> dict:
        """Format trace metadata for Elasticsearch indexing."""
        base_data = metadata.model_dump()
        try:
            dt = datetime.strptime(base_data["datetime"], "%Y-%m-%d %H:%M:%S")
            iso_datetime = dt.isoformat()
        except ValueError:
            iso_datetime = base_data["datetime"]

        return {
            "run_id": base_data["run_id"],
            "parent_run_id": base_data["parent_run_id"],
            "level": base_data["level"],
            "message": base_data["message"],
            "mode": base_data["mode"],
            "datetime": iso_datetime,
            "process": base_data["process"],
            "thread": base_data["thread"],
            "filename": base_data["filename"],
            "lineno": base_data["lineno"],
            "cut_id": base_data["cut_id"],
            "duration_ms": base_data.get("duration_ms"),
            "memory_usage_mb": base_data.get("memory_usage_mb"),
            "cpu_usage_percent": base_data.get("cpu_usage_percent"),
            "hostname": base_data.get("hostname"),
            "ip_address": base_data.get("ip_address"),
            "python_version": base_data.get("python_version"),
            "package_version": base_data.get("package_version"),
            "tags": base_data.get("tags", []),
            "metadata": base_data.get("metadata", {}),
            "created_at": iso_datetime,
        }

    def emit(
        self,
        metadata: Metadata,
        *,
        extra: Optional[DictData] = None,
    ): ...

    async def amit(
        self,
        metadata: Metadata,
        *,
        extra: Optional[DictData] = None,
    ) -> None: ...

    def flush(
        self,
        metadata: list[Metadata],
        *,
        extra: Optional[DictData] = None,
    ) -> None:
        client = self.client()
        try:
            bulk_data = []
            for meta in metadata:
                record = self._format_for_elastic(metadata=meta)
                bulk_data.append(
                    {
                        "index": {
                            "_index": self.index,
                            "_id": f"{meta.pointer_id}_{record['datetime']}_{record['thread']}",
                        }
                    }
                )
                bulk_data.append(record)

            # Execute bulk indexing
            response = client.bulk(body=bulk_data, refresh=True)

            # Check for errors
            if response.get("errors", False):
                for item in response.get("items", []):
                    if "index" in item and "error" in item["index"]:
                        logger.error(
                            f"Elasticsearch indexing error: {item['index']['error']}"
                        )
        finally:
            client.close()

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
                    trace_meta = Metadata(
                        run_id=source["run_id"],
                        parent_run_id=source["parent_run_id"],
                        error_flag=source["error_flag"],
                        level=source["level"],
                        datetime=source["datetime"],
                        process=source["process"],
                        thread=source["thread"],
                        message=source["message"],
                        cut_id=source.get("cut_id"),
                        filename=source["filename"],
                        lineno=source["lineno"],
                        duration_ms=source.get("duration_ms"),
                        memory_usage_mb=source.get("memory_usage_mb"),
                        cpu_usage_percent=source.get("cpu_usage_percent"),
                        hostname=source.get("hostname"),
                        ip_address=source.get("ip_address"),
                        python_version=source.get("python_version"),
                        package_version=source.get("package_version"),
                        tags=source.get("tags", []),
                        metric=source.get("metric", {}),
                    )

                    meta_list.append(trace_meta)
                    fmt = (
                        dynamic("log_format_file", extras=extras)
                        or "{datetime} ({process:5d}, {thread:5d}) ({cut_id}) {message:120s} ({filename}:{lineno})"
                    )
                    formatted_line = fmt.format(**trace_meta.model_dump())

                    if trace_meta.error_flag:
                        stderr_lines.append(formatted_line)
                    else:
                        stdout_lines.append(formatted_line)

                yield TraceData(
                    stdout="\n".join(stdout_lines),
                    stderr="\n".join(stderr_lines),
                    meta=meta_list,
                )

            client.close()

        except ImportError as e:
            raise ImportError(
                "Elasticsearch handler requires 'elasticsearch' package"
            ) from e
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
                trace_meta = Metadata(
                    run_id=source["run_id"],
                    parent_run_id=source["parent_run_id"],
                    error_flag=source["error_flag"],
                    level=source["level"],
                    datetime=source["datetime"],
                    process=source["process"],
                    thread=source["thread"],
                    message=source["message"],
                    cut_id=source.get("cut_id"),
                    filename=source["filename"],
                    lineno=source["lineno"],
                    duration_ms=source.get("duration_ms"),
                    memory_usage_mb=source.get("memory_usage_mb"),
                    cpu_usage_percent=source.get("cpu_usage_percent"),
                    hostname=source.get("hostname"),
                    ip_address=source.get("ip_address"),
                    python_version=source.get("python_version"),
                    package_version=source.get("package_version"),
                    tags=source.get("tags", []),
                    metric=source.get("metric", {}),
                )

                meta_list.append(trace_meta)

                # Add to stdout/stderr based on mode
                fmt = (
                    dynamic("log_format_file", extras=extras)
                    or "{datetime} ({process:5d}, {thread:5d}) ({cut_id}) {message:120s} ({filename}:{lineno})"
                )
                formatted_line = fmt.format(**trace_meta.model_dump())

                if trace_meta.error_flag:
                    stderr_lines.append(formatted_line)
                else:
                    stdout_lines.append(formatted_line)

            client.close()

            return TraceData(
                stdout="\n".join(stdout_lines),
                stderr="\n".join(stderr_lines),
                meta=meta_list,
            )

        except ImportError as e:
            raise ImportError(
                "Elasticsearch handler requires 'elasticsearch' package"
            ) from e
        except Exception as e:
            logger.error(f"Failed to read from Elasticsearch: {e}")
            if force_raise:
                raise
            return TraceData(stdout="", stderr="")


Handler = TypeVar("Handler", bound=BaseHandler)
TraceHandler = Annotated[
    Union[
        ConsoleHandler,
        FileHandler,
        # SQLiteHandler,
        # RestAPIHandler,
        # ElasticHandler
    ],
    Field(discriminator="type"),
]


class BaseEmit(ABC):

    @abstractmethod
    def emit(
        self,
        msg: str,
        level: Level,
        *,
        metric: Optional[DictData] = None,
        module: Optional[PrefixType] = None,
    ) -> None:
        """Write trace log with append mode and logging this message with any
        logging level.

        Args:
            msg: A message that want to log.
            level: A logging level.
            metric (DictData, default None): A metric data that want to export
                to each target handler.
            module (PrefixType, default None): A module name that use for adding
                prefix at the message value.
        """
        raise NotImplementedError(
            "Emit action should be implement for making trace log."
        )

    def debug(self, msg: str, module: Optional[PrefixType] = None):
        """Write trace log with append mode and logging this message with the
        DEBUG level.

        Args:
            msg: A message that want to log.
            module (PrefixType, default None): A module name that use for adding
                prefix at the message value.
        """
        self.emit(msg, level="debug", module=module)

    def info(self, msg: str, module: Optional[PrefixType] = None) -> None:
        """Write trace log with append mode and logging this message with the
        INFO level.

        Args:
            msg: A message that want to log.
            module (PrefixType, default None): A module name that use for adding
                prefix at the message value.
        """
        self.emit(msg, level="info", module=module)

    def warning(self, msg: str, module: Optional[PrefixType] = None) -> None:
        """Write trace log with append mode and logging this message with the
        WARNING level.

        Args:
            msg: A message that want to log.
            module (PrefixType, default None): A module name that use for adding
                prefix at the message value.
        """
        self.emit(msg, level="warning", module=module)

    def error(self, msg: str, module: Optional[PrefixType] = None) -> None:
        """Write trace log with append mode and logging this message with the
        ERROR level.

        Args:
            msg: A message that want to log.
            module (PrefixType, default None): A module name that use for adding
                prefix at the message value.
        """
        self.emit(msg, level="error", module=module)

    def exception(self, msg: str, module: Optional[PrefixType] = None) -> None:
        """Write trace log with append mode and logging this message with the
        EXCEPTION level.

        Args:
            msg: A message that want to log.
            module (PrefixType, default None): A module name that use for adding
                prefix at the message value.
        """
        self.emit(msg, level="exception", module=module)


class BaseAsyncEmit(ABC):
    """Base Async Emit Abstract class for mixin `amit` method and async
    logging that will use prefix with `a` charactor.
    """

    @abstractmethod
    async def amit(
        self,
        msg: str,
        level: Level,
        *,
        metric: Optional[DictData] = None,
        module: Optional[PrefixType] = None,
    ) -> None:
        """Async write trace log with append mode and logging this message with
        any logging level.

        Args:
            msg (str): A message that want to log.
            level (Mode): A logging level.
            metric (DictData, default None): A metric data that want to export
                to each target handler.
            module (PrefixType, default None): A module name that use for adding
                prefix at the message value.
        """
        raise NotImplementedError(
            "Async Logging action should be implement for making trace log."
        )

    async def adebug(
        self, msg: str, module: Optional[PrefixType] = None
    ) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the DEBUG level.

        Args:
            msg: A message that want to log.
            module (PrefixType, default None): A module name that use for adding
                prefix at the message value.
        """
        await self.amit(msg, level="debug", module=module)

    async def ainfo(
        self, msg: str, module: Optional[PrefixType] = None
    ) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the INFO level.

        Args:
            msg: A message that want to log.
            module (PrefixType, default None): A module name that use for adding
                prefix at the message value.
        """
        await self.amit(msg, level="info", module=module)

    async def awarning(
        self, msg: str, module: Optional[PrefixType] = None
    ) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the WARNING level.

        Args:
            msg: A message that want to log.
            module (PrefixType, default None): A module name that use for adding
                prefix at the message value.
        """
        await self.amit(msg, level="warning", module=module)

    async def aerror(
        self, msg: str, module: Optional[PrefixType] = None
    ) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the ERROR level.

        Args:
            msg: A message that want to log.
            module (PrefixType, default None): A module name that use for adding
                prefix at the message value.
        """
        await self.amit(msg, level="error", module=module)

    async def aexception(
        self, msg: str, module: Optional[PrefixType] = None
    ) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the EXCEPTION level.

        Args:
            msg: A message that want to log.
            module (PrefixType, default None): A module name that use for adding
                prefix at the message value.
        """
        await self.amit(msg, level="exception", module=module)


class Trace(BaseModel, BaseEmit, BaseAsyncEmit):
    """Trace Manager model that keep all trance handler and emit log to its
    handler.
    """

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
    handlers: list[TraceHandler] = Field(
        description="A list of Trace handler model."
    )
    buffer_size: int = Field(
        default=10,
        description="A buffer size to trigger flush trace log",
    )

    # NOTE: Private attrs for the internal process.
    _enable_buffer: bool = PrivateAttr(default=False)
    _buffer: list[Metadata] = PrivateAttr(default_factory=list)

    @property
    def cut_id(self) -> str:
        """Combine cutting ID of parent running ID if it set.

        Returns:
            str: The combined cutting ID string.
        """
        cut_run_id: str = cut_id(self.run_id)
        if not self.parent_run_id:
            return cut_run_id

        cut_parent_run_id: str = cut_id(self.parent_run_id)
        return f"{cut_parent_run_id} -> {cut_run_id}"

    def emit(
        self,
        msg: str,
        level: Level,
        *,
        metric: Optional[DictData] = None,
        module: Optional[PrefixType] = None,
    ) -> None:
        """Emit a trace log to all handler. This will use synchronise process.

        Args:
            msg (str): A message.
            level (Level): A tracing level.
            metric (DictData, default None): A metric data that want to export
                to each target handler.
            module (PrefixType, default None): A module name that use for adding
                prefix at the message value.
        """
        _msg: Message = Message.from_str(msg, module=module)
        metadata: Metadata = Metadata.make(
            error_flag=(level in ("error", "exception")),
            level=level,
            module=_msg.module,
            message=prepare_newline(_msg.prepare(self.extras)),
            cutting_id=self.cut_id,
            run_id=self.run_id,
            parent_run_id=self.parent_run_id,
            metric=metric,
            extras=self.extras,
        )

        # NOTE: Check enable buffer flag was set or not.
        if not self._enable_buffer:

            # NOTE: Start emit tracing log data to each handler.
            for handler in self.handlers:
                handler.emit(metadata, extra=self.extras)
            return

        # NOTE: Update metadata to the buffer.
        self._buffer.append(metadata)

        if len(self._buffer) >= self.buffer_size:  # pragma: no cov
            for handler in self.handlers:
                handler.flush(self._buffer, extra=self.extras)
            self._buffer.clear()

    async def amit(
        self,
        msg: str,
        level: Level,
        *,
        metric: Optional[DictData] = None,
        module: Optional[PrefixType] = None,
    ) -> None:
        """Async write trace log with append mode and logging this message with
        any logging level.

        Args:
            msg (str): A message that want to log.
            level (Level): A logging mode.
            metric (DictData, default None): A metric data that want to export
                to each target handler.
            module (PrefixType, default None): A module name that use for adding
                prefix at the message value.
        """
        _msg: Message = Message.from_str(msg, module=module)
        metadata: Metadata = Metadata.make(
            error_flag=(level in ("error", "exception")),
            level=level,
            module=_msg.module,
            message=prepare_newline(_msg.prepare(self.extras)),
            cutting_id=self.cut_id,
            run_id=self.run_id,
            parent_run_id=self.parent_run_id,
            metric=metric,
            extras=self.extras,
        )

        # NOTE: Start emit tracing log data to each handler.
        for handler in self.handlers:
            await handler.amit(metadata, extra=self.extras)

    @contextlib.contextmanager
    def buffer(self, module: Optional[PrefixType] = None) -> Iterator[Self]:
        """Enter the trace for catching the logs that run so fast. It will use
        buffer strategy to flush the logs instead emit.

        Args:
            module (PrefixType, default None): A module name that use for adding
                prefix at the message value.
        """
        self._enable_buffer = True
        exception: Optional[Exception] = None
        try:
            yield self
        except Exception as err:
            _msg: Message = Message.from_str(str(err), module=module)
            metadata: Metadata = Metadata.make(
                error_flag=True,
                level="error",
                module=_msg.module,
                message=prepare_newline(_msg.prepare(self.extras)),
                cutting_id=self.cut_id,
                run_id=self.run_id,
                parent_run_id=self.parent_run_id,
                extras=self.extras,
            )
            self._buffer.append(metadata)
            exception = err
        finally:
            if self._buffer:
                for handler in self.handlers:
                    handler.flush(self._buffer, extra=self.extras)
                self._buffer.clear()

            # NOTE: Raise the current exception after emit log.
            if exception:
                raise exception


def get_trace(
    run_id: str,
    *,
    handlers: list[Union[DictData, Handler]] = None,
    parent_run_id: Optional[str] = None,
    extras: Optional[DictData] = None,
    pre_process: bool = False,
) -> Trace:
    """Get dynamic Trace instance from the core config. This function will use
    for start some process, and it wants to generated trace object.

        This factory function returns the appropriate trace implementation based
    on configuration. It can be overridden by extras argument and accepts
    running ID and parent running ID.

    Args:
        run_id (str): A running ID.
        parent_run_id (str, default None): A parent running ID.
        handlers (list[DictData | Handler], default None): A list of handler or
            mapping of handler data that want to direct pass instead use
            environment variable config.
        extras (DictData, default None): An extra parameter that want to
            override the core config values.
        pre_process (bool, default False) A flag that will auto call pre
            method after validate a trace model.

    Returns:
        Trace: The appropriate trace instance.
    """
    trace: Trace = Trace.model_validate(
        {
            "run_id": run_id,
            "parent_run_id": parent_run_id,
            "handlers": dynamic("trace_handlers", f=handlers, extras=extras),
            "extras": extras or {},
        }
    )
    # NOTE: Start pre-process when start create trace.
    if pre_process:
        for handler in trace.handlers:
            handler.pre()
    return trace
