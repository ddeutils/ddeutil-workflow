import datetime as dt
from typing import Any


def datetime(value: Any) -> dt.datetime:
    if isinstance(value, dt.datetime):
        return value
    elif isinstance(value, dt.date):
        return dt.datetime(value.year, value.month, value.day)
    if value is None:
        return dt.datetime.now(dt.timezone.utc)
    elif not isinstance(value, str):
        raise ValueError(
            f"Value that want to convert to datetime does not support for "
            f"type: {type(value)}"
        )
    return dt.datetime.fromisoformat(value)


def string(value: Any) -> str:
    return str(value)


def integer(value: Any) -> int:
    if not isinstance(value, int):
        try:
            return int(str(value))
        except TypeError as err:
            raise ValueError(
                f"Value that want to convert to integer does not support for "
                f"type: {type(value)}"
            ) from err
    return value
