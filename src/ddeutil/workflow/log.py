# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from datetime import datetime
from heapq import heappop, heappush
from pathlib import Path
from typing import Optional, Union

from ddeutil.core import str2bool
from pydantic import BaseModel, Field
from pydantic.functional_validators import model_validator

from .__types import DictData
from .utils import config


class BaseLog(BaseModel, ABC):
    """Base Log Pydantic Model"""

    name: str = Field(description="A pipeline name.")
    on: str = Field(description="A cronjob string of this piepline schedule.")
    release: datetime = Field(description="A release datetime.")
    context: DictData = Field(
        default_factory=dict,
        description=(
            "A context data that receive from a pipeline execution result.",
        ),
    )
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
        return

    @abstractmethod
    def save(self) -> None:
        """Save logging"""
        raise NotImplementedError("Log should implement ``save`` method.")


class FileLog(BaseLog):
    """File Log Pydantic Model that use to saving log data from result of
    pipeline execution. It inherit from BaseLog model that implement the
    ``self.save`` method for file.
    """

    def do_before(self) -> None:
        """Create directory of release before saving log file."""
        self.pointer().mkdir(parents=True, exist_ok=True)

    @classmethod
    def latest_point(
        cls,
        name: str,
        *,
        queue: list[datetime] | None = None,
    ) -> datetime | None:
        """Return latest point that exist in current logging pointer keeping.

        :param name: A pipeline name
        :param queue: A release queue.
        """
        keeping: Path = config().engine.paths.root / f"./logs/pipeline={name}/"
        if not keeping.exists():
            return None

        keeping_files: list[int] = [
            int(found.stem)
            for found in keeping.glob("*")
            if found.is_dir() and re.match(r"\d{14}", found.stem)
        ]

        latest = max(keeping_files or [None])

        if not queue:
            if latest is None:
                return None
            return datetime.strptime(str(latest), "%Y%m%d%H%M%S")

        latest_queue: datetime = max(queue)

        if latest is None:
            return latest_queue

        latest_dt: datetime = datetime.strptime(
            str(latest), "%Y%m%d%H%M%S"
        ).replace(tzinfo=latest_queue.tzinfo)
        return max(latest_dt, latest_queue)

    @classmethod
    def is_pointed(
        cls,
        name: str,
        release: datetime,
        *,
        queue: list[datetime] | None = None,
    ) -> bool:
        """Check this log already point.

        :param name: A pipeline name.
        :param release: A release datetime.
        :param queue: A list of queue of datetime that already run in the
            future.
        """
        if not str2bool(os.getenv("WORKFLOW_LOG_ENABLE_WRITE", "false")):
            return False

        # NOTE: create pointer path that use the same logic of pointer method.
        pointer: Path = (
            config().engine.paths.root
            / f"./logs/pipeline={name}/release={release:%Y%m%d%H%M%S}"
        )

        if queue is None:
            return pointer.exists()

        if pointer.exists() and not queue:
            return True

        if queue:
            latest: datetime = heappop(queue)
            heappush(queue, latest)
            if release == latest:
                return True

        return False

    def pointer(self) -> Path:
        """Return release directory path that was generated from model data."""
        return (
            config().engine.paths.root
            / f"./logs/pipeline={self.name}/release={self.release:%Y%m%d%H%M%S}"
        )

    def save(self) -> None:
        """Save logging data that receive a context data from a pipeline
        execution result.
        """
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
