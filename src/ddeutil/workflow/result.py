# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from dataclasses import field
from typing import Optional

from pydantic.dataclasses import dataclass
from pydantic.functional_validators import model_validator
from typing_extensions import Self

from .__types import DictData, TupleStr
from .utils import gen_id

__all__: TupleStr = ("Result",)


@dataclass
class Result:
    """Result Pydantic Model for passing and receiving data context from any
    module execution process like stage execution, job execution, or workflow
    execution.

        For comparison property, this result will use ``status``, ``context``,
    and ``_run_id`` fields to comparing with other result instance.
    """

    status: int = field(default=2)
    context: DictData = field(default_factory=dict)
    run_id: Optional[str] = field(default=None)

    # NOTE: Ignore this field to compare another result model with __eq__.
    parent_run_id: Optional[str] = field(default=None, compare=False)

    @model_validator(mode="after")
    def __prepare_run_id(self) -> Self:
        """Prepare running ID which use default ID if it initializes at the
        first time.

        :rtype: Self
        """
        self._run_id = gen_id("manual", unique=True)
        return self

    def set_run_id(self, running_id: str) -> Self:
        """Set a running ID.

        :param running_id: A running ID that want to update on this model.
        :rtype: Self
        """
        self.run_id = running_id
        return self

    def set_parent_run_id(self, running_id: str) -> Self:
        """Set a parent running ID.

        :param running_id: A running ID that want to update on this model.
        :rtype: Self
        """
        self.parent_run_id: str = running_id
        return self

    def catch(self, status: int, context: DictData) -> Self:
        """Catch the status and context to current data."""
        self.__dict__["status"] = status
        self.__dict__["context"].update(context)
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

    def receive_jobs(self, result: Result) -> Self:
        """Receive context from another result object that use on the workflow
        execution which create a ``jobs`` keys on the context if it does not
        exist.

        :rtype: Self
        """
        self.__dict__["status"] = result.status

        # NOTE: Check the context has jobs key.
        if "jobs" not in self.__dict__["context"]:
            self.__dict__["context"]["jobs"] = {}

        self.__dict__["context"]["jobs"].update(result.context)

        # NOTE: Update running ID from an incoming result.
        self.parent_run_id: str = result.parent_run_id
        self.run_id: str = result.run_id
        return self
