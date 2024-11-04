# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import copy
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial, total_ordering
from typing import ClassVar, Optional, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ddeutil.core import (
    checker,
    isinstance_check,
    must_split,
)
from ddeutil.core.dtutils import next_date, replace_date

WEEKDAYS: dict[str, int] = {
    "Sun": 0,
    "Mon": 1,
    "Tue": 2,
    "Wed": 3,
    "Thu": 4,
    "Fri": 5,
    "Sat": 6,
}


class CronYearLimit(Exception): ...


def str2cron(value: str) -> str:  # pragma: no cov
    """Convert Special String with the @ prefix to Crontab value.

    :param value: A string value that want to convert to cron value.
    :rtype: str

    Table:

        @reboot 	Run once, at system startup
        @yearly 	Run once every year, "0 0 1 1 *"
        @annually   (same as @yearly)
        @monthly    Run once every month, "0 0 1 * *"
        @weekly 	Run once every week, "0 0 * * 0"
        @daily  	Run once each day, "0 0 * * *"
        @midnight   (same as @daily)
        @hourly 	Run once an hour, "0 * * * *"
    """
    mapping_spacial_str = {
        "@reboot": "",
        "@yearly": "0 0 1 1 *",
        "@annually": "0 0 1 1 *",
        "@monthly": "0 0 1 * *",
        "@weekly": "0 0 * * 0",
        "@daily": "0 0 * * *",
        "@midnight": "0 0 * * *",
        "@hourly": "0 * * * *",
    }
    return mapping_spacial_str[value]


@dataclass(frozen=True)
class Unit:
    """Unit dataclass for CronPart object."""

    name: str
    range: partial
    min: int
    max: int
    alt: list[str] = field(default_factory=list)

    def __repr__(self) -> str:
        return (
            f"{self.__class__}(name={self.name!r}, range={self.range},"
            f"min={self.min}, max={self.max}"
            f"{f', alt={self.alt}' if self.alt else ''})"
        )


@dataclass
class Options:
    """Options dataclass for config CronPart object."""

    output_weekday_names: bool = False
    output_month_names: bool = False
    output_hashes: bool = False


CRON_UNITS: tuple[Unit, ...] = (
    Unit(
        name="minute",
        range=partial(range, 0, 60),
        min=0,
        max=59,
    ),
    Unit(
        name="hour",
        range=partial(range, 0, 24),
        min=0,
        max=23,
    ),
    Unit(
        name="day",
        range=partial(range, 1, 32),
        min=1,
        max=31,
    ),
    Unit(
        name="month",
        range=partial(range, 1, 13),
        min=1,
        max=12,
        alt=[
            "JAN",
            "FEB",
            "MAR",
            "APR",
            "MAY",
            "JUN",
            "JUL",
            "AUG",
            "SEP",
            "OCT",
            "NOV",
            "DEC",
        ],
    ),
    Unit(
        name="weekday",
        range=partial(range, 0, 7),
        min=0,
        max=6,
        alt=[
            "SUN",
            "MON",
            "TUE",
            "WED",
            "THU",
            "FRI",
            "SAT",
        ],
    ),
)

CRON_UNITS_YEAR: tuple[Unit, ...] = CRON_UNITS + (
    Unit(
        name="year",
        range=partial(range, 1990, 2101),
        min=1990,
        max=2100,
    ),
)


