# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
# [x] Use fix config
"""A Logs module contain TraceLog dataclass and AuditLog model.
"""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime
from inspect import Traceback, currentframe, getframeinfo
from pathlib import Path
from threading import get_ident
from typing import ClassVar, Literal, Optional, Union

from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass
from pydantic.functional_validators import model_validator
from typing_extensions import Self

from .__types import DictData, DictStr, TupleStr
from .conf import config, get_logger
from .utils import cut_id, get_dt_now

logger = get_logger("ddeutil.workflow")

__all__: TupleStr = (
    "FileTraceLog",
    "SQLiteTraceLog",
    "TraceData",
    "TraceMeda",
    "TraceLog",
    "get_dt_tznow",
    "get_trace",
    "get_trace_obj",
    "get_audit",
    "FileAudit",
    "SQLiteAudit",
    "Audit",
)


def get_dt_tznow() -> datetime:  # pragma: no cov
    """Return the current datetime object that passing the config timezone.

    :rtype: datetime
    """
    return get_dt_now(tz=config.tz)


class TraceMeda(BaseModel):  # pragma: no cov
    mode: Literal["stdout", "stderr"]
    datetime: str
    process: int
    thread: int
    message: str
    filename: str
    lineno: int

    @classmethod
    def make(cls, mode: Literal["stdout", "stderr"], message: str) -> Self:
        """Make a TraceMeda instance."""
        frame_info: Traceback = getframeinfo(
            currentframe().f_back.f_back.f_back
        )
        return cls(
            mode=mode,
            datetime=get_dt_tznow().strftime(config.log_datetime_format),
            process=os.getpid(),
            thread=get_ident(),
            message=message,
            filename=frame_info.filename.split(os.path.sep)[-1],
            lineno=frame_info.lineno,
        )


