# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""This is the Result module. It is the data context transfer objects that use
by all object in this package. This module provide TraceLog dataclasses and
Result dataclass.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import field
from datetime import datetime
from enum import IntEnum
from inspect import Traceback, currentframe, getframeinfo
from pathlib import Path
from threading import Event, get_ident
from typing import Optional, Union

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass
from typing_extensions import Self

from .__types import DictData, TupleStr
from .conf import config, get_logger
from .utils import cut_id, gen_id, get_dt_now

logger = get_logger("ddeutil.workflow")

__all__: TupleStr = (
    "Result",
    "Status",
    "FileTraceLog",
    "default_gen_id",
    "get_dt_tznow",
)


def default_gen_id() -> str:
    """Return running ID which use for making default ID for the Result model if
    a run_id field initializes at the first time.

    :rtype: str
    """
    return gen_id("manual", unique=True)


def get_dt_tznow() -> datetime:
    """Return the current datetime object that passing the config timezone.

    :rtype: datetime
    """
    return get_dt_now(tz=config.tz)


class Status(IntEnum):
    """Status Int Enum object."""

    SUCCESS: int = 0
    FAILED: int = 1
    WAIT: int = 2


@dataclass(frozen=True)
class BaseTraceLog(ABC):  # pragma: no cov
    """Base Trace Log dataclass object."""

    run_id: str
    parent_run_id: Optional[str] = None

    @abstractmethod
    def writer(self, message: str, is_err: bool = False) -> None: ...

    @abstractmethod
    def make_message(self, message: str) -> str: ...

    def debug(self, message: str):
        msg: str = self.make_message(message)

        # NOTE: Write file if debug mode.
        if config.debug:
            self.writer(msg)

        logger.debug(msg, stacklevel=2)

    def info(self, message: str):
        msg: str = self.make_message(message)
        self.writer(msg)
        logger.info(msg, stacklevel=2)

    def warning(self, message: str):
        msg: str = self.make_message(message)
        self.writer(msg)
        logger.warning(msg, stacklevel=2)

    def error(self, message: str):
        msg: str = self.make_message(message)
        self.writer(msg, is_err=True)
        logger.error(msg, stacklevel=2)


class FileTraceLog(BaseTraceLog):  # pragma: no cov
    """Trace Log object that write file to the local storage."""

    @property
    def log_file(self) -> Path:
        log_file: Path = (
            config.log_path / f"run_id={self.parent_run_id or self.run_id}"
        )
        if not log_file.exists():
            log_file.mkdir(parents=True)
        return log_file

    @property
    def cut_id(self) -> str:
        """Combine cutting ID of parent running ID if it set."""
        cut_run_id: str = cut_id(self.run_id)
        if not self.parent_run_id:
            return f"{cut_run_id} -> {' ' * 6}"

        cut_parent_run_id: str = cut_id(self.parent_run_id)
        return f"{cut_parent_run_id} -> {cut_run_id}"

    def make_message(self, message: str) -> str:
        return f"({self.cut_id}) {message}"

    def writer(self, message: str, is_err: bool = False) -> None:
        """The path of logging data will store by format:

            ... ./logs/run_id=<run-id>/stdout.txt
            ... ./logs/run_id=<run-id>/stderr.txt

        :param message:
        :param is_err:
        """
        if not config.enable_write_log:
            return

        frame_info: Traceback = getframeinfo(currentframe().f_back.f_back)
        filename: str = frame_info.filename.split(os.path.sep)[-1]
        lineno: int = frame_info.lineno

        # NOTE: set process and thread IDs.
        process: int = os.getpid()
        thread: int = get_ident()

        write_file: str = "stderr.txt" if is_err else "stdout.txt"
        with (self.log_file / write_file).open(
            mode="at", encoding="utf-8"
        ) as f:
            msg_fmt: str = f"{config.log_format_file}\n"
            print(msg_fmt)
            f.write(
                msg_fmt.format(
                    **{
                        "datetime": get_dt_tznow().strftime(
                            config.log_datetime_format
                        ),
                        "process": process,
                        "thread": thread,
                        "message": message,
                        "filename": filename,
                        "lineno": lineno,
                    }
                )
            )


class SQLiteTraceLog(BaseTraceLog):  # pragma: no cov

    def make_message(self, message: str) -> str: ...

    def writer(self, message: str, is_err: bool = False) -> None: ...


TraceLog = Union[
    FileTraceLog,
    SQLiteTraceLog,
]


def get_trace() -> type[BaseTraceLog]:  # pragma: no cov
    if config.log_path.is_file():
        return SQLiteTraceLog
    return FileTraceLog


@dataclass(
    config=ConfigDict(arbitrary_types_allowed=True, use_enum_values=True)
)
class Result:
    """Result Pydantic Model for passing and receiving data context from any
    module execution process like stage execution, job execution, or workflow
    execution.

        For comparison property, this result will use ``status``, ``context``,
    and ``_run_id`` fields to comparing with other result instance.
    """

    status: Status = field(default=Status.WAIT)
    context: DictData = field(default_factory=dict)
    run_id: Optional[str] = field(default_factory=default_gen_id)

    # NOTE: Ignore this field to compare another result model with __eq__.
    parent_run_id: Optional[str] = field(default=None, compare=False)
    event: Event = field(default_factory=Event, compare=False)
    ts: datetime = field(default_factory=get_dt_tznow, compare=False)

    @classmethod
    def construct_with_rs_or_id(
        cls,
        result: Result | None = None,
        run_id: str | None = None,
        parent_run_id: str | None = None,
        id_logic: str | None = None,
    ) -> Self:  # pragma: no cov
        """Create the Result object or set parent running id if passing Result
        object.
        """
        if result is None:
            result: Result = cls(
                run_id=(run_id or gen_id(id_logic or "", unique=True)),
                parent_run_id=parent_run_id,
            )
        elif parent_run_id:
            result.set_parent_run_id(parent_run_id)
        return result

    def set_parent_run_id(self, running_id: str) -> Self:
        """Set a parent running ID.

        :param running_id: A running ID that want to update on this model.
        :rtype: Self
        """
        self.parent_run_id: str = running_id
        return self

    def catch(
        self,
        status: int | Status,
        context: DictData | None = None,
    ) -> Self:
        """Catch the status and context to this Result object. This method will
        use between a child execution return a result, and it wants to pass
        status and context to this object.

        :param status:
        :param context:
        """
        self.__dict__["status"] = (
            Status(status) if isinstance(status, int) else status
        )
        self.__dict__["context"].update(context or {})
        return self

    @property
    def trace(self) -> FileTraceLog:
        """Return FileTraceLog object that passing its running ID.

        :rtype: FileTraceLog
        """
        return FileTraceLog(self.run_id, self.parent_run_id)

    def alive_time(self) -> float:  # pragma: no cov
        return (get_dt_tznow() - self.ts).total_seconds()
