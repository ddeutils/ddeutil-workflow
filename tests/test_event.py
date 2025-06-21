# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from ddeutil.workflow import Crontab, CrontabYear
from ddeutil.workflow.event import CrontabValue, Event, interval2crontab
from pydantic import ValidationError


def test_localize_timezone():
    one_dt = datetime(2024, 1, 1, 17)
    second_dt = datetime(2024, 1, 1, 12)
    assert one_dt > second_dt

    one_dt = one_dt.replace(tzinfo=ZoneInfo("Asia/Bangkok"))
    assert one_dt > second_dt.replace(tzinfo=ZoneInfo("Asia/Bangkok"))
    assert one_dt.astimezone(timezone.utc).replace(tzinfo=None) == datetime(
        2024, 1, 1, 10
    )
    assert one_dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None) == datetime(
        2024, 1, 1, 10
    )
    assert one_dt.astimezone(timezone.utc).replace(tzinfo=None) < second_dt
    assert one_dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None) < second_dt

    bkk = ZoneInfo("Asia/Bangkok")
    dt = datetime(2024, 1, 1, 12, tzinfo=ZoneInfo("UTC"))
    assert dt.replace(tzinfo=None) == datetime(2024, 1, 1, 12)
    bkk_dt = dt.astimezone(bkk)
    assert bkk_dt.replace(tzinfo=None) == datetime(2024, 1, 1, 19)


def test_interval2crontab():
    assert interval2crontab(interval="daily", time="01:30") == "1 30 * * *"
    assert (
        interval2crontab(interval="weekly", day="friday", time="18:30")
        == "18 30 * * 5"
    )
    assert interval2crontab(interval="monthly", time="00:00") == "0 0 1 * *"
    assert (
        interval2crontab(interval="monthly", day="tuesday", time="12:00")
        == "12 0 1 * 2"
    )


def test_event_crontab():
    schedule = Crontab(
        cronjob="*/5,3,6 9-17/2 * 1-3 1-5",
        extras={"output_hashes": True, "other_key": "not_use_value"},
    )
    assert (
        str(schedule.cronjob)
        == "0,3,5-6,10,15,20,25,30,35,40,45,50,55 H(9-17)/2 H 1-3 1-5"
    )

    schedule = Crontab(
        cronjob="*/5 * * * *",
        timezone="Asia/Bangkok",
        extras={},
    )
    assert "Asia/Bangkok" == schedule.tz
    assert "*/5 * * * *" == str(schedule.cronjob)

    start_date: datetime = datetime(2024, 1, 1, 12)
    start_date_bkk: datetime = start_date.astimezone(ZoneInfo(schedule.tz))

    # NOTE: Passing the start datetime object that does not set timezone.
    cron_runner = schedule.generate(start=start_date)

    # NOTE: Check the timezone was changed by schedule object.
    assert cron_runner.date.tzinfo == ZoneInfo(schedule.tz)

    # NOTE: Check the date argument that valid with the input state datetime.
    assert cron_runner.date == start_date_bkk

    assert cron_runner.next == start_date_bkk
    assert cron_runner.next == start_date_bkk + timedelta(minutes=5)
    assert cron_runner.next == start_date_bkk + timedelta(minutes=10)
    assert cron_runner.next == start_date_bkk + timedelta(minutes=15)

    cron_runner.reset()

    assert cron_runner.date == start_date_bkk
    assert cron_runner.prev == start_date_bkk - timedelta(minutes=5)

    with pytest.raises(ValidationError):
        Crontab(cronjob="*/5 * * * *", timezone="Not/Exists")

    with pytest.raises(ValidationError):
        Crontab.model_validate(
            {"cronjob": "*/5 * * * *", "timezone": "Not/Exists"}
        )


