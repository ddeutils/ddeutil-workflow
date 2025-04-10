# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from dataclasses import fields
from datetime import datetime
from typing import Annotated, Literal, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo
from pydantic.functional_serializers import field_serializer
from pydantic.functional_validators import field_validator, model_validator
from typing_extensions import Self

from .__cron import WEEKDAYS, CronJob, CronJobYear, CronRunner, Options
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

    :param interval: An interval value that is one of 'daily', 'weekly', or
        'monthly'.
    :param day: A day value that will be day of week. The default value is
        monday if it is weekly interval.
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

    :rtype: str
    """
    d: str = "*"
    if interval == "weekly":
        d = str(WEEKDAYS[(day or "monday")[:3].title()])
    elif interval == "monthly" and day:
        d = str(WEEKDAYS[day[:3].title()])

    h, m = tuple(
        i.lstrip("0") if i != "00" else "0" for i in time.split(":", maxsplit=1)
    )
    return f"{h} {m} {'1' if interval == 'monthly' else '*'} * {d}"


class On(BaseModel):
    """On Pydantic model (Warped crontab object by model).

    See Also:
        * ``generate()`` is the main use-case of this schedule object.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    extras: Annotated[
        DictData,
        Field(
            default_factory=dict,
            description="An extras mapping parameters.",
        ),
    ]
    cronjob: Annotated[
        CronJob,
        Field(description="A Cronjob object of this schedule."),
    ]
    tz: Annotated[
        str,
        Field(
            description="A timezone string value",
            alias="timezone",
        ),
    ] = "Etc/UTC"

    @classmethod
    def from_value(cls, value: DictStr, extras: DictData) -> Self:
        """Constructor from values that will generate crontab by function.

        :param value: A mapping value that will generate crontab before create
            schedule model.
        :param extras: An extras parameter that will keep in extras.
        """
        passing: DictStr = {}
        if "timezone" in value:
            passing["tz"] = value.pop("timezone")
        passing["cronjob"] = interval2crontab(
            **{v: value[v] for v in value if v in ("interval", "day", "time")}
        )
        return cls(extras=extras | passing.pop("extras", {}), **passing)

    @classmethod
    def from_conf(
        cls,
        name: str,
        extras: DictData | None = None,
    ) -> Self:
        """Constructor from the name of config that will use loader object for
        getting the data.

        :param name: A name of config that will get from loader.
        :param extras: An extra parameter that will keep in extras.
        """
        extras: DictData = extras or {}
        loader: Loader = Loader(name, externals=extras)

        # NOTE: Validate the config type match with current connection model
        if loader.type != cls.__name__:
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
                    extras=extras | loader_data.pop("extras", {}),
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
                extras=extras | loader_data.pop("extras", {}),
                **loader_data,
            )
        )

    @model_validator(mode="before")
    def __prepare_values(cls, values: DictData) -> DictData:
        """Extract tz key from value and change name to timezone key."""
        if tz := values.pop("tz", None):
            values["timezone"] = tz
        return values

    @field_validator("tz")
    def __validate_tz(cls, value: str) -> str:
        """Validate timezone value that able to initialize with ZoneInfo after
        it passing to this model in before mode.

        :rtype: str
        """
        try:
            _ = ZoneInfo(value)
            return value
        except ZoneInfoNotFoundError as err:
            raise ValueError(f"Invalid timezone: {value}") from err

    @field_validator(
        "cronjob", mode="before", json_schema_input_type=Union[CronJob, str]
    )
    def __prepare_cronjob(
        cls, value: str | CronJob, info: ValidationInfo
    ) -> CronJob:
        """Prepare crontab value that able to receive with string type.
        This step will get options kwargs from extras and pass to the
        CronJob object.

        :rtype: CronJob
        """
        extras: DictData = info.data.get("extras", {})
        return (
            CronJob(
                value,
                option={
                    name: extras[name]
                    for name in (f.name for f in fields(Options))
                    if name in extras
                },
            )
            if isinstance(value, str)
            else value
        )

    @field_serializer("cronjob")
    def __serialize_cronjob(self, value: CronJob) -> str:
        """Serialize the cronjob field that store with CronJob object.

        :rtype: str
        """
        return str(value)

    def generate(self, start: str | datetime) -> CronRunner:
        """Return Cron runner object.

        :rtype: CronRunner
        """
        if isinstance(start, str):
            start: datetime = datetime.fromisoformat(start)
        elif not isinstance(start, datetime):
            raise TypeError("start value should be str or datetime type.")
        return self.cronjob.schedule(date=start, tz=self.tz)

    def next(self, start: str | datetime) -> CronRunner:
        """Return a next datetime from Cron runner object that start with any
        date that given from input.

        :rtype: CronRunner
        """
        runner: CronRunner = self.generate(start=start)

        # NOTE: ship the next date of runner object that create from start.
        _ = runner.next

        return runner


class YearOn(On):
    """On with enhance Year Pydantic model for limit year matrix that use by
    some data schedule tools like AWS Glue.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # NOTE: This is fields of the base schedule.
    cronjob: Annotated[
        CronJobYear,
        Field(description="Cron job of this schedule"),
    ]

    @field_validator(
        "cronjob", mode="before", json_schema_input_type=Union[CronJob, str]
    )
    def __prepare_cronjob(
        cls, value: str | CronJobYear, info: ValidationInfo
    ) -> CronJobYear:
        """Prepare crontab value that able to receive with string type.

        :rtype: CronJobYear
        """
        extras: DictData = info.data.get("extras", {})
        return (
            CronJobYear(
                value,
                option={
                    name: extras[name]
                    for name in (f.name for f in fields(Options))
                    if name in extras
                },
            )
            if isinstance(value, str)
            else value
        )
