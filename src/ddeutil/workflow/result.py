# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""A Result module. It is the data context transfer objects that use by all
object in this package. This module provide Status enum object and Result
dataclass.
"""
from __future__ import annotations

from dataclasses import field
from datetime import datetime
from enum import IntEnum
from typing import Optional, Union

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass
from pydantic.functional_validators import model_validator
from typing_extensions import Self

from .__types import DictData
from .conf import dynamic
from .errors import ResultError
from .logs import TraceModel, get_dt_tznow, get_trace
from .utils import default_gen_id, gen_id, get_dt_now


class Status(IntEnum):
    """Status Int Enum object that use for tracking execution status to the
    Result dataclass object.
    """

    SUCCESS = 0
    FAILED = 1
    WAIT = 2
    SKIP = 3
    CANCEL = 4

    @property
    def emoji(self) -> str:  # pragma: no cov
        """Return the emoji value of this status.

        :rtype: str
        """
        return {0: "✅", 1: "❌", 2: "🟡", 3: "⏩", 4: "🚫"}[self.value]

    # TODO: Remove this line before release.
    def __repr__(self) -> str:
        return self.name


SUCCESS = Status.SUCCESS
FAILED = Status.FAILED
WAIT = Status.WAIT
SKIP = Status.SKIP
CANCEL = Status.CANCEL


def validate_statuses(statuses: list[Status]) -> Status:
    """Validate the final status from list of Status object.

    :param statuses: (list[Status]) A list of status that want to validate the
        final status.

    :rtype: Status
    """
    if any(s == FAILED for s in statuses):
        return FAILED
    for status in (SUCCESS, SKIP, WAIT, CANCEL):
        if all(s == status for s in statuses):
            return status
    return FAILED


def default_context() -> DictData:
    return {"status": WAIT}


@dataclass(
    config=ConfigDict(arbitrary_types_allowed=True, use_enum_values=True),
)
class Result:
    """Result Pydantic Model for passing and receiving data context from any
    module execution process like stage execution, job execution, or workflow
    execution.

        For comparison property, this result will use ``status``, ``context``,
    and ``_run_id`` fields to comparing with other result instance.

    Warning:
        I use dataclass object instead of Pydantic model object because context
    field that keep dict value change its ID when update new value to it.
    """

    status: Status = field(default=WAIT)
    context: DictData = field(default_factory=default_context)
    run_id: Optional[str] = field(default_factory=default_gen_id)
    parent_run_id: Optional[str] = field(default=None, compare=False)
    ts: datetime = field(default_factory=get_dt_tznow, compare=False)

    trace: Optional[TraceModel] = field(default=None, compare=False, repr=False)
    extras: DictData = field(default_factory=dict, compare=False, repr=False)

    @classmethod
    def construct_with_rs_or_id(
        cls,
        result: Optional[Result] = None,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        id_logic: Optional[str] = None,
        *,
        extras: DictData | None = None,
    ) -> Self:
        """Create the Result object or set parent running id if passing Result
        object.

        :param result: A Result instance.
        :param run_id: A running ID.
        :param parent_run_id: A parent running ID.
        :param id_logic: A logic function that use to generate a running ID.
        :param extras: An extra parameter that want to override the core config.

        :rtype: Self
        """
        if result is None:
            return cls(
                run_id=(run_id or gen_id(id_logic or "", unique=True)),
                parent_run_id=parent_run_id,
                ts=get_dt_now(dynamic("tz", extras=extras)),
                extras=(extras or {}),
            )
        elif parent_run_id:
            result.set_parent_run_id(parent_run_id)

        if extras is not None:
            result.extras.update(extras)

        return result

    @model_validator(mode="after")
    def __prepare_trace(self) -> Self:
        """Prepare trace field that want to pass after its initialize step.

        :rtype: Self
        """
        if self.trace is None:  # pragma: no cov
            self.trace: TraceModel = get_trace(
                self.run_id,
                parent_run_id=self.parent_run_id,
                extras=self.extras,
            )
        return self

    def set_parent_run_id(self, running_id: str) -> Self:
        """Set a parent running ID.

        :param running_id: (str) A running ID that want to update on this model.

        :rtype: Self
        """
        self.parent_run_id: str = running_id
        self.trace: TraceModel = get_trace(
            self.run_id, parent_run_id=running_id, extras=self.extras
        )
        return self

    def catch(
        self,
        status: Union[int, Status],
        context: DictData | None = None,
        **kwargs,
    ) -> Self:
        """Catch the status and context to this Result object. This method will
        use between a child execution return a result, and it wants to pass
        status and context to this object.

        :param status: A status enum object.
        :param context: A context data that will update to the current context.

        :rtype: Self
        """
        self.__dict__["status"] = (
            Status(status) if isinstance(status, int) else status
        )
        self.__dict__["context"].update(context or {})
        self.__dict__["context"]["status"] = self.status
        if kwargs:
            for k in kwargs:
                if k in self.__dict__["context"]:
                    self.__dict__["context"][k].update(kwargs[k])
                # NOTE: Exclude the `info` key for update information data.
                elif k == "info":
                    self.__dict__["context"][k].update(kwargs[k])
                else:
                    raise ResultError(
                        f"The key {k!r} does not exists on context data."
                    )
        return self

    def alive_time(self) -> float:  # pragma: no cov
        """Return total seconds that this object use since it was created.

        :rtype: float
        """
        return (
            get_dt_now(tz=dynamic("tz", extras=self.extras)) - self.ts
        ).total_seconds()
