# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""This is the Result module. It is the data context transfer objects that use
by all object in this package. This module provide Result dataclass.
"""
from __future__ import annotations

from dataclasses import field
from datetime import datetime
from enum import IntEnum
from threading import Event
from typing import Optional

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass
from pydantic.functional_validators import model_validator
from typing_extensions import Self

from .__types import DictData, TupleStr
from .logs import TraceLog, get_dt_tznow, get_trace
from .utils import default_gen_id, gen_id

__all__: TupleStr = (
    "Result",
    "Status",
)


class Status(IntEnum):
    """Status Int Enum object."""

    SUCCESS: int = 0
    FAILED: int = 1
    WAIT: int = 2


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
    parent_run_id: Optional[str] = field(default=None, compare=False)
    ts: datetime = field(default_factory=get_dt_tznow, compare=False)

    event: Event = field(default_factory=Event, compare=False, repr=False)
    trace: Optional[TraceLog] = field(default=None, compare=False, repr=False)

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

    @model_validator(mode="after")
    def __prepare_trace(self) -> Self:
        """Prepare trace field that want to pass after its initialize step."""
        if self.trace is None:  # pragma: no cov
            self.trace: TraceLog = get_trace(self.run_id, self.parent_run_id)

        return self

    def set_parent_run_id(self, running_id: str) -> Self:
        """Set a parent running ID.

        :param running_id: A running ID that want to update on this model.
        :rtype: Self
        """
        self.parent_run_id: str = running_id
        self.trace: TraceLog = get_trace(self.run_id, running_id)
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

    def alive_time(self) -> float:  # pragma: no cov
        """Return total seconds that this object use since it was created.

        :rtype: float
        """
        return (get_dt_tznow() - self.ts).total_seconds()
