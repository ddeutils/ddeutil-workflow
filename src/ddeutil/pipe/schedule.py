from datetime import datetime
from typing import (
    Any,
    Optional,
)

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from .__base.converter import CronJob
from .exceptions import ScheduleArgumentError


class BaseSchedule:
    timezone: str = "UTC"

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "BaseSchedule":
        if (_cron := data.pop("cron", None)) is None:
            raise ScheduleArgumentError(
                "cron", "this necessary key does not exists in data."
            )
        return cls(cron=_cron, props=data)

    def __init__(
        self,
        cron: str,
        *,
        props: Optional[dict[str, Any]] = None,
    ) -> None:
        self.cron: CronJob = CronJob(value=cron)
        self.properties = props or {}

    def schedule(self, start: str):
        _datetime: datetime = datetime.fromisoformat(start).astimezone(
            ZoneInfo(self.timezone)
        )
        return self.cron.schedule(start_date=_datetime)


class BKKSchedule(BaseSchedule):
    timezone: str = "Asia/Bangkok"


class AWSSchedule(BaseSchedule): ...
