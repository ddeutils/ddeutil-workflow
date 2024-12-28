# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field
from pydantic.functional_serializers import field_serializer
from pydantic.functional_validators import field_validator, model_validator
from typing_extensions import Self

from .__cron import WEEKDAYS, CronJob, CronJobYear, CronRunner
from .__types import DictData, DictStr, TupleStr
from .conf import Loader

__all__: TupleStr = (
    "On",
    "YearOn",
    "interval2crontab",
)


def interval2crontab(
    interval: Literal["daily", "weekly", "monthly"],
    day: str | None = None,
    time: str = "00:00",
) -> str:
    """Return the crontab string that was generated from specific values.

    :param interval: A interval value that is one of 'daily', 'weekly', or
        'monthly'.
    :param day: A day value that will be day of week. The default value is
        monday if it be weekly interval.
    :param time: A time value that passing with format '%H:%M'.

    Examples:
        >>> interval2crontab(interval='daily', time='01:30')
        '1 30 * * *'
        >>> interval2crontab(interval='weekly', day='friday', time='18:30')
        '18 30 * * 5'
        >>> interval2crontab(interval='monthly', time='00:00')
        '0 0 1 * *'
        >>> interval2crontab(interval='monthly', day='tuesday', time='12:00')
        '12 0 1 * 2'
    """
    d: str = "*"
    if interval == "weekly":
        d = WEEKDAYS[(day or "monday")[:3].title()]
    elif interval == "monthly" and day:
        d = WEEKDAYS[day[:3].title()]

    h, m = tuple(
        i.lstrip("0") if i != "00" else "0" for i in time.split(":", maxsplit=1)
    )
    return f"{h} {m} {'1' if interval == 'monthly' else '*'} * {d}"


class On(BaseModel):
    """On Model (Schedule)

    See Also:
        * ``generate()`` is the main usecase of this schedule object.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # NOTE: This is fields of the base schedule.
    cronjob: Annotated[
        CronJob,
        Field(description="Cron job of this schedule"),
    ]
    tz: Annotated[
        str,
        Field(
            description="A timezone string value",
            alias="timezone",
        ),
    ] = "Etc/UTC"
    extras: Annotated[
        DictData,
        Field(
            default_factory=dict,
            description="An extras mapping parameters",
        ),
    ]

    @classmethod
    def from_value(cls, value: DictStr, externals: DictData) -> Self:
        """Constructor from values that will generate crontab by function.

        :param value: A mapping value that will generate crontab before create
            schedule model.
        :param externals: A extras external parameter that will keep in extras.
        """
        passing: DictStr = {}
        if "timezone" in value:
            passing["tz"] = value.pop("timezone")
        passing["cronjob"] = interval2crontab(
            **{v: value[v] for v in value if v in ("interval", "day", "time")}
        )
        return cls(extras=externals | passing.pop("extras", {}), **passing)

    @classmethod
    def from_loader(
        cls,
        name: str,
        externals: DictData | None = None,
    ) -> Self:
        """Constructor from the name of config that will use loader object for
        getting the data.

        :param name: A name of config that will getting from loader.
        :param externals: A extras external parameter that will keep in extras.
        """
        externals: DictData = externals or {}
        loader: Loader = Loader(name, externals=externals)

        # NOTE: Validate the config type match with current connection model
        if loader.type != cls:
            raise ValueError(f"Type {loader.type} does not match with {cls}")

        loader_data: DictData = loader.data
        if "interval" in loader_data:
            return cls.model_validate(
                obj=dict(
                    cronjob=interval2crontab(
                        **{
                            v: loader_data[v]
                            for v in loader_data
                            if v in ("interval", "day", "time")
                        }
                    ),
                    extras=externals | loader_data.pop("extras", {}),
                    **loader_data,
                )
            )
        if "cronjob" not in loader_data:
            raise ValueError(
                "Config does not set ``cronjob`` or ``interval`` keys"
            )
        return cls.model_validate(
            obj=dict(
                cronjob=loader_data.pop("cronjob"),
                extras=externals | loader_data.pop("extras", {}),
                **loader_data,
            )
        )

    @model_validator(mode="before")
    def __prepare_values(cls, values: DictData) -> DictData:
        if tz := values.pop("tz", None):
            values["timezone"] = tz
        return values

    @field_validator("tz")
    def __validate_tz(cls, value: str) -> str:
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

    @field_serializer("cronjob")
    def __serialize_cronjob(self, value: CronJob) -> str:
        return str(value)

    def generate(self, start: str | datetime) -> CronRunner:
        """Return Cron runner object."""
        if isinstance(start, str):
            start: datetime = datetime.fromisoformat(start)
        elif not isinstance(start, datetime):
            raise TypeError("start value should be str or datetime type.")
        return self.cronjob.schedule(date=start, tz=self.tz)

    def next(self, start: str | datetime) -> CronRunner:
        """Return a next datetime from Cron runner object that start with any
        date that given from input.
        """
        runner: CronRunner = self.generate(start=start)

        # NOTE: ship the next date of runner object that create from start.
        _ = runner.next

        return runner


class YearOn(On):
    """Implement On Year Schedule Model for limit year matrix that use by some
    data schedule tools like AWS Glue.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # NOTE: This is fields of the base schedule.
    cronjob: Annotated[
        CronJobYear,
        Field(description="Cron job of this schedule"),
    ]

    @field_validator("cronjob", mode="before")
    def __prepare_cronjob(cls, value: str | CronJobYear) -> CronJobYear:
        """Prepare crontab value that able to receive with string type."""
        return CronJobYear(value) if isinstance(value, str) else value
