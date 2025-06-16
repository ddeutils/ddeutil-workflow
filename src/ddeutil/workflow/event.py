# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Event Scheduling Module for Workflow Orchestration.

This module provides event-driven scheduling capabilities for workflows, with
a primary focus on cron-based scheduling. It includes models for defining
when workflows should be triggered and executed.

The core event trigger is the Crontab model, which wraps cron functionality
in a Pydantic model for validation and easy integration with the workflow system.

Classes:
    Crontab: Main cron-based event scheduler
    CrontabYear: Enhanced cron scheduler with year constraints
    ReleaseEvent: Release-based event triggers
    SensorEvent: Sensor-based event monitoring

Functions:
    interval2crontab: Convert interval specifications to cron expressions

Example:
    ```python
    from ddeutil.workflow.event import Crontab

    # Create daily schedule at 9 AM
    schedule = Crontab(
        cronjob="0 9 * * *",
        timezone="America/New_York"
    )

    # Generate next run times
    runner = schedule.generate(datetime.now())
    next_run = next(runner)
    ```
"""
from __future__ import annotations

from dataclasses import fields
from datetime import datetime
from typing import Annotated, Any, Literal, Optional, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo
from pydantic.functional_serializers import field_serializer
from pydantic.functional_validators import field_validator, model_validator
from pydantic_extra_types.timezone_name import TimeZoneName

from .__cron import WEEKDAYS, CronJob, CronJobYear, CronRunner, Options
from .__types import DictData

Interval = Literal["daily", "weekly", "monthly"]


def interval2crontab(
    interval: Interval,
    *,
    day: Optional[str] = None,
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

    Returns:
        str: The generated crontab expression.
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


class BaseCrontab(BaseModel):
    extras: DictData = Field(
        default_factory=dict,
        description=(
            "An extras parameters that want to pass to the CronJob field."
        ),
    )
    tz: TimeZoneName = Field(
        default="UTC",
        description="A timezone string value.",
        alias="timezone",
    )

    @model_validator(mode="before")
    def __prepare_values(cls, data: Any) -> Any:
        """Extract a `tz` key from data and change the key name from `tz` to
        `timezone`.

        :param data: (DictData) A data that want to pass for create a Crontab
            model.

        :rtype: DictData
        """
        if isinstance(data, dict) and (tz := data.pop("tz", None)):
            data["timezone"] = tz
        return data

    @field_validator("tz")
    def __validate_tz(cls, value: str) -> str:
        """Validate timezone value that able to initialize with ZoneInfo after
        it passing to this model in before mode.

        :rtype: str
        """
        try:
            _ = ZoneInfo(value)
            return value
        except ZoneInfoNotFoundError as e:
            raise ValueError(f"Invalid timezone: {value}") from e


class CrontabValue(BaseCrontab):
    interval: Interval
    day: Optional[str] = Field(default=None)
    time: str = Field(default="00:00")

    @property
    def cronjob(self) -> CronJob:
        """Return the CronJob object that was built from interval format."""
        return CronJob(
            value=interval2crontab(self.interval, day=self.day, time=self.time)
        )

    def generate(self, start: Union[str, datetime]) -> CronRunner:
        """Return CronRunner object from an initial datetime.

        :param start: (str | datetime) A string or datetime for generate the
            CronRunner object.

        :rtype: CronRunner
        """
        if isinstance(start, str):
            start: datetime = datetime.fromisoformat(start)
        elif not isinstance(start, datetime):
            raise TypeError("start value should be str or datetime type.")
        return self.cronjob.schedule(date=start, tz=self.tz)

    def next(self, start: Union[str, datetime]) -> CronRunner:
        """Return a next datetime from Cron runner object that start with any
        date that given from input.

        :param start: (str | datetime) A start datetime that use to generate
            the CronRunner object.

        :rtype: CronRunner
        """
        runner: CronRunner = self.generate(start=start)

        # NOTE: ship the next date of runner object that create from start.
        _ = runner.next

        return runner


class Crontab(BaseCrontab):
    """Cron event model (Warped the CronJob object by Pydantic model) to keep
    crontab value and generate CronRunner object from this crontab value.

    Methods:
        - generate: is the main use-case of this schedule object.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    cronjob: CronJob = Field(
        description=(
            "A Cronjob object that use for validate and generate datetime."
        ),
    )
    tz: TimeZoneName = Field(
        default="UTC",
        description="A timezone string value.",
        alias="timezone",
    )

    @model_validator(mode="before")
    def __prepare_values(cls, data: Any) -> Any:
        """Extract a `tz` key from data and change the key name from `tz` to
        `timezone`.

        :param data: (DictData) A data that want to pass for create a Crontab
            model.

        :rtype: DictData
        """
        if isinstance(data, dict) and (tz := data.pop("tz", None)):
            data["timezone"] = tz
        return data

    @field_validator(
        "cronjob", mode="before", json_schema_input_type=Union[CronJob, str]
    )
    def __prepare_cronjob(
        cls, value: Union[str, CronJob], info: ValidationInfo
    ) -> CronJob:
        """Prepare crontab value that able to receive with string type.
        This step will get options kwargs from extras field and pass to the
        CronJob object.

        :param value: (str | CronJobYear) A cronjob value that want to create.
        :param info: (ValidationInfo) A validation info object that use to get
            the extra parameters for create cronjob.

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

        :param value: (CronJob) The CronJob field.

        :rtype: str
        """
        return str(value)

    def generate(self, start: Union[str, datetime]) -> CronRunner:
        """Return CronRunner object from an initial datetime.

        :param start: (str | datetime) A string or datetime for generate the
            CronRunner object.

        :rtype: CronRunner
        """
        if isinstance(start, str):
            start: datetime = datetime.fromisoformat(start)
        elif not isinstance(start, datetime):
            raise TypeError("start value should be str or datetime type.")
        return self.cronjob.schedule(date=start, tz=self.tz)

    def next(self, start: Union[str, datetime]) -> CronRunner:
        """Return a next datetime from Cron runner object that start with any
        date that given from input.

        :param start: (str | datetime) A start datetime that use to generate
            the CronRunner object.

        :rtype: CronRunner
        """
        runner: CronRunner = self.generate(start=start)

        # NOTE: ship the next date of runner object that create from start.
        _ = runner.next

        return runner