@total_ordering
class CronPart:
    """Part of Cron object that represent a collection of positive integers.

    :param unit: A Unit dataclass object.
    :param values: A crontab values that want to validate
    :param options: A Options dataclass object.
    """

    __slots__: tuple[str, ...] = (
        "unit",
        "options",
        "values",
    )

    def __init__(
        self,
        unit: Unit,
        values: str | list[int],
        options: Options,
    ) -> None:
        self.unit: Unit = unit
        self.options: Options = options

        if isinstance(values, str):
            values: list[int] = self.from_str(values) if values != "?" else []
        elif isinstance_check(values, list[int]):
            values: list[int] = self.replace_weekday(values)
        else:
            raise TypeError(f"Invalid type of value in cron part: {values}.")

        self.values: list[int] = self.out_of_range(
            sorted(dict.fromkeys(values))
        )

    def __str__(self) -> str:
        """Generate String value from part of cronjob."""
        _hash: str = "H" if self.options.output_hashes else "*"

        if self.is_full:
            return _hash

        if self.is_interval:
            if self.is_full_interval:
                return f"{_hash}/{self.step}"
            _hash: str = (
                f"H({self.filler(self.min)}-{self.filler(self.max)})"
                if _hash == "H"
                else f"{self.filler(self.min)}-{self.filler(self.max)}"
            )
            return f"{_hash}/{self.step}"

        cron_range_strings: list[str] = []
        for cron_range in self.ranges():
            if isinstance(cron_range, list):
                cron_range_strings.append(
                    f"{self.filler(cron_range[0])}-{self.filler(cron_range[1])}"
                )
            else:
                cron_range_strings.append(f"{self.filler(cron_range)}")
        return ",".join(cron_range_strings) if cron_range_strings else "?"

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}"
            f"(unit={self.unit}, values={self.__str__()!r})"
        )

    def __lt__(self, other) -> bool:
        if isinstance(other, CronPart):
            return self.values < other.values
        elif isinstance(other, list):
            return self.values < other

    def __eq__(self, other) -> bool:
        if isinstance(other, CronPart):
            return self.values == other.values
        elif isinstance(other, list):
            return self.values == other

    @property
    def min(self) -> int:
        """Returns the smallest value in the range."""
        return self.values[0]

    @property
    def max(self) -> int:
        """Returns the largest value in the range."""
        return self.values[-1]

    @property
    def step(self) -> Optional[int]:
        """Returns the difference between first and second elements in the
        range.
        """
        if (
            len(self.values) > 2
            and (step := self.values[1] - self.values[0]) > 1
        ):
            return step

    @property
    def is_full(self) -> bool:
        """Returns true if range has all the values of the unit."""
        return len(self.values) == (self.unit.max - self.unit.min + 1)

    def from_str(self, value: str) -> tuple[int, ...]:
        """Parses a string as a range of positive integers. The string should
        include only `-` and `,` special strings.

        :param value: A string value that want to parse
        :type value: str

        TODO: support for `L`, `W`, and `#`
        ---
        TODO: The ? (question mark) wildcard specifies one or another.
            In the Day-of-month field you could enter 7, and if you didn't care
            what day of the week the seventh was, you could enter ? in the
            Day-of-week field.
        TODO: L : The L wildcard in the Day-of-month or Day-of-week fields
            specifies the last day of the month or week.
            DEV: use -1 for represent with L
        TODO: W : The W wildcard in the Day-of-month field specifies a weekday.
            In the Day-of-month field, 3W specifies the weekday closest to the
            third day of the month.
        TODO: # : 3#2 would be the second Tuesday of every month,
            the 3 refers to Tuesday because it is the third day of each week.

        Examples:
            -   0 10 * * ? *
                Run at 10:00 am (UTC) every day

            -   15 12 * * ? *
                Run at 12:15 pm (UTC) every day

            -   0 18 ? * MON-FRI *
                Run at 6:00 pm (UTC) every Monday through Friday

            -   0 8 1 * ? *
                Run at 8:00 am (UTC) every 1st day of the month

            -   0/15 * * * ? *
                Run every 15 minutes

            -   0/10 * ? * MON-FRI *
                Run every 10 minutes Monday through Friday

            -   0/5 8-17 ? * MON-FRI *
                Run every 5 minutes Monday through Friday between 8:00 am and
                5:55 pm (UTC)

            -   5,35 14 * * ? *
                Run every day, at 5 and 35 minutes past 2:00 pm (UTC)

            -   15 10 ? * 6L 2002-2005
                Run at 10:15am UTC on the last Friday of each month during the
                years 2002 to 2005

        :rtype: tuple[int, ...]
        """
        interval_list: list[list[int]] = []
        # NOTE: Start replace alternative like JAN to FEB or MON to SUN.
        for _value in self.replace_alternative(value.upper()).split(","):
            if _value == "?":
                continue
            elif _value.count("/") > 1:
                raise ValueError(
                    f"Invalid value {_value!r} in cron part {value!r}"
                )

            value_range, value_step = must_split(_value, "/", maxsplit=1)
            value_range_list: list[int] = self.out_of_range(
                self._parse_range(value_range)
            )

            if (
                value_step and not checker.is_int(value_step)
            ) or value_step == "":
                raise ValueError(
                    f"Invalid interval step value {value_step!r} for "
                    f"{self.unit.name!r}"
                )

            # NOTE: Generate interval that has step
            interval_list.append(self._interval(value_range_list, value_step))

        return tuple(item for sublist in interval_list for item in sublist)

    def replace_alternative(self, value: str) -> str:
        """Replaces the alternative representations of numbers in a string.

            For example if value == 'JAN,AUG' it will replace to '1,8'.

        :param value: A string value that want to replace alternative to int.
        """
        for i, alt in enumerate(self.unit.alt):
            if alt in value:
                value: str = value.replace(alt, str(self.unit.min + i))
        return value

    def replace_weekday(self, values: list[int] | Iterator[int]) -> list[int]:
        """Replaces all 7 with 0 as Sunday can be represented by both.

        :param values: list or iter of int that want to mode by 7
        :rtype: list[int]
        """
        if self.unit.name == "weekday":
            # NOTE: change weekday value in range 0-6 (div-mod by 7).
            return [value % 7 for value in values]
        return list(values)

    def out_of_range(self, values: list[int]) -> list[int]:
        """Return an integer is a value out of range was found, otherwise None.

        :param values: A list of int value
        :type values: list[int]

        :rtype: list[int]
        """
        if values:
            if (first := values[0]) < self.unit.min:
                raise ValueError(
                    f"Value {first!r} out of range for {self.unit.name!r}"
                )
            elif (last := values[-1]) > self.unit.max:
                raise ValueError(
                    f"Value {last!r} out of range for {self.unit.name!r}"
                )
        return values

    def _parse_range(self, value: str) -> list[int]:
        """Parses a range string."""
        if value == "*":
            return list(self.unit.range())
        elif value.count("-") > 1:
            raise ValueError(f"Invalid value {value}")
        try:
            sub_parts: list[int] = list(map(int, value.split("-")))
        except ValueError as exc:
            raise ValueError(f"Invalid value {value!r} --> {exc}") from exc

        if len(sub_parts) == 2:
            min_value, max_value = sub_parts
            if max_value < min_value:
                raise ValueError(f"Max range is less than min range in {value}")
            sub_parts: list[int] = list(range(min_value, max_value + 1))
        return self.replace_weekday(sub_parts)

    def _interval(
        self,
        values: list[int],
        step: int | None = None,
    ) -> list[int]:
        """Applies an interval step to a collection of values."""
        if not step:
            return values
        elif (_step := int(step)) < 1:
            raise ValueError(
                f"Invalid interval step value {_step!r} for "
                f"{self.unit.name!r}"
            )
        min_value: int = values[0]
        return [
            value
            for value in values
            if (value % _step == min_value % _step) or (value == min_value)
        ]

    @property
    def is_interval(self) -> bool:
        """Returns true if the range can be represented as an interval."""
        if not (step := self.step):
            return False
        for idx, value in enumerate(self.values):
            if idx == 0:
                continue
            elif (value - self.values[idx - 1]) != step:
                return False
        return True

    @property
    def is_full_interval(self) -> bool:
        """Returns true if the range contains all the interval values."""
        if step := self.step:
            return (
                self.min == self.unit.min
                and (self.max + step) > self.unit.max
                and (
                    len(self.values)
                    == (round((self.max - self.min) / step) + 1)
                )
            )
        return False

    def ranges(self) -> list[Union[int, list[int]]]:
        """Returns the range as an array of ranges defined as arrays of
        positive integers.

        :rtype: list[Union[int, list[int]]]
        """
        multi_dim_values: list[Union[int, list[int]]] = []
        start_number: Optional[int] = None
        for idx, value in enumerate(self.values):
            try:
                next_value: int = self.values[idx + 1]
            except IndexError:
                next_value: int = -1
            if value != (next_value - 1):
                # NOTE: ``next_value`` is not the subsequent number
                if start_number is None:
                    # NOTE:
                    #   The last number of the list ``self.values`` is not in a
                    #   range.
                    multi_dim_values.append(value)
                else:
                    multi_dim_values.append([start_number, value])
                    start_number: Optional[int] = None
            elif start_number is None:
                start_number: Optional[int] = value
        return multi_dim_values

    def filler(self, value: int) -> int | str:
        """Formats weekday and month names as string when the relevant options
        are set.

        :param value: a int value
        :type value: int

        :rtype: int | str
        """
        return (
            self.unit.alt[value - self.unit.min]
            if (
                (
                    self.options.output_weekday_names
                    and self.unit.name == "weekday"
                )
                or (
                    self.options.output_month_names
                    and self.unit.name == "month"
                )
            )
            else value
        )


