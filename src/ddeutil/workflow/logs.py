# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
# [x] Use fix config for `get_logger`, and Model initialize step.
"""A Logs module contain Trace and Audit Pydantic models for process log from
the core workflow engine. I separate part of log to 2 types:
  - Trace: A stdout and stderr log
  - Audit: An audit release log for tracking incremental running workflow.
"""
from __future__ import annotations

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
from threading import get_ident
from types import FrameType
from typing import ClassVar, Literal, Optional, TypeVar, Union

from pydantic import BaseModel, ConfigDict, Field
from pydantic.functional_validators import model_validator
from typing_extensions import Self

from .__types import DictData
from .conf import config, dynamic
from .utils import cut_id, get_dt_now, prepare_newline

METADATA: str = "metadata.json"


@lru_cache
def get_logger(name: str):
    """Return logger object with an input module name.

    :param name: (str) A module name that want to log.
    """
    lg = logging.getLogger(name)

    # NOTE: Developers using this package can then disable all logging just for
    #   this package by;
    #
    #   `logging.getLogger('ddeutil.workflow').propagate = False`
    #
    lg.addHandler(logging.NullHandler())

    formatter = logging.Formatter(
        fmt=config.log_format,
        datefmt=config.log_datetime_format,
    )
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    lg.addHandler(stream)

    lg.setLevel(logging.DEBUG if config.debug else logging.INFO)
    return lg


logger = get_logger("ddeutil.workflow")


def get_dt_tznow() -> datetime:  # pragma: no cov
    """Return the current datetime object that passing the config timezone.

    :rtype: datetime
    """
    return get_dt_now(tz=config.tz)


PREFIX_LOGS: dict[str, dict] = {
    "CALLER": {
        "emoji": "📍",
        "desc": "logs from any usage from custom caller function.",
    },
    "STAGE": {"emoji": "⚙️", "desc": "logs from stages module."},
    "JOB": {"emoji": "⛓️", "desc": "logs from job module."},
    "WORKFLOW": {"emoji": "🏃", "desc": "logs from workflow module."},
    "RELEASE": {"emoji": "📅", "desc": "logs from release workflow method."},
    "POKE": {"emoji": "⏰", "desc": "logs from poke workflow method."},
}  # pragma: no cov
PREFIX_DEFAULT: str = "CALLER"
PREFIX_LOGS_REGEX: re.Pattern[str] = re.compile(
    rf"(^\[(?P<name>{'|'.join(PREFIX_LOGS)})]:\s?)?(?P<message>.*)",
    re.MULTILINE | re.DOTALL | re.ASCII | re.VERBOSE,
)  # pragma: no cov


class PrefixMsg(BaseModel):
    """Prefix Message model for receive grouping dict from searching prefix data
    from logging message.
    """

    name: Optional[str] = Field(default=None)
    message: Optional[str] = Field(default=None)

    def prepare(self, extras: Optional[DictData] = None) -> str:
        """Prepare message with force add prefix before writing trace log.

        :rtype: str
        """
        name: str = self.name or PREFIX_DEFAULT
        emoji: str = (
            f"{PREFIX_LOGS[name]['emoji']} "
            if (extras or {}).get("log_add_emoji", True)
            else ""
        )
        return f"{emoji}[{name}]: {self.message}"