def test_event_crontab_from_value():
    schedule = CrontabValue.model_validate(
        {
            "interval": "monthly",
            "day": "monday",
            "time": "12:00",
            "extras": {},
        }
    )
    assert "UTC" == schedule.tz
    assert "12 0 1 * 1" == str(schedule.cronjob)
    gen = schedule.generate("2025-01-01 00:00:00")
    assert f"{gen.date:%Y-%m-%d %H:%M:%S}" == "2024-12-31 17:00:00"
    assert f"{gen.next:%Y-%m-%d %H:%M:%S}" == "2025-09-01 00:12:00"
    assert f"{gen.next:%Y-%m-%d %H:%M:%S}" == "2025-12-01 00:12:00"
    assert f"{gen.next:%Y-%m-%d %H:%M:%S}" == "2026-06-01 00:12:00"

    gen = schedule.generate(datetime(2025, 1, 1))
    assert f"{gen.date:%Y-%m-%d %H:%M:%S}" == "2024-12-31 17:00:00"
    assert f"{gen.next:%Y-%m-%d %H:%M:%S}" == "2025-09-01 00:12:00"
    assert f"{gen.next:%Y-%m-%d %H:%M:%S}" == "2025-12-01 00:12:00"
    assert f"{gen.next:%Y-%m-%d %H:%M:%S}" == "2026-06-01 00:12:00"

    n = schedule.next("2025-01-01 00:00:00")
    assert f"{n.date:%Y-%m-%d %H:%M:%S}" == "2025-09-01 00:12:00"

    schedule = CrontabValue.model_validate(
        {
            "interval": "monthly",
            "day": "monday",
            "time": "12:00",
            "timezone": "Etc/UTC",
            "extras": {},
        }
    )
    assert schedule.tz == "Etc/UTC"
    assert str(schedule.cronjob) == "12 0 1 * 1"

    schedule = CrontabValue.model_validate(
        {
            "interval": "monthly",
            "day": "monday",
            "time": "12:00",
            "tz": "Etc/UTC",
            "extras": {},
        }
    )
    assert schedule.tz == "Etc/UTC"
    assert str(schedule.cronjob) == "12 0 1 * 1"

    with pytest.raises(TypeError):
        schedule.generate(1990)


def test_event_crontab_from_conf():
    schedule = CrontabValue(
        interval="monthly",
        day="monthly",
        time="12:00",
        timezone="Etc/UTC",
    )
    assert schedule.tz == "Etc/UTC"
    assert str(schedule.cronjob) == "12 0 1 * 1"


def test_event_crontab_aws():
    schedule = CrontabYear(
        cronjob="*/5 * * * * 2024",
        timezone="Asia/Bangkok",
        extras={},
    )
    assert schedule.tz == "Asia/Bangkok"
    assert str(schedule.cronjob) == "*/5 * * * * 2024"


def test_event_crontab_every_minute():
    schedule = Crontab.model_validate(
        {"cronjob": "* * * * *", "timezone": "Asia/Bangkok"}
    )
    current: datetime = datetime(2024, 8, 1, 12, 5, 45)
    adjust: datetime = current.replace(second=0, microsecond=0).astimezone(
        tz=ZoneInfo(schedule.tz)
    )
    gen = schedule.generate(adjust)
    assert f"{gen.date:%Y-%m-%d %H:%M:%S}" == "2024-08-01 12:05:00"
    assert f"{gen.next:%Y-%m-%d %H:%M:%S}" == "2024-08-01 12:05:00"
    assert f"{gen.next:%Y-%m-%d %H:%M:%S}" == "2024-08-01 12:06:00"


def test_event_crontab_every_minute_with_second():
    schedule = Crontab.model_validate(
        {"cronjob": "* * * * *", "timezone": "Asia/Bangkok"}
    )
    gen = schedule.next(datetime(2024, 1, 1, 0, 0, 12))
    assert f"{gen.date:%Y-%m-%d %H:%M:%S}" == "2024-01-01 00:01:00"
    assert f"{gen.next:%Y-%m-%d %H:%M:%S}" == "2024-01-01 00:02:00"


def test_event_crontab_every_5_minute_bkk():
    schedule = Crontab.model_validate(
        {"cronjob": "*/5 * * * *", "timezone": "Asia/Bangkok"}
    )
    schedule.generate("2024-01-01 01:12:00")
    schedule.next("2024-01-01 01:12:00")

    with pytest.raises(TypeError):
        schedule.generate(20240101001200)

    with pytest.raises(TypeError):
        schedule.next(20240101001200)


def test_event_crontab_serialize():
    schedule = Crontab.model_validate(
        {"cronjob": "* * * * *", "tz": "Asia/Bangkok"}
    )
    assert schedule.model_dump(by_alias=False, exclude_unset=True) == {
        "cronjob": "* * * * *",
        "tz": "Asia/Bangkok",
    }
    assert schedule.model_dump(by_alias=True, exclude_unset=True) == {
        "cronjob": "* * * * *",
        "timezone": "Asia/Bangkok",
    }

    assert schedule.model_dump(by_alias=True, exclude_unset=False) == {
        "cronjob": "* * * * *",
        "timezone": "Asia/Bangkok",
        "extras": {},
    }


def test_event():
    event = Event.model_validate(
        obj={
            "schedule": [
                {"cronjob": "* * * * *", "timezone": "Asia/Bangkok"},
                {"cronjob": "* * * * * 2025", "timezone": "Asia/Bangkok"},
            ],
        },
    )
    assert len(event.schedule) == 2