@total_ordering
class CronJob:
    """The Cron Job Converter object that generate datetime dimension of cron
    job schedule format,

        *  *  *  *  *  <command to execute>

        (i)     minute (0 - 59)
        (ii)    hour (0 - 23)
        (iii)   day of the month (1 - 31)
        (iv)    month (1 - 12)
        (v)     day of the week (0 - 6) (Sunday to Saturday; 7 is also Sunday
                on some systems)

        This object implement necessary methods and properties for using cron
    job value with other object like Schedule.
        Support special value with `/`, `*`, `-`, `,`, and `?` (in day of month
    and day of week value).

        Fields          | Values            | Wildcards
        ---             | ---               | ---
        Minutes         | 0–59              | , - * /
        Hours           | 0–23              | , - * /
        Day-of-month    | 1–31              | , - * ? / L W
        Month           | 1–12 or JAN-DEC   | , - * /
        Day-of-week     | 1–7 or SUN-SAT    | , - * ? / L
        Year            | 1970–2199         | , - * /

    References:
        - https://github.com/Sonic0/cron-converter
        - https://pypi.org/project/python-crontab/
        - https://docs.aws.amazon.com/glue/latest/dg/ -
            monitor-data-warehouse-schedule.html
    """

    cron_length: int = 5
    cron_units: tuple[Unit, ...] = CRON_UNITS

    def __init__(
        self,
        value: Union[list[list[int]], str],
        *,
        option: Optional[dict[str, bool]] = None,
    ) -> None:
        if isinstance(value, str):
            value: list[str] = value.strip().split()
        elif not isinstance_check(value, list[list[int]]):
            raise TypeError(
                f"{self.__class__.__name__} cron value does not support "
                f"type: {type(value)}."
            )

        # NOTE: Validate length of crontab of this class.
        if len(value) != self.cron_length:
            raise ValueError(
                f"Invalid cron value does not have length equal "
                f"{self.cron_length}: {value}."
            )
        self.options: Options = Options(**(option or {}))

        # NOTE: Start initial crontab for each part
        self.parts: list[CronPart] = [
            CronPart(unit, values=item, options=self.options)
            for item, unit in zip(value, self.cron_units)
        ]

        # NOTE: Validate values of `day` and `dow` from parts.
        if self.day == self.dow == []:
            raise ValueError(
                "Invalid cron value when set the `?` on day of month and "
                "day of week together"
            )

    def __str__(self) -> str:
        """Return joining with space of each value in parts."""
        return " ".join(str(part) for part in self.parts)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(value={self.__str__()!r}, "
            f"option={self.options.__dict__})"
        )

    def __lt__(self, other) -> bool:
        return any(
            part < other_part
            for part, other_part in zip(self.parts_order, other.parts_order)
        )

    def __eq__(self, other) -> bool:
        return all(
            part == other_part
            for part, other_part in zip(self.parts, other.parts)
        )

    @property
    def parts_order(self) -> Iterator[CronPart]:
        return reversed(self.parts[:3] + [self.parts[4], self.parts[3]])

    @property
    def minute(self) -> CronPart:
        """Return part of minute."""
        return self.parts[0]

    @property
    def hour(self) -> CronPart:
        """Return part of hour."""
        return self.parts[1]

    @property
    def day(self) -> CronPart:
        """Return part of day."""
        return self.parts[2]

    @property
    def month(self) -> CronPart:
        """Return part of month."""
        return self.parts[3]

    @property
    def dow(self) -> CronPart:
        """Return part of day of month."""
        return self.parts[4]

    def to_list(self) -> list[list[int]]:
        """Returns the cron schedule as a 2-dimensional list of integers."""
        return [part.values for part in self.parts]

    def check(self, date: datetime, mode: str) -> bool:
        assert mode in ("year", "month", "day", "hour", "minute")
        return getattr(date, mode) in getattr(self, mode).values

    def schedule(
        self,
        date: datetime | None = None,
        *,
        tz: str | None = None,
    ) -> CronRunner:
        """Returns the schedule datetime runner with this cronjob. It would run
        ``next``, ``prev``, or ``reset`` to generate running date that you want.

        :param date: An initial date that want to mark as the start point.
        :param tz: A string timezone that want to change on runner.

        :rtype: CronRunner
        """
        return CronRunner(self, date, tz=tz)


