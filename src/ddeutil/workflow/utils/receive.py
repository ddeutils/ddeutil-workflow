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
            "Value that want to convert to datetime does not support for type: "
            f"{type(value)}"
        )
    return dt.datetime.fromisoformat(value)


def string(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError(
            "Value that want to convert to string does not support for type: "
            f"{type(value)}"
        )
    return value
