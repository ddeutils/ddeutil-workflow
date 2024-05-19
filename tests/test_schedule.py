import datetime
from collections.abc import Generator
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from ddeutil.io.param import Params
from ddeutil.workflow.schedule import ScdlBkk


@pytest.fixture(scope="module")
def params(
    conf_path: Path,
    test_path: Path,
    root_path: Path,
) -> Generator[Params, None, None]:
    yield Params.model_validate(
        {
            "engine": {
                "paths": {
                    "conf": conf_path,
                    "data": test_path / ".cache",
                    "root": root_path,
                },
            },
            "stages": {
                "raw": {"format": "{naming:%s}.{timestamp:%Y%m%d_%H%M%S}"},
            },
        }
    )


def test_schedule(params: Params):
    schedule = ScdlBkk.from_loader(
        name="scdl_bkk_every_5_minute",
        params=params,
        externals={},
    )
    assert "Asia/Bangkok" == schedule.tz
    assert "*/5 * * * *" == str(schedule.cronjob)

    start_date: datetime.datetime = datetime.datetime(2024, 1, 1, 12)
    cron_runner = schedule.generate(start=start_date)
    assert cron_runner.date.tzinfo == ZoneInfo(schedule.tz)
    assert cron_runner.date == start_date.astimezone(ZoneInfo(schedule.tz))