class CronJobYear(CronJob):
    """The Cron Job Converter with Year extension object that generate datetime
    dimension of cron job schedule format,

        *  *  *  *  *  *  <command to execute>

        (i)     minute (0 - 59)
        (ii)    hour (0 - 23)
        (iii)   day of the month (1 - 31)
        (iv)    month (1 - 12)
        (v)     day of the week (0 - 6) (Sunday to Saturday; 7 is also Sunday
                on some systems)
        (vi)    year (1990 - 2100)
    """

    cron_length = 6
    cron_units = CRON_UNITS_YEAR

    @property
    def year(self) -> CronPart:
        """Return part of year."""
        return self.parts[5]


class CronRunner:
    """Create an instance of Date Runner object for datetime generate with
    cron schedule object value.
    """

    shift_limit: ClassVar[int] = 25

    __slots__: tuple[str, ...] = (
        "__start_date",
        "cron",
        "is_year",
        "date",
        "reset_flag",
        "tz",
    )

    def __init__(
        self,
        cron: CronJob | CronJobYear,
        date: datetime | None = None,
        *,
        tz: str | None = None,
    ) -> None:
        # NOTE: Prepare timezone if this value does not set, it will use UTC.
        self.tz: ZoneInfo = ZoneInfo("UTC")
        if tz:
            try:
                self.tz = ZoneInfo(tz)
            except ZoneInfoNotFoundError as err:
                raise ValueError(f"Invalid timezone: {tz}") from err

        # NOTE: Prepare date
        if date:
            if not isinstance(date, datetime):
                raise ValueError(
                    "Input schedule start time is not a valid datetime object."
                )
            if tz is None:
                self.tz = date.tzinfo
            self.date: datetime = date.astimezone(self.tz)
        else:
            self.date: datetime = datetime.now(tz=self.tz)

        # NOTE: Add one second if the microsecond value more than 0.
        if self.date.microsecond > 0:
            self.date: datetime = self.date.replace(microsecond=0) + timedelta(
                seconds=1
            )

        # NOTE: Add one minute if the second value more than 0.
        if self.date.second > 0:
            self.date: datetime = self.date.replace(second=0) + timedelta(
                minutes=1
            )

        self.__start_date: datetime = self.date
        self.cron: CronJob | CronJobYear = cron
        self.is_year: bool = isinstance(cron, CronJobYear)
        self.reset_flag: bool = True

    def reset(self) -> None:
        """Resets the iterator to start time."""
        self.date: datetime = self.__start_date
        self.reset_flag: bool = True

    @property
    def next(self) -> datetime:
        """Returns the next time of the schedule."""
        self.date = (
            self.date
            if self.reset_flag
            else (self.date + timedelta(minutes=+1))
        )
        return self.find_date(reverse=False)

    @property
    def prev(self) -> datetime:
        """Returns the previous time of the schedule."""
        self.date: datetime = self.date + timedelta(minutes=-1)
        return self.find_date(reverse=True)

    def find_date(self, reverse: bool = False) -> datetime:
        """Returns the time the schedule would run by `next` or `prev` methods.

        :param reverse: A reverse flag.
        """
        # NOTE: Set reset flag to false if start any action.
        self.reset_flag: bool = False

        # NOTE: For loop with 25 times by default.
        for _ in range(
            max(self.shift_limit, 100) if self.is_year else self.shift_limit
        ):

            # NOTE: Shift the date
            if all(
                not self.__shift_date(mode, reverse)
                for mode in ("year", "month", "day", "hour", "minute")
            ):
                return copy.deepcopy(self.date)

        raise RecursionError("Unable to find execution time for schedule")

    def __shift_date(self, mode: str, reverse: bool = False) -> bool:
        """Increments the mode of date value ("month", "day", "hour", "minute")
        until matches with the schedule.

        :param mode: A mode of date that want to shift.
        :param reverse: A flag that define shifting next or previous
        """
        switch: dict[str, str] = {
            "year": "year",
            "month": "year",
            "day": "month",
            "hour": "day",
            "minute": "hour",
        }
        current_value: int = getattr(self.date, switch[mode])

        if not self.is_year and mode == "year":
            return False

        # NOTE: Additional condition for weekdays
        def addition_cond(dt: datetime) -> bool:
            return (
                WEEKDAYS.get(dt.strftime("%a")) not in self.cron.dow.values
                if mode == "day"
                else False
            )

        # NOTE:
        #   Start while-loop for checking this date include in this cronjob.
        while not self.cron.check(self.date, mode) or addition_cond(self.date):
            if mode == "year" and (
                getattr(self.date, mode)
                > (max_year := max(self.cron.year.values))
            ):
                raise CronYearLimit(
                    f"The year is out of limit with this crontab value: "
                    f"{max_year}."
                )

            # NOTE: Shift date with it mode matrix unit.
            self.date: datetime = next_date(self.date, mode, reverse=reverse)

            # NOTE: Replace date that less than it mode to zero.
            self.date: datetime = replace_date(self.date, mode, reverse=reverse)

            # NOTE: Replace second and microsecond values that change from
            #   the replace_date func with reverse flag.
            self.date: datetime = self.date.replace(second=0, microsecond=0)

            if current_value != getattr(self.date, switch[mode]):
                return mode != "month"

        # NOTE: Return False if the date that match with condition.
        return False


__all__ = (
    "CronJob",
    "CronJobYear",
    "CronRunner",
    "WEEKDAYS",
)
