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
from typing import Optional, Union

from pydantic import BaseModel, Field
from pydantic.functional_validators import model_validator
from rich.console import Console
from rich.logging import RichHandler

from .__types import DictData
from .utils import config

console = Console(color_system="256", width=200, style="blue")


@lru_cache
def get_logger(module_name):
    logger = logging.getLogger(module_name)
    handler = RichHandler(
        rich_tracebacks=True, console=console, tracebacks_show_locals=True
    )
    handler.setFormatter(
        logging.Formatter(
            "[ %(threadName)s:%(funcName)s:%(process)d ] - %(message)s"
        )
    )
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    return logger


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
        self.do_before()
        return self

    def do_before(self) -> None:
        """To something before end up of initial log model."""
        ...

    @abstractmethod
    def save(self) -> None:
        """Save logging"""
        raise NotImplementedError("Log should implement ``save`` method.")


class FileLog(BaseLog):
    """Filee Log"""

    def do_before(self) -> None:
        self.pointer().mkdir(parents=True, exist_ok=True)

    @classmethod
    def is_pointed(cls, name: str, release: datetime) -> bool:
        """Check this log already point."""
        return (
            config().engine.paths.root / f"./logs/{name}/{release:%Y%m%d%H%M%S}"
        ).exists()

    def pointer(self) -> Path:
        return (
            config().engine.paths.root
            / f"./logs/{self.name}/{self.release:%Y%m%d%H%M%S}"
        )

    def save(self) -> None:
        """Save logging data"""
        log_file: Path = self.pointer() / f"{self.run_id}.log"
        log_file.write_text(
            json.dumps(
                self.model_dump(),
                default=str,
            ),
            encoding="utf-8",
        )


Log = Union[FileLog,]
