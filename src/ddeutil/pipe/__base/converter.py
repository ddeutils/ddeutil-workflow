# -------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# --------------------------------------------------------------------------

import copy
import re
from collections.abc import Iterator
from datetime import (
    datetime,
    timedelta,
)
from functools import (
    partial,
    total_ordering,
)
from typing import (
    Optional,
    Union,
)

from dateutil import tz
from ddeutil.core.__base import (
    is_int,
    isinstance_check,
    merge_dict,
    must_rsplit,
    must_split,
)
from ddeutil.core.dtutils import (
    next_date,
    replace_date,
)


class SchemaFeatures:
    """ """

    def __init__(
        self,
        alias: str,
        nullable: Optional[bool] = False,
        pk: Optional = None,
        default: Optional = None,
        fk: Optional = None,
    ): ...


class Schemas:
    """The Schema Converter object that implement converter methods of schema
    config data like `data_type`, `rename_cols`, etc.

    :usage:
        >>> schema_obj = Schemas({
        ...     'conf_data': {'alias': "varchar(64)", 'nullable': False},
        ...     'update_time': {'alias': "datetime", 'nullable': False},
        ...     'register_time': {'alias': "datetime", 'nullable': False}
        ... })
        >>> schema_obj.features['conf_data']['pk']

        >>> schema_obj.features['conf_data']['alias']
        'varchar(64)'

    """

    datatype_ptt: str = "::"

    mapping_necessary_keys: dict = {
        "alias": {
            "name",
            "datatype",
            "type",
        },
        "nullable": {
            "na",
            "null",
        },
        "pk": {
            "primary_key",
            "primary",
        },
        "unique": {
            "uq",
        },
        "default": {
            "df",
            "fill_na",
        },
        "fk": {
            "foreign_key",
            "foreign",
        },
    }

    def __init__(self, schemas: dict):
        self._schemas: dict = {
            col: self.prepare(schemas[col]) for col in schemas
        }

    @property
    def features(self) -> dict:
        """Return feature of schemas."""
        return self._schemas

    @property
    def pk(self):
        """Return the primary key columns of this schema data."""
        return [_ for _ in self._schemas if _["pk"] is not None]

    def prepare(self, value: Union[str, dict]) -> dict:
        """Return mapping of column properties which included
        `cls.mapping_necessary_keys`.
        """
        if not isinstance(value, (dict, str)):
            raise AttributeError(
                f"value of schema mapping data does not support for "
                f"type: {type(value)}."
            )
        _value: dict = value if isinstance(value, dict) else {"alias": value}
        for key in self.mapping_necessary_keys:
            for must_change in self.mapping_necessary_keys[key]:
                if must_change in _value:
                    _value[key] = _value.pop(must_change)
            if key not in _value:
                _value[key] = None
        return _value

    def data_type(self, style: str = "new") -> dict:
        """Return the mapping of data type that can switch the column name by
        old or new style from the configuration data like,

                schemas:
                    <new-column-name>:
                        'alias': '<old-column-name><data-type-ptt><data-type>'
                        ...

        """
        assert style in {
            "old",
            "new",
        }, "the `style` should equal the only one of 'old' or 'new' value"
        _result: dict = {}
        for col, mapping in self._schemas.items():
            _col_old, _type = must_rsplit(mapping["alias"], "::", maxsplit=1)
            if style == "old" and _col_old is not None:
                _result[_col_old]: str = _type
            else:
                _result[col]: str = _type
        return _result

    def rename_cols(self) -> dict:
        """Return mapping of old and new column name."""
        _result: dict = {}
        for col, mapping in self._schemas.items():
            _col_old, _type = must_rsplit(mapping["alias"], "::", maxsplit=1)
            _result[_col_old]: str = col
        return _result


