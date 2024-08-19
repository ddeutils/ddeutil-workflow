# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime

# import logging
from heapq import heappop, heappush

# from functools import lru_cache
from pathlib import Path
from typing import Optional, Union

from ddeutil.core import str2bool
from pydantic import BaseModel, Field
from pydantic.functional_validators import model_validator

# from rich.console import Console
# from rich.logging import RichHandler
from .__types import DictData
from .utils import config

# console = Console(color_system="256", width=200, style="blue")
# @lru_cache
# def get_logger(module_name):
#     logger = logging.getLogger(module_name)
#     handler = RichHandler(
#         rich_tracebacks=True, console=console, tracebacks_show_locals=True
#     )
#     handler.setFormatter(
#         logging.Formatter(
#             "[ %(threadName)s:%(funcName)s:%(process)d ] - %(message)s"
#         )
#     )
#     logger.addHandler(handler)
#     logger.setLevel(logging.DEBUG)
#     return logger


class BaseLog(BaseModel, ABC):
    """Base Log Pydantic Model"""

    name: str
    on: str
    release: datetime
    context: DictData
    parent_run_id: Optional[str] = Field(default=None)
    run_id: str
    update: datetime = Field(default_factory=datetime.now)

    @model_validator(mode="after")
    def __model_action(self):
        if str2bool(os.getenv("WORKFLOW_LOG_ENABLE_WRITE", "false")):
            self.do_before()
        return self

    def do_before(self) -> None:
        """To something before end up of initial log model."""

    @abstractmethod
    def save(self) -> None:
        """Save logging"""
        raise NotImplementedError("Log should implement ``save`` method.")


class FileLog(BaseLog):
    """Filee Log"""

    def do_before(self) -> None:
        self.pointer().mkdir(parents=True, exist_ok=True)

    @classmethod
    def is_pointed(
        cls,
        name: str,
        release: datetime,
        *,
        queue: list[datetime] | None = None,
    ) -> bool:
        """Check this log already point."""
        if not str2bool(os.getenv("WORKFLOW_LOG_ENABLE_WRITE", "false")):
            return False

        if queue is None:
            return (
                config().engine.paths.root
                / f"./logs/{name}/{release:%Y%m%d%H%M%S}"
            ).exists()

        if (
            config().engine.paths.root / f"./logs/{name}/{release:%Y%m%d%H%M%S}"
        ).exists() and not queue:
            return True

        if queue:
            latest: datetime = heappop(queue)
            heappush(queue, latest)
            if release == latest:
                return True

        return False

    def pointer(self) -> Path:
        return (
            config().engine.paths.root
            / f"./logs/{self.name}/{self.release:%Y%m%d%H%M%S}"
        )

    def save(self) -> None:
        """Save logging data"""
        if not str2bool(os.getenv("WORKFLOW_LOG_ENABLE_WRITE", "false")):
            return

        log_file: Path = self.pointer() / f"{self.run_id}.log"
        log_file.write_text(
            json.dumps(
                self.model_dump(),
                default=str,
            ),
            encoding="utf-8",
        )


class SQLiteLog(BaseLog):

    def save(self) -> None:
        raise NotImplementedError("SQLiteLog does not implement yet.")


Log = Union[
    FileLog,
    SQLiteLog,
]