class CrontabYear(Crontab):
    """Cron event with enhance Year Pydantic model for limit year matrix that
    use by some data schedule tools like AWS Glue.
    """

    cronjob: CronJobYear = (
        Field(
            description=(
                "A Cronjob object that use for validate and generate datetime."
            ),
        ),
    )

    @field_validator(
        "cronjob",
        mode="before",
        json_schema_input_type=Union[CronJobYear, str],
    )
    def __prepare_cronjob(
        cls, value: Union[CronJobYear, str], info: ValidationInfo
    ) -> CronJobYear:
        """Prepare crontab value that able to receive with string type.
        This step will get options kwargs from extras field and pass to the
        CronJobYear object.

        :param value: (str | CronJobYear) A cronjob value that want to create.
        :param info: (ValidationInfo) A validation info object that use to get
            the extra parameters for create cronjob.

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


Cron = Annotated[
    Union[
        CrontabYear,
        Crontab,
        CrontabValue,
    ],
    Field(
        union_mode="smart",
        description="An event models.",
    ),
]  # pragma: no cov


class Event(BaseModel):
    """Event model."""

    schedule: list[Cron] = Field(
        default_factory=list,
        description="A list of Cron schedule.",
    )
    release: list[str] = Field(
        default_factory=list,
        description=(
            "A list of workflow name that want to receive event from release"
            "trigger."
        ),
    )

    @field_validator("schedule", mode="after")
    def __on_no_dup_and_reach_limit__(
        cls,
        value: list[Crontab],
    ) -> list[Crontab]:
        """Validate the on fields should not contain duplicate values and if it
        contains the every minute value more than one value, it will remove to
        only one value.

        Args:
            value: A list of on object.

        Returns:
            list[CronJobYear | Crontab]: The validated list of Crontab objects.

        Raises:
            ValueError: If it has some duplicate value.
        """
        set_ons: set[str] = {str(on.cronjob) for on in value}
        if len(set_ons) != len(value):
            raise ValueError(
                "The on fields should not contain duplicate on value."
            )

        # WARNING:
        # if '* * * * *' in set_ons and len(set_ons) > 1:
        #     raise ValueError(
        #         "If it has every minute cronjob on value, it should have "
        #         "only one value in the on field."
        #     )
        set_tz: set[str] = {on.tz for on in value}
        if len(set_tz) > 1:
            raise ValueError(
                f"The on fields should not contain multiple timezone, "
                f"{list(set_tz)}."
            )

        if len(set_ons) > 10:
            raise ValueError(
                "The number of the on should not more than 10 crontabs."
            )
        return value