class Statement:
    """The Statement Converter that convert statement mapping to a string value
    for execute to RDBMS system.

    :usage:
        >>> statement_obj = Statement(
        ...     "select {columns} from {{database}}.{schema}.{table} "
        ...     "where {table}={condition};"
        ... )
        >>> statement_obj.parameters
        ['columns', 'condition', 'schema', 'table']
    """

    statement_ptt: str = ";"

    @classmethod
    def load(cls, stm: Union[str, dict, list[str]]):
        """Dialect load value with not string type of value in mapping
        statement.
        """
        if isinstance(stm, str):
            stm: dict = {"common": stm}
        elif isinstance_check(stm, list[str]):
            stm: dict = {"common": f"{cls.statement_ptt} ".join(stm)}
        elif isinstance(stm, dict):
            # Convert if does not match with type: Dict[str, str]
            ...
        return cls(stm=stm)

    def __init__(self, stm: dict[str, str], *, sensitive: bool = False):
        """Main initialize of the statement object.

        :structure:

            statement:
                common: "<statement-common>"

            statement:
                with_<temp-table-name>: "<statement-with>"
                with_exists: "<statement-exists>"

            statement:
                update:
                    table: "<table-name>"
                    from: ""
                    set:
                        target-col: from-col
                        ...

                insert:
                    into: "<table-name>"
                    from: "<select-statement>"
                    mapping:
                        target-col: from-col
                        ...
                    conflict:
                        set:
                            target-col: from-col
                        where: ""

                delete:
                    into: ""
                    from: ""
                    where: ""

                merge:
                    into: ""
                    from: ""
                    not_match: ""
                    match_by_source: ""
                    match_by_target: ""

        """
        # Prepare statement input.
        for _ in stm:
            if not isinstance((_value := stm[_]), str):
                raise NotImplementedError(
                    f"{self.__class__.__name__} dose not support for not "
                    f"string type in value of mapping statement."
                )
            value: str = " ".join(_value.split())
            if not sensitive:
                value: str = value.lower()
            stm[_] = value
        self._st_stm: dict[str, str] = stm

    def __str__(self) -> str:
        return self._st_stm

    def __repr__(self):
        return f"<{self.__class__.__name__}(stm='{self._st_stm}')>"

    @property
    def parameters(self) -> list:
        """Return parameters of format string from the statement."""
        return sorted(
            frozenset(
                re.findall(r"{(\w.*?)}", re.sub(r"({{|}})", "", self._st_stm))
            )
        )

    @staticmethod
    def _check_type(statement: str) -> str:
        """Return type of SQL statement."""
        _statement: str = statement.strip()
        if _statement.startswith("select"):
            # Data Query Language
            return "dql"
        elif _statement.startswith(
            (
                "insert into",
                "update",
                "delete from",
                "merge",
            )
        ):
            # Data Manipulation Language
            return "dml"
        elif _statement.startswith(
            (
                "create",
                "alter",
                "drop",
                "truncate",
                "rename",
            )
        ):
            # Data Definition Language
            return "ddl"
        elif _statement.startswith(
            (
                "grant",
                "revoke",
            )
        ):
            # Data Control Language
            return "dcl"
        return "undefined"


WEEKDAYS: dict[str, int] = {
    "Sun": 0,
    "Mon": 1,
    "Tue": 2,
    "Wed": 3,
    "Thu": 4,
    "Fri": 5,
    "Sat": 6,
}

