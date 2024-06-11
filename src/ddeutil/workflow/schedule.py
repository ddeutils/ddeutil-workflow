# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ddeutil.workflow.vendors.__schedule import CronJob, CronRunner
from pydantic import BaseModel, ConfigDict, Field
from pydantic.functional_validators import field_validator
from typing_extensions import Self

from .__types import DictData
from .loader import Loader
from .vendors.__schedule import WEEKDAYS


def crontab_convert(
    interval: Literal["daily", "weekly", "monthly"],
    day: str = "monday",
    time: str = "00:00",
) -> str:
    if interval == "weekly" and day is None:
        raise ValueError("Weekly interval should pass day for fix it")
    h, m = time.split(":", maxsplit=1)
    return (
        f"{h.lstrip('0')} {m.lstrip('0')} " f"* * {WEEKDAYS[day[:3].title()]}"
    )


class BaseSchedule(BaseModel):
    """Base Schedule (Schedule) Model"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # NOTE: This is fields
    cronjob: Annotated[CronJob, Field(description="Cron job of this schedule")]
    tz: Annotated[str, Field(description="Timezone")] = "utc"
    extras: Annotated[
        DictData,
        Field(default_factory=dict, description="Extras mapping of parameters"),
    ]

    @classmethod
    def from_loader(
        cls,
        name: str,
        externals: DictData,
    ) -> Self:
        loader: Loader = Loader(name, externals=externals)
        if "cronjob" not in loader.data:
            raise ValueError("Config does not set ``cronjob`` value")
        return cls(cronjob=loader.data["cronjob"], extras=externals)

    @field_validator("tz")
    def __validate_tz(cls, value: str):
        try:
            _ = ZoneInfo(value)
            return value
        except ZoneInfoNotFoundError as err:
            raise ValueError(f"Invalid timezone: {value}") from err

    @field_validator("cronjob", mode="before")
    def __prepare_cronjob(cls, value: str | CronJob) -> CronJob:
        return CronJob(value) if isinstance(value, str) else value

    def generate(self, start: str | datetime) -> CronRunner:
        """Return Cron runner object."""
        if not isinstance(start, datetime):
            start: datetime = datetime.fromisoformat(start)
        return self.cronjob.schedule(date=(start.astimezone(ZoneInfo(self.tz))))


class Schedule(BaseSchedule):
    """Schedule (Schedule) Model.

    See Also:
        * ``generate()`` is the main usecase of this schedule object.
    """


class ScheduleBkk(Schedule):
    """Asia Bangkok Schedule (Schedule) timezone Model.

    This model use for change timezone from utc to Asia/Bangkok
    """

    tz: Annotated[str, Field(description="Timezone")] = "Asia/Bangkok"


class AwsSchedule(BaseSchedule):
    """Implement Schedule for AWS Service."""
