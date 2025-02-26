# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""A Logs module contain a TraceLog dataclass.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime
from inspect import Traceback, currentframe, getframeinfo
from pathlib import Path
from threading import get_ident
from typing import Optional, Union

from pydantic.dataclasses import dataclass

from .__types import DictStr, TupleStr
from .conf import config, get_logger
from .utils import cut_id, get_dt_now

logger = get_logger("ddeutil.workflow")

__all__: TupleStr = (
    "FileTraceLog",
    "TraceLog",
    "get_dt_tznow",
    "get_trace",
    "get_trace_obj",
)


def get_dt_tznow() -> datetime:  # pragma: no cov
    """Return the current datetime object that passing the config timezone.

    :rtype: datetime
    """
    return get_dt_now(tz=config.tz)


@dataclass(frozen=True)
class BaseTraceLog(ABC):  # pragma: no cov
    """Base Trace Log dataclass object."""

    run_id: str
    parent_run_id: Optional[str] = None

    @abstractmethod
    def writer(self, message: str, is_err: bool = False) -> None:
        raise NotImplementedError(
            "Create writer logic for this trace object before using."
        )

    @abstractmethod
    def make_message(self, message: str) -> str:
        raise NotImplementedError(
            "Adjust make message method for this trace object before using."
        )

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

    def exception(self, message: str):
        msg: str = self.make_message(message)
        self.writer(msg, is_err=True)
        logger.exception(msg, stacklevel=2)


class FileTraceLog(BaseTraceLog):  # pragma: no cov
    """Trace Log object that write file to the local storage."""

    @classmethod
    def find_logs(cls) -> Iterator[DictStr]:  # pragma: no cov
        for file in config.log_path.glob("./run_id=*"):
            yield cls.__read_std(file)

    @classmethod
    def find_log_with_id(cls, run_id: str, force_raise: bool = True) -> DictStr:
        file: Path = config.log_path / f"run_id={run_id}"
        if file.exists():
            return cls.__read_std(file)
        elif force_raise:
            raise FileNotFoundError(
                f"Trace log on path 'run_id={run_id}' does not found."
            )
        return {}

    @classmethod
    def __read_std(cls, file: Path) -> DictStr:
        data: DictStr = {}

        if (file / "stdout.txt").exists():
            data["stdout"] = (file / "stdout.txt").read_text(encoding="utf-8")

        if (file / "stderr.txt").exists():
            data["stdout"] = (file / "stdout.txt").read_text(encoding="utf-8")

        return data

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
        with (self.pointer / write_file).open(mode="at", encoding="utf-8") as f:
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

    @classmethod
    def find_logs(cls) -> Iterator[DictStr]: ...

    @classmethod
    def find_log_with_id(cls, run_id: str) -> DictStr: ...

    def make_message(self, message: str) -> str: ...

    def writer(self, message: str, is_err: bool = False) -> None: ...


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