CRON_UNITS: tuple = (
    {
        "name": "minute",
        "range": partial(range, 0, 60),
        "min": 0,
        "max": 59,
    },
    {
        "name": "hour",
        "range": partial(range, 0, 24),
        "min": 0,
        "max": 23,
    },
    {
        "name": "day",
        "range": partial(range, 1, 32),
        "min": 1,
        "max": 31,
    },
    {
        "name": "month",
        "range": partial(range, 1, 13),
        "min": 1,
        "max": 12,
        "alt": [
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
    },
    {
        "name": "weekday",
        "range": partial(range, 0, 7),
        "min": 0,
        "max": 6,
        "alt": [
            "SUN",
            "MON",
            "TUE",
            "WED",
            "THU",
            "FRI",
            "SAT",
        ],
    },
)

CRON_UNITS_AWS: tuple = CRON_UNITS + (
    {
        "name": "year",
        "range": partial(range, 1990, 2101),
        "min": 1990,
        "max": 2100,
    },
)


@total_ordering
class CronPart:
    """Part of Cron object that represent a collection of positive integers."""

    __slots__ = (
        "unit",
        "options",
        "values",
    )

    def __init__(
        self, unit: dict, values: Union[str, list[int]], options: dict
    ):
        self.unit: dict = unit
        self.options: dict = options
        if isinstance(values, str):
            values: list[int] = (
                self.from_string(values) if values != "?" else []
            )
        elif isinstance_check(values, list[int]):
            values: list[int] = self.replace_weekday(values)
        else:
            raise TypeError(f"Invalid type of value in cron part: {values}.")
        unique_values: list[int] = self.out_of_range(
            sorted(dict.fromkeys(values))
        )
        self.values: list[int] = unique_values

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}"
            f"(unit={self.unit}, values={self.to_string()!r})>"
        )

    def __lt__(self, other) -> bool:
        return self.values < other.values

    def __eq__(self, other) -> bool:
        return self.values == other.values

    @property
    def is_weekday(self) -> bool:
        return self.unit["name"] == "weekday"

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
        return len(self.values) == (
            self.unit.get("max") - self.unit.get("min") + 1
        )

    def from_string(self, value: str) -> list[int]:
        """Parses a string as a range of positive integers. The string should
        include only `-` and `,` special strings.

        TODO: support for `L`, `W`, and `#`
        TODO:     if you didn't care what day of the week the 7th was, you
            could enter ? in the Day-of-week field.
        TODO: L : the Day-of-month or Day-of-week fields specifies the last day
            of the month or week.
            DEV: use -1 for represent with L
        TODO: W : In the Day-of-month field, 3W specifies the weekday closest
            to the third day of the month.
        TODO: # : 3#2 would be the second Tuesday of the month,
            the 3 refers to Tuesday because it is the third day of each week.

        .. :example:
            - 0 10 * * ? *
              Run at 10:00 am (UTC) every day

            - 15 12 * * ? *
              Run at 12:15 pm (UTC) every day

            - 0 18 ? * MON-FRI *
              Run at 6:00 pm (UTC) every Monday through Friday

            - 0 8 1 * ? *
              Run at 8:00 am (UTC) every 1st day of the month

            - 0/15 * * * ? *
              Run every 15 minutes

            - 0/10 * ? * MON-FRI *
              Run every 10 minutes Monday through Friday

            - 0/5 8-17 ? * MON-FRI *
              Run every 5 minutes Monday through Friday between 8:00 am and 5:55 pm (UTC)

            - 5,35 14 * * ? *
              Run every day, at 5 and 35 minutes past 2:00 pm (UTC)

            - 15 10 ? * 6L 2002-2005
              Run at 10:15am UTC on the last Friday of each month during the years 2002 to 2005

        """
        interval_list: list[list[int]] = []
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

            if (value_step and not is_int(value_step)) or value_step == "":
                raise ValueError(
                    f'Invalid interval step value {value_step!r} for {self.unit["name"]!r}'
                )

            interval_list.append(self._interval(value_range_list, value_step))
        return [item for sublist in interval_list for item in sublist]

    def replace_alternative(self, value: str) -> str:
        """Replaces the alternative representations of numbers in a string."""
        for i, alt in enumerate(self.unit.get("alt", [])):
            if alt in value:
                value: str = value.replace(alt, str(self.unit["min"] + i))
        return value

    def replace_weekday(
        self, values: Union[list[int], Iterator[int]]
    ) -> list[int]:
        """Replaces all 7 with 0 as Sunday can be represented by both."""
        if self.is_weekday:
            return [0 if value == 7 else value for value in values]
        return list(values)

    def out_of_range(self, values: list[int]) -> list[int]:
        """Return an integer is a value out of range was found, otherwise None."""
        if values:
            if (first := values[0]) < self.unit["min"]:
                raise ValueError(
                    f'Value {first!r} out of range for {self.unit["name"]!r}'
                )
            elif (last := values[-1]) > self.unit["max"]:
                raise ValueError(
                    f'Value {last!r} out of range for {self.unit["name"]!r}'
                )
        return values

    def _parse_range(self, value: str) -> list[int]:
        """Parses a range string."""
        if value == "*":
            return list(self.unit["range"]())
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
        self, values: list[int], step: Optional[int] = None
    ) -> list[int]:
        """Applies an interval step to a collection of values."""
        if not step:
            return values
        elif (_step := int(step)) < 1:
            raise ValueError(
                f'Invalid interval step value {_step!r} for {self.unit["name"]!r}'
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
                self.min == self.unit["min"]
                and (self.max + step) > self.unit["max"]
                and (
                    len(self.values)
                    == (round((self.max - self.min) / step) + 1)
                )
            )
        return False

    def ranges(self) -> list[Union[int, list[int]]]:
        """Returns the range as an array of ranges defined as arrays of positive integers."""
        multi_dim_values = []
        start_number: Optional[int] = None
        for idx, value in enumerate(self.values):
            try:
                next_value: int = self.values[idx + 1]
            except IndexError:
                next_value: int = -1
            if value != (next_value - 1):
                # next_value is not the subsequent number
                if start_number is None:
                    # The last number of the list "self.values" is not in a range
                    multi_dim_values.append(value)
                else:
                    multi_dim_values.append([start_number, value])
                    start_number: Optional[int] = None
            elif start_number is None:
                start_number: Optional[int] = value
        return multi_dim_values

    def to_string(self) -> str:
        """Returns the range as a string."""
        _hash: str = "H" if self.options.get("output_hashes") else "*"

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

    def filler(self, value: int) -> Union[int, str]:
        """Formats weekday and month names as string when the relevant options are set."""
        return (
            self.unit["alt"][value - self.unit["min"]]
            if (
                (
                    self.options["output_weekday_names"]
                    and self.unit["name"] == "weekday"
                )
                or (
                    self.options["output_month_names"]
                    and self.unit["name"] == "month"
                )
            )
            else value
        )


