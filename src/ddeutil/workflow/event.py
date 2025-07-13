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

Attributes:
    Interval: Type alias for scheduling intervals ('daily', 'weekly', 'monthly')

Classes:
    Crontab: Main cron-based event scheduler.
    CrontabYear: Enhanced cron scheduler with year constraints.
    ReleaseEvent: Release-based event triggers.
    FileEvent: File system monitoring triggers.
    WebhookEvent: API/webhook-based triggers.
    DatabaseEvent: Database change monitoring triggers.
    SensorEvent: Sensor-based event monitoring.

Example:
    >>> from ddeutil.workflow.event import Crontab
    >>> # NOTE: Create daily schedule at 9 AM
    >>> schedule = Crontab.model_validate(
    ...     {
    ...         "cronjob": "0 9 * * *",
    ...         "timezone": "America/New_York",
    ...     }
    ... )
    >>> # NOTE: Generate next run times
    >>> runner = schedule.generate(datetime.now())
    >>> next_run = runner.next
"""
from __future__ import annotations

from dataclasses import fields
from datetime import datetime
from typing import Annotated, Any, Literal, Optional, Union

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
    """Convert interval specification to cron expression.

    Args:
        interval: Scheduling interval ('daily', 'weekly', or 'monthly').
        day: Day of week for weekly intervals or monthly schedules. Defaults to
            Monday for weekly intervals.
        time: Time of day in 'HH:MM' format. Defaults to '00:00'.

    Returns:
        Generated crontab expression string.

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
        d = str(WEEKDAYS[(day or "monday")[:3].title()])
    elif interval == "monthly" and day:
        d = str(WEEKDAYS[day[:3].title()])

    h, m = tuple(
        i.lstrip("0") if i != "00" else "0" for i in time.split(":", maxsplit=1)
    )
    return f"{h} {m} {'1' if interval == 'monthly' else '*'} * {d}"


class BaseCrontab(BaseModel):
    """Base class for crontab-based scheduling models.

    Attributes:
        extras: Additional parameters to pass to the CronJob field.
        tz: Timezone string value (alias: timezone).
    """

    extras: DictData = Field(
        default_factory=dict,
        description=(
            "An extras parameters that want to pass to the CronJob field."
        ),
    )
    tz: TimeZoneName = Field(
        default="UTC",
        description="A timezone string value that will pass to ZoneInfo.",
        alias="timezone",
    )

    @model_validator(mode="before")
    def __prepare_values(cls, data: Any) -> Any:
        """Extract and rename timezone key in input data.

        Args:
            data: Input data dictionary for creating Crontab model.

        Returns:
            Modified data dictionary with standardized timezone key.
        """
        if isinstance(data, dict) and (tz := data.pop("tz", None)):
            data["timezone"] = tz
        return data


class CrontabValue(BaseCrontab):
    """Crontab model using interval-based specification.

    Attributes:
        interval: (Interval)
            A scheduling interval string ('daily', 'weekly', 'monthly').
        day: (str, default None)
            Day specification for weekly/monthly schedules.
        time: Time of day in 'HH:MM' format.
    """

    interval: Interval = Field(description="A scheduling interval string.")
    day: Optional[str] = Field(default=None)
    time: str = Field(
        default="00:00",
        pattern=r"\d{2}:\d{2}",
        description="A time of day that pass with format 'HH:MM'.",
    )

    @property
    def cronjob(self) -> CronJob:
        """Get CronJob object built from interval format.

        Returns:
            CronJob instance configured with interval-based schedule.
        """
        return CronJob(
            value=interval2crontab(self.interval, day=self.day, time=self.time)
        )

    def generate(self, start: Union[str, datetime]) -> CronRunner:
        """Generate CronRunner from initial datetime.

        Args:
            start: Starting datetime (string or datetime object).

        Returns:
            CronRunner instance for schedule generation.

        Raises:
            TypeError: If start parameter is neither string nor datetime.
        """
        if isinstance(start, str):
            return self.cronjob.schedule(
                date=datetime.fromisoformat(start), tz=self.tz
            )

        if isinstance(start, datetime):
            return self.cronjob.schedule(date=start, tz=self.tz)
        raise TypeError("start value should be str or datetime type.")

    def next(self, start: Union[str, datetime]) -> CronRunner:
        """Get next scheduled datetime after given start time.

        Args:
            start: Starting datetime for schedule generation.

        Returns:
            CronRunner instance positioned at next scheduled time.
        """
        runner: CronRunner = self.generate(start=start)

        # NOTE: ship the next date of runner object that create from start.
        _ = runner.next

        return runner


