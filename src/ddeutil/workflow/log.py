# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import ClassVar, Optional, Union

from pydantic import BaseModel, Field
from pydantic.functional_validators import model_validator
from typing_extensions import Self

from .__types import DictData
from .conf import config


@lru_cache
def get_logger(name: str):
    """Return logger object with an input module name.

    :param name: A module name that want to log.
    """
    logger = logging.getLogger(name)
    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s.%(msecs)03d (%(name)-10s, %(process)-5d, "
            "%(thread)-5d) [%(levelname)-7s] %(message)-120s "
            "(%(filename)s:%(lineno)s)"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    logger.setLevel(logging.DEBUG if config.debug else logging.INFO)
    return logger


class BaseLog(BaseModel, ABC):
    """Base Log Pydantic Model with abstraction class property that implement
    only model fields. This model should to use with inherit to logging
    sub-class like file, sqlite, etc.
    """

    name: str = Field(description="A workflow name.")
    on: str = Field(description="A cronjob string of this piepline schedule.")
    release: datetime = Field(description="A release datetime.")
    context: DictData = Field(
        default_factory=dict,
        description=(
            "A context data that receive from a workflow execution result.",
        ),
    )
    parent_run_id: Optional[str] = Field(default=None)
    run_id: str
    update: datetime = Field(default_factory=datetime.now)

    @model_validator(mode="after")
    def __model_action(self) -> Self:
        """Do before the Log action with WORKFLOW_LOG_ENABLE_WRITE env variable.

        :rtype: Self
        """
        if config.enable_write_log:
            self.do_before()
        return self

    def do_before(self) -> None:
        """To something before end up of initial log model."""

    @abstractmethod
    def save(self, excluded: list[str] | None) -> None:
        """Save this model logging to target logging store."""
        raise NotImplementedError("Log should implement ``save`` method.")


class FileLog(BaseLog):
    """File Log Pydantic Model that use to saving log data from result of
    workflow execution. It inherit from BaseLog model that implement the
    ``self.save`` method for file.
    """

    filename: ClassVar[str] = (
        "./logs/workflow={name}/release={release:%Y%m%d%H%M%S}"
    )

    def do_before(self) -> None:
        """Create directory of release before saving log file."""
        self.pointer().mkdir(parents=True, exist_ok=True)

    @classmethod
    def find_logs(cls, name: str):
        pointer: Path = config.root_path / f"./logs/workflow={name}"
        for file in pointer.glob("./release=*/*.log"):
            with file.open(mode="r", encoding="utf-8") as f:
                yield json.load(f)

    @classmethod
    def find_log(cls, name: str, release: datetime | None = None):
        if release is not None:
            pointer: Path = (
                config.root_path
                / f"./logs/workflow={name}/release={release:%Y%m%d%H%M%S}"
            )
            if not pointer.exists():
                raise FileNotFoundError(
                    f"Pointer: ./logs/workflow={name}/"
                    f"release={release:%Y%m%d%H%M%S} does not found."
                )
            return cls.model_validate(
                obj=json.loads(pointer.read_text(encoding="utf-8"))
            )
        raise NotImplementedError("Find latest log does not implement yet.")

    @classmethod
    def is_pointed(
        cls,
        name: str,
        release: datetime,
        *,
        queue: list[datetime] | None = None,
    ) -> bool:
        """Check this log already point in the destination.

        :param name: A workflow name.
        :param release: A release datetime.
        :param queue: A list of queue of datetime that already run in the
            future.
        """
        # NOTE: Check environ variable was set for real writing.
        if not config.enable_write_log:
            return False

        # NOTE: create pointer path that use the same logic of pointer method.
        pointer: Path = config.root_path / cls.filename.format(
            name=name, release=release
        )

        if not queue:
            return pointer.exists()
        return pointer.exists() or (release in queue)

    def pointer(self) -> Path:
        """Return release directory path that was generated from model data.

        :rtype: Path
        """
        return config.root_path / self.filename.format(
            name=self.name, release=self.release
        )

    def save(self, excluded: list[str] | None) -> Self:
        """Save logging data that receive a context data from a workflow
        execution result.

        :param excluded: An excluded list of key name that want to pass in the
            model_dump method.
        :rtype: Self
        """
        # NOTE: Check environ variable was set for real writing.
        if not config.enable_write_log:
            return self

        log_file: Path = self.pointer() / f"{self.run_id}.log"
        log_file.write_text(
            json.dumps(
                self.model_dump(exclude=excluded),
                default=str,
                indent=2,
            ),
            encoding="utf-8",
        )
        return self


class SQLiteLog(BaseLog):

    def save(self, excluded: list[str] | None) -> None:
        raise NotImplementedError("SQLiteLog does not implement yet.")


Log = Union[
    FileLog,
    SQLiteLog,
]