def extract_msg_prefix(msg: str) -> PrefixMsg:
    """Extract message prefix from an input message.

    :param msg: A message that want to extract.

    :rtype: PrefixMsg
    """
    return PrefixMsg.model_validate(
        obj=PREFIX_LOGS_REGEX.search(msg).groupdict()
    )


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
    filename: str = Field(description="A filename of this log.")
    lineno: int = Field(description="A line number of this log.")

    @classmethod
    def dynamic_frame(
        cls, frame: FrameType, *, extras: Optional[DictData] = None
    ) -> Traceback:
        """Dynamic Frame information base on the `logs_trace_frame_layer` config
        value that was set from the extra parameter.

        :param frame: (FrameType) The current frame that want to dynamic.
        :param extras: (DictData) An extra parameter that want to get the
            `logs_trace_frame_layer` config value.
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
        *,
        extras: Optional[DictData] = None,
    ) -> Self:
        """Make the current metric for contract this TraceMeta model instance
        that will catch local states like PID, thread identity.

        :param mode: (Literal["stdout", "stderr"]) A metadata mode.
        :param message: (str) A message.
        :param level: (str) A log level.
        :param extras: (DictData) An extra parameter that want to override core
            config values.

        :rtype: Self
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

    run_id: str = Field(default="A running ID")
    parent_run_id: Optional[str] = Field(
        default=None, description="A parent running ID"
    )
    extras: DictData = Field(
        default_factory=dict,
        description=(
            "An extra parameter that want to override on the core config "
            "values."
        ),
    )

    @classmethod
    @abstractmethod
    def find_traces(
        cls,
        path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> Iterator[TraceData]:  # pragma: no cov
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

    @abstractmethod
    def writer(self, message: str, level: str, is_err: bool = False) -> None:
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
        self, message: str, level: str, is_err: bool = False
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

    def __logging(
        self, message: str, mode: str, *, is_err: bool = False
    ) -> None:
        """Write trace log with append mode and logging this message with any
        logging level.

        :param message: (str) A message that want to log.
        """
        msg: str = prepare_newline(
            self.make_message(extract_msg_prefix(message).prepare(self.extras))
        )

        if mode != "debug" or (
            mode == "debug" and dynamic("debug", extras=self.extras)
        ):
            self.writer(msg, level=mode, is_err=is_err)

        getattr(logger, mode)(msg, stacklevel=3)

    def debug(self, message: str):
        """Write trace log with append mode and logging this message with the
        DEBUG level.

        :param message: (str) A message that want to log.
        """
        self.__logging(message, mode="debug")

    def info(self, message: str) -> None:
        """Write trace log with append mode and logging this message with the
        INFO level.

        :param message: (str) A message that want to log.
        """
        self.__logging(message, mode="info")

    def warning(self, message: str) -> None:
        """Write trace log with append mode and logging this message with the
        WARNING level.

        :param message: (str) A message that want to log.
        """
        self.__logging(message, mode="warning")

    def error(self, message: str) -> None:
        """Write trace log with append mode and logging this message with the
        ERROR level.

        :param message: (str) A message that want to log.
        """
        self.__logging(message, mode="error", is_err=True)

    def exception(self, message: str) -> None:
        """Write trace log with append mode and logging this message with the
        EXCEPTION level.

        :param message: (str) A message that want to log.
        """
        self.__logging(message, mode="exception", is_err=True)

    async def __alogging(
        self, message: str, mode: str, *, is_err: bool = False
    ) -> None:
        """Write trace log with append mode and logging this message with any
        logging level.

        :param message: (str) A message that want to log.
        """
        msg: str = prepare_newline(
            self.make_message(extract_msg_prefix(message).prepare(self.extras))
        )

        if mode != "debug" or (
            mode == "debug" and dynamic("debug", extras=self.extras)
        ):
            await self.awriter(msg, level=mode, is_err=is_err)

        getattr(logger, mode)(msg, stacklevel=3)

    async def adebug(self, message: str) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the DEBUG level.

        :param message: (str) A message that want to log.
        """
        await self.__alogging(message, mode="debug")

    async def ainfo(self, message: str) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the INFO level.

        :param message: (str) A message that want to log.
        """
        await self.__alogging(message, mode="info")

    async def awarning(self, message: str) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the WARNING level.

        :param message: (str) A message that want to log.
        """
        await self.__alogging(message, mode="warning")

    async def aerror(self, message: str) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the ERROR level.

        :param message: (str) A message that want to log.
        """
        await self.__alogging(message, mode="error", is_err=True)

    async def aexception(self, message: str) -> None:  # pragma: no cov
        """Async write trace log with append mode and logging this message with
        the EXCEPTION level.

        :param message: (str) A message that want to log.
        """
        await self.__alogging(message, mode="exception", is_err=True)


class FileTrace(BaseTrace):  # pragma: no cov
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
            (path or dynamic("trace_path", extras=extras)).glob("./run_id=*"),
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
        base_path: Path = path or dynamic("trace_path", extras=extras)
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
        log_file: Path = (
            dynamic("trace_path", extras=self.extras)
            / f"run_id={self.parent_run_id or self.run_id}"
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
            return f"{cut_run_id}"

        cut_parent_run_id: str = cut_id(self.parent_run_id)
        return f"{cut_parent_run_id} -> {cut_run_id}"

    def make_message(self, message: str) -> str:
        """Prepare and Make a message before write and log processes.

        :param message: (str) A message that want to prepare and make before.

        :rtype: str
        """
        return f"({self.cut_id}) {message}"

    def writer(self, message: str, level: str, is_err: bool = False) -> None:
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
            mode=mode, level=level, message=message, extras=self.extras
        )

        with (self.pointer / f"{mode}.txt").open(
            mode="at", encoding="utf-8"
        ) as f:
            fmt: str = dynamic("log_format_file", extras=self.extras)
            f.write(f"{fmt}\n".format(**trace_meta.model_dump()))

        with (self.pointer / METADATA).open(mode="at", encoding="utf-8") as f:
            f.write(trace_meta.model_dump_json() + "\n")

    async def awriter(
        self, message: str, level: str, is_err: bool = False
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
            mode=mode, level=level, message=message, extras=self.extras
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
    """SQLite Trace dataclass that write trace log to the SQLite database file."""

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
    def find_traces(
        cls,
        path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> Iterator[TraceData]: ...

    @classmethod
    def find_trace_with_id(
        cls,
        run_id: str,
        force_raise: bool = True,
        *,
        path: Optional[Path] = None,
        extras: Optional[DictData] = None,
    ) -> TraceData: ...

    def make_message(self, message: str) -> str: ...

    def writer(
        self, message: str, level: str, is_err: bool = False
    ) -> None: ...

    def awriter(
        self, message: str, level: str, is_err: bool = False
    ) -> None: ...


Trace = TypeVar("Trace", bound=BaseTrace)
TraceModel = Union[
    FileTrace,
    SQLiteTrace,
]


def get_trace(
    run_id: str,
    *,
    parent_run_id: Optional[str] = None,
    extras: Optional[DictData] = None,
) -> TraceModel:  # pragma: no cov
    """Get dynamic Trace instance from the core config (it can override by an
    extras argument) that passing running ID and parent running ID.

    :param run_id: (str) A running ID.
    :param parent_run_id: (str) A parent running ID.
    :param extras: (DictData) An extra parameter that want to override the core
        config values.

    :rtype: TraceLog
    """
    if dynamic("trace_path", extras=extras).is_file():
        return SQLiteTrace(
            run_id=run_id, parent_run_id=parent_run_id, extras=(extras or {})
        )
    return FileTrace(
        run_id=run_id, parent_run_id=parent_run_id, extras=(extras or {})
    )


class BaseAudit(BaseModel, ABC):
    """Base Audit Pydantic Model with abstraction class property that implement
    only model fields. This model should to use with inherit to logging
    subclass like file, sqlite, etc.
    """

    extras: DictData = Field(
        default_factory=dict,
        description="An extras parameter that want to override core config",
    )
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
        if dynamic("enable_write_audit", extras=self.extras):
            self.do_before()
        return self

    @classmethod
    @abstractmethod
    def is_pointed(
        cls,
        name: str,
        release: datetime,
        *,
        extras: Optional[DictData] = None,
    ) -> bool:
        raise NotImplementedError(
            "Audit should implement `is_pointed` class-method"
        )

    @classmethod
    @abstractmethod
    def find_audits(
        cls, name: str, *, extras: Optional[DictData] = None
    ) -> Iterator[Self]:
        raise NotImplementedError(
            "Audit should implement `find_audits` class-method"
        )

    @classmethod
    @abstractmethod
    def find_audit_with_release(
        cls,
        name: str,
        release: Optional[datetime] = None,
        *,
        extras: Optional[DictData] = None,
    ) -> Self:
        raise NotImplementedError(
            "Audit should implement `find_audit_with_release` class-method"
        )

    def do_before(self) -> None:  # pragma: no cov
        """To something before end up of initial log model."""

    @abstractmethod
    def save(self, excluded: Optional[list[str]]) -> None:  # pragma: no cov
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
    def find_audits(
        cls, name: str, *, extras: Optional[DictData] = None
    ) -> Iterator[Self]:
        """Generate the audit data that found from logs path with specific a
        workflow name.

        :param name: A workflow name that want to search release logging data.
        :param extras: An extra parameter that want to override core config.

        :rtype: Iterator[Self]
        """
        pointer: Path = (
            dynamic("audit_path", extras=extras) / f"workflow={name}"
        )
        if not pointer.exists():
            raise FileNotFoundError(f"Pointer: {pointer.absolute()}.")

        for file in pointer.glob("./release=*/*.log"):
            with file.open(mode="r", encoding="utf-8") as f:
                yield cls.model_validate(obj=json.load(f))

    @classmethod
    def find_audit_with_release(
        cls,
        name: str,
        release: Optional[datetime] = None,
        *,
        extras: Optional[DictData] = None,
    ) -> Self:
        """Return the audit data that found from logs path with specific
        workflow name and release values. If a release does not pass to an input
        argument, it will return the latest release from the current log path.

        :param name: (str) A workflow name that want to search log.
        :param release: (datetime) A release datetime that want to search log.
        :param extras: An extra parameter that want to override core config.

        :raise FileNotFoundError:
        :raise NotImplementedError: If an input release does not pass to this
            method. Because this method does not implement latest log.

        :rtype: Self
        """
        if release is None:
            raise NotImplementedError("Find latest log does not implement yet.")

        pointer: Path = (
            dynamic("audit_path", extras=extras)
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
    def is_pointed(
        cls,
        name: str,
        release: datetime,
        *,
        extras: Optional[DictData] = None,
    ) -> bool:
        """Check the release log already pointed or created at the destination
        log path.

        :param name: (str) A workflow name.
        :param release: (datetime) A release datetime.
        :param extras: An extra parameter that want to override core config.

        :rtype: bool
        :return: Return False if the release log was not pointed or created.
        """
        # NOTE: Return False if enable writing log flag does not set.
        if not dynamic("enable_write_audit", extras=extras):
            return False

        # NOTE: create pointer path that use the same logic of pointer method.
        pointer: Path = dynamic(
            "audit_path", extras=extras
        ) / cls.filename_fmt.format(name=name, release=release)

        return pointer.exists()

    def pointer(self) -> Path:
        """Return release directory path that was generated from model data.

        :rtype: Path
        """
        return dynamic(
            "audit_path", extras=self.extras
        ) / self.filename_fmt.format(name=self.name, release=self.release)

    def save(self, excluded: Optional[list[str]]) -> Self:
        """Save logging data that receive a context data from a workflow
        execution result.

        :param excluded: An excluded list of key name that want to pass in the
            model_dump method.

        :rtype: Self
        """
        trace: TraceModel = get_trace(
            self.run_id,
            parent_run_id=self.parent_run_id,
            extras=self.extras,
        )

        # NOTE: Check environ variable was set for real writing.
        if not dynamic("enable_write_audit", extras=self.extras):
            trace.debug("[AUDIT]: Skip writing log cause config was set")
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

    @classmethod
    def is_pointed(
        cls,
        name: str,
        release: datetime,
        *,
        extras: Optional[DictData] = None,
    ) -> bool: ...

    @classmethod
    def find_audits(
        cls, name: str, *, extras: Optional[DictData] = None
    ) -> Iterator[Self]: ...

    @classmethod
    def find_audit_with_release(
        cls,
        name: str,
        release: Optional[datetime] = None,
        *,
        extras: Optional[DictData] = None,
    ) -> Self: ...

    def save(self, excluded: Optional[list[str]]) -> SQLiteAudit:
        """Save logging data that receive a context data from a workflow
        execution result.
        """
        trace: TraceModel = get_trace(
            self.run_id,
            parent_run_id=self.parent_run_id,
            extras=self.extras,
        )

        # NOTE: Check environ variable was set for real writing.
        if not dynamic("enable_write_audit", extras=self.extras):
            trace.debug("[AUDIT]: Skip writing log cause config was set")
            return self

        raise NotImplementedError("SQLiteAudit does not implement yet.")


Audit = TypeVar("Audit", bound=BaseAudit)
AuditModel = Union[
    FileAudit,
    SQLiteAudit,
]


def get_audit(
    extras: Optional[DictData] = None,
) -> type[AuditModel]:  # pragma: no cov
    """Get an audit class that dynamic base on the config audit path value.

    :param extras: An extra parameter that want to override the core config.

    :rtype: type[Audit]
    """
    if dynamic("audit_path", extras=extras).is_file():
        return SQLiteAudit
    return FileAudit