@total_ordering
class CronJob:
    """The Cron Job Converter object that generate datetime dimension of cron job schedule
    format,

            * * * * * <command to execute>

        (i)     minute (0 - 59)
        (ii)    hour (0 - 23)
        (iii)   day of the month (1 - 31)
        (iv)    month (1 - 12)
        (v)     day of the week (0 - 6) (Sunday to Saturday; 7 is also Sunday on some systems)

        This object implement necessary methods and properties for using cron job value with
    other object like Schedule.
        Support special value with `/`, `*`, `-`, `,`, and `?` (in day of month and day of week
    value).

    :ref:
        - https://github.com/Sonic0/cron-converter
        - https://pypi.org/project/python-crontab/
    """

    cron_length: int = 5

    options_defaults: dict = {
        "output_weekday_names": False,
        "output_month_names": False,
        "output_hashes": False,
    }

    def __init__(
        self,
        value: Union[list[list[int]], str],
        *,
        option: Optional[dict] = None,
    ):
        if isinstance(value, str):
            value: list = value.strip().split()
        elif not isinstance_check(value, list[list[int]]):
            raise TypeError(
                f"{self.__class__.__name__} cron value does not support type: {type(value)}."
            )
        if len(value) != self.cron_length:
            raise ValueError(
                f"Invalid cron value does not have length equal {self.cron_length}: {value}."
            )
        self._options: dict[str, bool] = merge_dict(
            self.options_defaults, (option or {})
        )
        self._parts: list[CronPart] = [
            CronPart(unit, values=item, options=self._options)
            for item, unit in zip(value, CRON_UNITS)
        ]
        if self.day == self.dow == []:
            raise ValueError(
                "Invalid cron value when set the `?` on day of month and day of week together"
            )

    def __str__(self):
        return " ".join(str(part) for part in self._parts)

    def __repr__(self):
        return f"<{self.__class__.__name__}(value={self.__str__()!r}, option={self._options})>"

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
    def parts(self) -> list[CronPart]:
        return self._parts

    @property
    def parts_order(self) -> Iterator[CronPart]:
        return reversed(self.parts[:3] + [self.parts[4], self.parts[3]])

    @property
    def minute(self):
        """Return part of minute."""
        return self._parts[0]

    @property
    def hour(self):
        """Return part of hour."""
        return self._parts[1]

    @property
    def day(self):
        """Return part of day."""
        return self._parts[2]

    @property
    def month(self):
        """Return part of month."""
        return self._parts[3]

    @property
    def dow(self):
        """Return part of day of month."""
        return self._parts[4]

    def to_list(self) -> list[list[int]]:
        """Returns the cron schedule as a 2-dimensional list of integers."""
        return [part.values for part in self._parts]

    def schedule(
        self, start_date: Optional[datetime] = None, _tz: Optional[str] = None
    ) -> "CronRunner":
        """Returns the time the schedule would run next."""
        return CronRunner(self, start_date, _tz)


