# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from ddeutil.io import Params
from pydantic import BaseModel, ConfigDict, Field
from pydantic.functional_validators import field_validator
from typing_extensions import Self

from .__schedule import CronJob, CronRunner
from .__types import DictData
from .exceptions import ScdlArgumentError
from .loader import SimLoad


class BaseScdl(BaseModel):
    """Base Scdl (Schedule) Model"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # NOTE: This is fields
    cronjob: Annotated[CronJob, Field(description="Cron job of this schedule")]
    tz: Annotated[str, Field(description="Timezone")] = "UTC"
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
        if "cron" not in loader.data:
            raise ScdlArgumentError("cron", "Config does not set ``cron``")
        return cls(cron=loader.data["cron"], extras=externals)

    @field_validator("cronjob", mode="before")
    def __prepare_cronjob(cls, value: str | CronJob) -> CronJob:
        return CronJob(value) if isinstance(value, str) else value

    def generate(self, start: str) -> CronRunner:
        """Return Cron runner object."""
        return self.cronjob.schedule(
            start_date=(
                datetime.fromisoformat(start).astimezone(ZoneInfo(self.tz))
            )
        )


class Scdl(BaseScdl):
    """Scdl (Schedule) Model"""


class BkkScdl(BaseScdl):
    """Asia Bangkok Scdl (Schedule) timezone Model"""

    tz: str = "Asia/Bangkok"


class AwsScdl(BaseScdl):
    """Implement Schedule for AWS Service."""
