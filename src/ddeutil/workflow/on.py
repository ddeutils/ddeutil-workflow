# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ddeutil.workflow.vendors.scheduler import CronJob, CronRunner
from pydantic import BaseModel, ConfigDict, Field
from pydantic.functional_validators import field_validator
from typing_extensions import Self

try:
    from .__types import DictData
    from .loader import Loader
    from .vendors.__schedule import WEEKDAYS
except ImportError:
    from ddeutil.workflow.__types import DictData
    from ddeutil.workflow.loader import Loader
    from ddeutil.workflow.vendors.scheduler import WEEKDAYS


def crontab_generate(
    interval: Literal["daily", "weekly", "monthly"],
    day: str = "monday",
    time: str = "00:00",
) -> str:
    """Return the crontab string that was generated from specific values.

    :param interval: A interval value that is one of 'daily', 'weekly', or
        'monthly'.
    :param day: A day value that will be day of week.
    :param time: A time value that passing with format '%H:%M'.

    Examples:
        >>> crontab_generate(interval='daily', time='01:30')
        '1 30 * * *'
        >>> crontab_generate(interval='weekly', day='friday', time='18:30')
        '18 30 * * 5'
        >>> crontab_generate(interval='monthly', time='00:00')
        '0 0 1 * *'
    """
    h, m = tuple(
        i.lstrip("0") if i != "00" else "0" for i in time.split(":", maxsplit=1)
    )
    return (
        f"{h} {m} {'1' if interval == 'monthly' else '*'} * "
        f"{WEEKDAYS[day[:3].title()] if interval == 'weekly' else '*'}"
    )


class Schedule(BaseModel):
    """Base Schedule (Schedule) Model

    See Also:
        * ``generate()`` is the main usecase of this schedule object.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # NOTE: This is fields of the base schedule.
    cronjob: Annotated[CronJob, Field(description="Cron job of this schedule")]
    tz: Annotated[str, Field(description="Timezone")] = "Etc/UTC"
    extras: Annotated[
        DictData,
        Field(default_factory=dict, description="Extras mapping of parameters"),
    ]

    @classmethod
    def from_value(
        cls,
        value: dict[str, str],
        externals: DictData,
    ) -> Self:
        """Constructor from values that will generate crontab by function.

        :param value: A mapping value that will generate crontab before create
            schedule model.
        :param externals: A extras external parameter that will keep in extras.
        """
        passing: dict[str, str] = {}
        if "timezone" in value:
            passing["tz"] = value.pop("timezone")
        passing["cronjob"] = crontab_generate(
            **{v: value[v] for v in value if v in ("interval", "day", "time")}
        )
        return cls(extras=externals, **passing)

    @classmethod
    def from_loader(
        cls,
        name: str,
        externals: DictData,
    ) -> Self:
        """Constructor from the name of config that will use loader object for
        getting the data.

        :param name: A name of config that will getting from loader.
        :param externals: A extras external parameter that will keep in extras.
        """
        loader: Loader = Loader(name, externals=externals)
        # NOTE: Validate the config type match with current connection model
        if loader.type != cls:
            raise ValueError(f"Type {loader.type} does not match with {cls}")

        if "interval" in loader.data:
            return cls.from_value(loader.data, externals=externals)
        if "cronjob" not in loader.data:
            raise ValueError("Config does not set ``cronjob`` value")
        if "timezone" in loader.data:
            return cls(
                cronjob=loader.data["cronjob"],
                tz=loader.data["timezone"],
                extras=externals,
            )
        return cls(cronjob=loader.data["cronjob"], extras=externals)

    @field_validator("tz")
    def __validate_tz(cls, value: str):
        """Validate timezone value that able to initialize with ZoneInfo after
        it passing to this model in before mode."""
        try:
            _ = ZoneInfo(value)
            return value
        except ZoneInfoNotFoundError as err:
            raise ValueError(f"Invalid timezone: {value}") from err

    @field_validator("cronjob", mode="before")
    def __prepare_cronjob(cls, value: str | CronJob) -> CronJob:
        """Prepare crontab value that able to receive with string type."""
        return CronJob(value) if isinstance(value, str) else value

    def generate(self, start: str | datetime) -> CronRunner:
        """Return Cron runner object."""
        if not isinstance(start, datetime):
            start: datetime = datetime.fromisoformat(start)
        return self.cronjob.schedule(date=(start.astimezone(ZoneInfo(self.tz))))


class AwsSchedule(Schedule):
    """Implement Schedule for AWS Service."""
