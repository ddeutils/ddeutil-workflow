# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from datetime import datetime
from typing import (
    Any,
    Optional,
)
from zoneinfo import ZoneInfo

from typing_extensions import Self

from .__schedule import CronJob, CronRunner
from .exceptions import ScheduleArgumentError


class BaseSchedule:
    timezone: str = "UTC"

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> Self:
        if (_cron := data.pop("cron", None)) is None:
            raise ScheduleArgumentError(
                "cron", "this necessary key does not exists in data."
            )
        return cls(cron=_cron, props=data)

    def __init__(
        self,
        cron: str,
        *,
        props: Optional[dict[str, Any]] = None,
    ) -> None:
        self.cron: CronJob = CronJob(value=cron)
        self.props = props or {}

    def schedule(self, start: str) -> CronRunner:
        """Return Cron runner object."""
        _datetime: datetime = datetime.fromisoformat(start).astimezone(
            ZoneInfo(self.timezone)
        )
        return self.cron.schedule(start_date=_datetime)


class BKKSchedule(BaseSchedule):
    timezone: str = "Asia/Bangkok"


class AWSSchedule(BaseSchedule): ...