class TraceData(BaseModel):  # pragma: no cov
    """Trace Data model for keeping data for any Trace models."""

    stdout: str = Field(description="A standard output trace data.")
    stderr: str = Field(description="A standard error trace data.")
    meta: list[TraceMeda] = Field(
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
        data: DictStr = {"stdout": "", "stderr": "", "meta": []}

        if (file / "stdout.txt").exists():
            data["stdout"] = (file / "stdout.txt").read_text(encoding="utf-8")

        if (file / "stderr.txt").exists():
            data["stderr"] = (file / "stderr.txt").read_text(encoding="utf-8")

        if (file / "metadata.json").exists():
            data["meta"] = [
                json.loads(line)
                for line in (
                    (file / "metadata.json")
                    .read_text(encoding="utf-8")
                    .splitlines()
                )
            ]

        return cls.model_validate(data)


@dataclass(frozen=True)
class BaseTraceLog(ABC):  # pragma: no cov
    """Base Trace Log dataclass object."""

    run_id: str
    parent_run_id: Optional[str] = None

    @abstractmethod
    def writer(self, message: str, is_err: bool = False) -> None:
        """Write a trace message after making to target pointer object. The
        target can be anything be inherited this class and overwrite this method
        such as file, console, or database.

        :param message: A message after making.
        :param is_err: A flag for writing with an error trace or not.
        """
        raise NotImplementedError(
            "Create writer logic for this trace object before using."
        )

    @abstractmethod
    async def awriter(self, message: str, is_err: bool = False) -> None:
        """Async Write a trace message after making to target pointer object.

        :param message:
        :param is_err:
        """

    @abstractmethod
    def make_message(self, message: str) -> str:
        """Prepare and Make a message before write and log processes.

        :param message: A message that want to prepare and make before.

        :rtype: str
        """
        raise NotImplementedError(
            "Adjust make message method for this trace object before using."
        )

    def debug(self, message: str):
        """Write trace log with append mode and logging this message with the
        DEBUG level.

        :param message: (str) A message that want to log.
        """
        msg: str = self.make_message(message)

        if config.debug:
            self.writer(msg)

        logger.debug(msg, stacklevel=2)

    def info(self, message: str) -> None:
        """Write trace log with append mode and logging this message with the
        INFO level.

        :param message: (str) A message that want to log.
        """
        msg: str = self.make_message(message)
        self.writer(msg)
        logger.info(msg, stacklevel=2)

    def warning(self, message: str) -> None:
        """Write trace log with append mode and logging this message with the
        WARNING level.

        :param message: (str) A message that want to log.
        """
        msg: str = self.make_message(message)
        self.writer(msg)
        logger.warning(msg, stacklevel=2)

    def error(self, message: str) -> None:
        """Write trace log with append mode and logging this message with the
        ERROR level.

        :param message: (str) A message that want to log.
        """
        msg: str = self.make_message(message)
        self.writer(msg, is_err=True)
        logger.error(msg, stacklevel=2)

    def exception(self, message: str) -> None:
        """Write trace log with append mode and logging this message with the
        EXCEPTION level.

        :param message: (str) A message that want to log.
        """
        msg: str = self.make_message(message)
        self.writer(msg, is_err=True)
        logger.exception(msg, stacklevel=2)

    async def adebug(self, message: str) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the DEBUG level.

        :param message: (str) A message that want to log.
        """
        msg: str = self.make_message(message)
        if config.debug:
            await self.awriter(msg)
        logger.info(msg, stacklevel=2)

    async def ainfo(self, message: str) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the INFO level.

        :param message: (str) A message that want to log.
        """
        msg: str = self.make_message(message)
        await self.awriter(msg)
        logger.info(msg, stacklevel=2)

    async def awarning(self, message: str) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the WARNING level.

        :param message: (str) A message that want to log.
        """
        msg: str = self.make_message(message)
        await self.awriter(msg)
        logger.warning(msg, stacklevel=2)

    async def aerror(self, message: str) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the ERROR level.

        :param message: (str) A message that want to log.
        """
        msg: str = self.make_message(message)
        await self.awriter(msg, is_err=True)
        logger.error(msg, stacklevel=2)

    async def aexception(self, message: str) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the EXCEPTION level.

        :param message: (str) A message that want to log.
        """
        msg: str = self.make_message(message)
        await self.awriter(msg, is_err=True)
        logger.exception(msg, stacklevel=2)


class FileTraceLog(BaseTraceLog):  # pragma: no cov
    """Trace Log object that write file to the local storage."""

    @classmethod
    def find_logs(
        cls, path: Path | None = None
    ) -> Iterator[TraceData]:  # pragma: no cov
        """Find trace logs."""
        for file in sorted(
            (path or config.log_path).glob("./run_id=*"),
            key=lambda f: f.lstat().st_mtime,
        ):
            yield TraceData.from_path(file)

    @classmethod
    def find_log_with_id(
        cls, run_id: str, force_raise: bool = True, *, path: Path | None = None
    ) -> TraceData:
        """Find trace log with an input specific run ID."""
        base_path: Path = path or config.log_path
        file: Path = base_path / f"run_id={run_id}"
        if file.exists():
            return TraceData.from_path(file)
        elif force_raise:
            raise FileNotFoundError(
                f"Trace log on path {base_path}, does not found trace "
                f"'run_id={run_id}'."
            )
        return {}

    @property
    def pointer(self) -> Path:
        log_file: Path = (
            config.log_path / f"run_id={self.parent_run_id or self.run_id}"
        )
        if not log_file.exists():
            log_file.mkdir(parents=True)
        return log_file

    @property
    def cut_id(self) -> str:
        """Combine cutting ID of parent running ID if it set.

        :rtype: str
        """
        cut_run_id: str = cut_id(self.run_id)
        if not self.parent_run_id:
            return f"{cut_run_id} -> {' ' * 6}"

        cut_parent_run_id: str = cut_id(self.parent_run_id)
        return f"{cut_parent_run_id} -> {cut_run_id}"

    def make_message(self, message: str) -> str:
        """Prepare and Make a message before write and log processes.

        :param message: (str) A message that want to prepare and make before.

        :rtype: str
        """
        return f"({self.cut_id}) {message}"

    def writer(self, message: str, is_err: bool = False) -> None:
        """Write a trace message after making to target file and write metadata
        in the same path of standard files.

            The path of logging data will store by format:

            ... ./logs/run_id=<run-id>/metadata.json
            ... ./logs/run_id=<run-id>/stdout.txt
            ... ./logs/run_id=<run-id>/stderr.txt

        :param message: A message after making.
        :param is_err: A flag for writing with an error trace or not.
        """
        if not config.enable_write_log:
            return

        write_file: str = "stderr" if is_err else "stdout"
        trace_meta: TraceMeda = TraceMeda.make(mode=write_file, message=message)

        with (self.pointer / f"{write_file}.txt").open(
            mode="at", encoding="utf-8"
        ) as f:
            f.write(
                f"{config.log_format_file}\n".format(**trace_meta.model_dump())
            )

        with (self.pointer / "metadata.json").open(
            mode="at", encoding="utf-8"
        ) as f:
            f.write(trace_meta.model_dump_json() + "\n")

    async def awriter(
        self, message: str, is_err: bool = False
    ) -> None:  # pragma: no cov
        if not config.enable_write_log:
            return

        try:
            import aiofiles
        except ImportError as e:
            raise ImportError("Async mode need aiofiles package") from e

        write_file: str = "stderr" if is_err else "stdout"
        trace_meta: TraceMeda = TraceMeda.make(mode=write_file, message=message)

        async with aiofiles.open(
            self.pointer / f"{write_file}.txt", mode="at", encoding="utf-8"
        ) as f:
            await f.write(
                f"{config.log_format_file}\n".format(**trace_meta.model_dump())
            )

        async with aiofiles.open(
            self.pointer / "metadata.json", mode="at", encoding="utf-8"
        ) as f:
            await f.write(trace_meta.model_dump_json() + "\n")


class SQLiteTraceLog(BaseTraceLog):  # pragma: no cov
    """Trace Log object that write trace log to the SQLite database file."""

    table_name: ClassVar[str] = "audits"
    schemas: ClassVar[
        str
    ] = """
        run_id          int,
        stdout          str,
        stderr          str,
        update          datetime
        primary key ( run_id )
        """

    @classmethod
    def find_logs(cls) -> Iterator[DictStr]: ...

    @classmethod
    def find_log_with_id(cls, run_id: str) -> DictStr: ...

    def make_message(self, message: str) -> str: ...

    def writer(self, message: str, is_err: bool = False) -> None: ...

    def awriter(self, message: str, is_err: bool = False) -> None: ...


TraceLog = Union[
    FileTraceLog,
    SQLiteTraceLog,
]


def get_trace(
    run_id: str, parent_run_id: str | None = None
) -> TraceLog:  # pragma: no cov
    """Get dynamic TraceLog object from the setting config."""
    if config.log_path.is_file():
        return SQLiteTraceLog(run_id, parent_run_id=parent_run_id)
    return FileTraceLog(run_id, parent_run_id=parent_run_id)


def get_trace_obj() -> type[TraceLog]:  # pragma: no cov
    if config.log_path.is_file():
        return SQLiteTraceLog
    return FileTraceLog


class BaseAudit(BaseModel, ABC):
    """Base Audit Pydantic Model with abstraction class property that implement
    only model fields. This model should to use with inherit to logging
    subclass like file, sqlite, etc.
    """

    name: str = Field(description="A workflow name.")
    release: datetime = Field(description="A release datetime.")
    type: str = Field(description="A running type before logging.")
    context: DictData = Field(
        default_factory=dict,
        description="A context that receive from a workflow execution result.",
    )
    parent_run_id: Optional[str] = Field(
        default=None, description="A parent running ID."
    )
    run_id: str = Field(description="A running ID")
    update: datetime = Field(default_factory=get_dt_tznow)
    execution_time: float = Field(default=0, description="An execution time.")

    @model_validator(mode="after")
    def __model_action(self) -> Self:
        """Do before the Audit action with WORKFLOW_AUDIT_ENABLE_WRITE env variable.

        :rtype: Self
        """
        if config.enable_write_audit:
            self.do_before()
        return self

    def do_before(self) -> None:  # pragma: no cov
        """To something before end up of initial log model."""

    @abstractmethod
    def save(self, excluded: list[str] | None) -> None:  # pragma: no cov
        """Save this model logging to target logging store."""
        raise NotImplementedError("Audit should implement ``save`` method.")


class FileAudit(BaseAudit):
    """File Audit Pydantic Model that use to saving log data from result of
    workflow execution. It inherits from BaseAudit model that implement the
    ``self.save`` method for file.
    """

    filename_fmt: ClassVar[str] = (
        "workflow={name}/release={release:%Y%m%d%H%M%S}"
    )

    def do_before(self) -> None:
        """Create directory of release before saving log file."""
        self.pointer().mkdir(parents=True, exist_ok=True)

    @classmethod
    def find_audits(cls, name: str) -> Iterator[Self]:
        """Generate the audit data that found from logs path with specific a
        workflow name.

        :param name: A workflow name that want to search release logging data.

        :rtype: Iterator[Self]
        """
        pointer: Path = config.audit_path / f"workflow={name}"
        if not pointer.exists():
            raise FileNotFoundError(f"Pointer: {pointer.absolute()}.")

        for file in pointer.glob("./release=*/*.log"):
            with file.open(mode="r", encoding="utf-8") as f:
                yield cls.model_validate(obj=json.load(f))

    @classmethod
    def find_audit_with_release(
        cls,
        name: str,
        release: datetime | None = None,
    ) -> Self:
        """Return the audit data that found from logs path with specific
        workflow name and release values. If a release does not pass to an input
        argument, it will return the latest release from the current log path.

        :param name: A workflow name that want to search log.
        :param release: A release datetime that want to search log.

        :raise FileNotFoundError:
        :raise NotImplementedError: If an input release does not pass to this
            method. Because this method does not implement latest log.

        :rtype: Self
        """
        if release is None:
            raise NotImplementedError("Find latest log does not implement yet.")

        pointer: Path = (
            config.audit_path
            / f"workflow={name}/release={release:%Y%m%d%H%M%S}"
        )
        if not pointer.exists():
            raise FileNotFoundError(
                f"Pointer: ./logs/workflow={name}/"
                f"release={release:%Y%m%d%H%M%S} does not found."
            )

        latest_file: Path = max(pointer.glob("./*.log"), key=os.path.getctime)
        with latest_file.open(mode="r", encoding="utf-8") as f:
            return cls.model_validate(obj=json.load(f))

    @classmethod
    def is_pointed(cls, name: str, release: datetime) -> bool:
        """Check the release log already pointed or created at the destination
        log path.

        :param name: A workflow name.
        :param release: A release datetime.

        :rtype: bool
        :return: Return False if the release log was not pointed or created.
        """
        # NOTE: Return False if enable writing log flag does not set.
        if not config.enable_write_audit:
            return False

        # NOTE: create pointer path that use the same logic of pointer method.
        pointer: Path = config.audit_path / cls.filename_fmt.format(
            name=name, release=release
        )

        return pointer.exists()

    def pointer(self) -> Path:
        """Return release directory path that was generated from model data.

        :rtype: Path
        """
        return config.audit_path / self.filename_fmt.format(
            name=self.name, release=self.release
        )

    def save(self, excluded: list[str] | None) -> Self:
        """Save logging data that receive a context data from a workflow
        execution result.

        :param excluded: An excluded list of key name that want to pass in the
            model_dump method.

        :rtype: Self
        """
        trace: TraceLog = get_trace(self.run_id, self.parent_run_id)

        # NOTE: Check environ variable was set for real writing.
        if not config.enable_write_audit:
            trace.debug("[LOG]: Skip writing log cause config was set")
            return self

        log_file: Path = (
            self.pointer() / f"{self.parent_run_id or self.run_id}.log"
        )
        log_file.write_text(
            json.dumps(
                self.model_dump(exclude=excluded),
                default=str,
                indent=2,
            ),
            encoding="utf-8",
        )
        return self


class SQLiteAudit(BaseAudit):  # pragma: no cov
    """SQLite Audit Pydantic Model."""

    table_name: ClassVar[str] = "audits"
    schemas: ClassVar[
        str
    ] = """
        workflow        str,
        release         int,
        type            str,
        context         json,
        parent_run_id   int,
        run_id          int,
        update          datetime
        primary key ( run_id )
        """

    def save(self, excluded: list[str] | None) -> SQLiteAudit:
        """Save logging data that receive a context data from a workflow
        execution result.
        """
        trace: TraceLog = get_trace(self.run_id, self.parent_run_id)

        # NOTE: Check environ variable was set for real writing.
        if not config.enable_write_audit:
            trace.debug("[LOG]: Skip writing log cause config was set")
            return self

        raise NotImplementedError("SQLiteAudit does not implement yet.")


class RemoteFileAudit(FileAudit):  # pragma: no cov
    """Remote File Audit Pydantic Model."""

    def save(self, excluded: list[str] | None) -> RemoteFileAudit: ...


class RedisAudit(BaseAudit):  # pragma: no cov
    """Redis Audit Pydantic Model."""

    def save(self, excluded: list[str] | None) -> RedisAudit: ...


Audit = Union[
    FileAudit,
    SQLiteAudit,
]


def get_audit() -> type[Audit]:  # pragma: no cov
    """Get an audit class that dynamic base on the config audit path value.

    :rtype: type[Audit]
    """
    if config.audit_path.is_file():
        return SQLiteAudit
    return FileAudit
