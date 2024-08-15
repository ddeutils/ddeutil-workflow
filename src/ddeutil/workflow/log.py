# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import logging
from datetime import datetime
from functools import lru_cache
from typing import Union

from pydantic import BaseModel, Field
from rich.console import Console
from rich.logging import RichHandler

from .__types import DictData

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


class BaseLog(BaseModel):
    """Base logging model."""

    parent_id: str
    id: str
    input: DictData
    output: DictData
    update_time: datetime = Field(default_factory=datetime.now)


class StageLog(BaseLog): ...


class JobLog(BaseLog): ...


class PipelineLog(BaseLog): ...


Log = Union[
    StageLog,
    JobLog,
    PipelineLog,
]


def push_log_memory(log: DictData):
    """Push message log to globals log queue."""
    print(log)


LOGS_REGISTRY = {
    "memory": push_log_memory,
}


def push_log(log: DictData, mode: str = "memory"):
    return LOGS_REGISTRY[mode](log)


def save_log():
    """Save log that push to queue to target saving"""