class CronRunner:
    """Create an instance of Date Runner object for datetime generate with
    cron schedule object value.
    """

    __slots__ = (
        "tz_info",
        "date",
        "start_time",
        "cron",
        "reset_flag",
    )

    def __init__(
        self,
        cron: CronJob,
        start_date: Optional[datetime] = None,
        tz_str: Optional[str] = None,
    ):
        self.tz_info = tz.tzutc()
        if tz_str:
            if not (_tz := tz.gettz(tz_str)):
                raise ValueError(f"Invalid timezone: {tz_str}")
            self.tz_info = _tz
        if start_date:
            if not isinstance(start_date, datetime):
                raise ValueError(
                    "Input schedule start time is not a valid datetime object."
                )
            self.tz_info = start_date.tzinfo
            self.date: datetime = start_date
        else:
            self.date: datetime = datetime.now(self.tz_info)

        if self.date.second > 0:
            self.date: datetime = self.date + timedelta(minutes=+1)

        self.start_time: datetime = self.date
        self.cron: CronJob = cron
        self.reset_flag: bool = True

    def reset(self) -> None:
        """Resets the iterator to start time."""
        self.date: datetime = self.start_time
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
        """Returns the time the schedule would run by `next` or `prev`."""
        self.reset_flag: bool = False
        for _ in range(25):
            if all(
                not self._shift_date(mode, reverse)
                for mode in (
                    "month",
                    "day",
                    "hour",
                    "minute",
                )
            ):
                return copy.deepcopy(self.date.replace(second=0, microsecond=0))
        raise RecursionError("Unable to find execution time for schedule")

    def _shift_date(self, mode: str, reverse: bool = False) -> bool:
        """Increments the mode value until matches with the schedule."""
        switch: dict = {
            "month": "year",
            "day": "month",
            "hour": "day",
            "minute": "hour",
        }
        current_value: int = getattr(self.date, switch[mode])
        _addition: callable = (
            (
                lambda: WEEKDAYS.get(self.date.strftime("%a"))
                not in self.cron.dow.values
            )
            if mode == "day"
            else lambda: False
        )
        while (
            getattr(self.date, mode) not in getattr(self.cron, mode).values
        ) or _addition():
            self.date: datetime = next_date(
                self.date, mode=mode, reverse=reverse
            )
            self.date: datetime = replace_date(
                self.date, mode=mode, reverse=reverse
            )
            if current_value != getattr(self.date, switch[mode]):
                return mode != "month"
        return False


__all__ = [
    "Schemas",
    "Statement",
    "CronJob",
    "CronRunner",
]


def test_cron():
    cr1 = CronJob("*/5 * * * *")
    print(cr1)
    cr2 = CronJob("*/5,3,6 9-17/2 * 1-3 1-5")
    print(cr2)
    print(cr1 == cr2)
    print(cr1 < cr2)
    cr = CronJob(
        "*/5,3,6 9-17/2 * 1-3 1-5",
        option={
            "output_hashes": True,
        },
    )
    print(cr)
    cr = CronJob(
        "*/5 9-17/2 * 1-3,5 1-5",
        option={
            "output_weekday_names": True,
            "output_month_names": True,
        },
    )
    print(cr)
    cr = CronJob("*/30 */12 23 */3 *")
    print(cr.to_list())
    sch = cr.schedule(_tz="Asia/Bangkok")
    print(sch.next)
    print(sch.next)
    print(sch.next)
    print(sch.next)
    sch.reset()
    print("-" * 100)
    for _ in range(20):
        print(sch.prev)
    cr = CronJob("0 */12 1 1 0")
    print(cr.to_list())
    cr = CronJob("0 */12 1 ? 0")
    print(cr)


if __name__ == "__main__":
    # _statement = '{{{data}}} from {table} with {{database}} and value from {{schema}} with {{{{condition}}}}'
    # print(Statement(_statement))
    # print(re.sub('({{|}})', '', _statement))
    # a = [y for x in {'a1', 'b2'} for y in x]
    # print(a)
    test_cron()