class Crontab(BaseCrontab):
    """Cron event model wrapping CronJob functionality.

    A Pydantic model that encapsulates crontab scheduling functionality with
    validation and datetime generation capabilities.

    Attributes:
        cronjob: CronJob instance for schedule validation and datetime generation.
        tz: Timezone string value (alias: timezone).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    cronjob: CronJob = Field(
        description=(
            "A Cronjob object that use for validate and generate datetime."
        ),
    )

    @model_validator(mode="before")
    def __prepare_values(cls, data: Any) -> Any:
        """Prepare input data by standardizing timezone key.

        Args:
            data: Input dictionary for model creation.

        Returns:
            Modified dictionary with standardized timezone key.
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
        """Prepare and validate cronjob input.

        Args:
            value: Raw cronjob value (string or CronJob instance).
            info: Validation context containing extra parameters.

        Returns:
            Configured CronJob instance.
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
        """Serialize CronJob instance to string representation.

        Args:
            value: CronJob instance to serialize.

        Returns:
            String representation of the CronJob.
        """
        return str(value)

    def generate(self, start: Union[str, datetime]) -> CronRunner:
        """Generate schedule runner from start time.

        Args:
            start: Starting datetime (string or datetime object).

        Returns:
            CronRunner instance for schedule generation.

        Raises:
            TypeError: If start parameter is neither string nor datetime.
        """
        if isinstance(start, str):
            start: datetime = datetime.fromisoformat(start)
        elif not isinstance(start, datetime):
            raise TypeError("start value should be str or datetime type.")
        return self.cronjob.schedule(date=start, tz=self.tz)

    def next(self, start: Union[str, datetime]) -> CronRunner:
        """Get runner positioned at next scheduled time.

        Args:
            start: Starting datetime for schedule generation.

        Returns:
            CronRunner instance positioned at next scheduled time.
        """
        runner: CronRunner = self.generate(start=start)

        # NOTE: ship the next date of runner object that create from start.
        _ = runner.next

        return runner


class CrontabYear(Crontab):
    """Cron event model with enhanced year-based scheduling.

    Extends the base Crontab model to support year-specific scheduling,
    particularly useful for tools like AWS Glue.

    Attributes:
        cronjob: CronJobYear instance for year-aware schedule validation and generation.
    """

    cronjob: CronJobYear = Field(
        description=(
            "A Cronjob object that use for validate and generate datetime."
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
        """Prepare and validate year-aware cronjob input.

        Args:
            value: Raw cronjob value (string or CronJobYear instance).
            info: Validation context containing extra parameters.

        Returns:
            Configured CronJobYear instance with applied options.
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
        description=(
            "Event model type supporting year-based, standard, and "
            "interval-based cron scheduling."
        ),
    ),
]  # pragma: no cov


class Event(BaseModel):
    """Event model with comprehensive trigger support.

    Supports multiple types of event triggers including cron scheduling,
    file monitoring, webhooks, database changes, sensor-based triggers,
    polling-based triggers, message queue events, stream processing events,
    batch processing events, data quality events, API rate limiting events,
    data lineage events, ML pipeline events, data catalog events,
    infrastructure events, compliance events, and business events.
    """

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
