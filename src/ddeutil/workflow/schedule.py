# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ddeutil.io import Params
from ddeutil.workflow.vendors.__schedule import CronJob, CronRunner
from pydantic import BaseModel, ConfigDict, Field
from pydantic.functional_validators import field_validator
from typing_extensions import Self

from .__types import DictData
from .loader import SimLoad


class BaseScdl(BaseModel):
    """Base Scdl (Schedule) Model"""

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
        params: Params,
        externals: DictData,
    ) -> Self:
        loader: SimLoad = SimLoad(name, params=params, externals=externals)
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


class Scdl(BaseScdl):
    """Scdl (Schedule) Model.

    See Also:
        * ``generate()`` is the main usecase of this schedule object.
    """


class ScdlBkk(Scdl):
    """Asia Bangkok Scdl (Schedule) timezone Model.

    This model use for change timezone from utc to Asia/Bangkok
    """

    tz: Annotated[str, Field(description="Timezone")] = "Asia/Bangkok"


class AwsScdl(BaseScdl):
    """Implement Schedule for AWS Service."""
