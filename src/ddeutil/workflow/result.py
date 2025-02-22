# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from dataclasses import field
from enum import IntEnum
from threading import Event
from typing import Optional

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass
from typing_extensions import Self

from .__types import DictData, TupleStr
from .conf import get_logger
from .utils import cut_id, gen_id

logger = get_logger("ddeutil.workflow.audit")

__all__: TupleStr = (
    "Result",
    "Status",
)


def default_gen_id() -> str:
    """Return running ID which use for making default ID for the Result model if
    a run_id field initializes at the first time.

    :rtype: str
    """
    return gen_id("manual", unique=True)


class Status(IntEnum):
    SUCCESS: int = 0
    FAILED: int = 1
    WAIT: int = 2


class TraceLog:  # pragma: no cov
    """Trace Log object."""

    __slots__: TupleStr = ("run_id",)

    def __init__(self, run_id: str):
        self.run_id: str = run_id

    def debug(self, message: str):
        logger.debug(f"({cut_id(self.run_id)}) {message}")

    def info(self, message: str):
        logger.info(f"({cut_id(self.run_id)}) {message}")

    def warning(self, message: str):
        logger.warning(f"({cut_id(self.run_id)}) {message}")

    def error(self, message: str):
        logger.error(f"({cut_id(self.run_id)}) {message}")


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

    def set_run_id(self, running_id: str) -> Self:
        """Set a running ID.

        :param running_id: A running ID that want to update on this model.
        :rtype: Self
        """
        self.run_id: str = running_id
        return self

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

    def receive(self, result: Result) -> Self:
        """Receive context from another result object.

        :rtype: Self
        """
        self.__dict__["status"] = result.status
        self.__dict__["context"].update(result.context)

        # NOTE: Update running ID from an incoming result.
        self.parent_run_id = result.parent_run_id
        self.run_id = result.run_id
        return self

    @property
    def trace(self) -> TraceLog:
        """Return TraceLog object that passing its running ID.

        :rtype: TraceLog
        """
        return TraceLog(self.run_id)
