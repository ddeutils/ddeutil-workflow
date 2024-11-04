from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import yaml
from ddeutil.workflow.on import On, YearOn, interval2crontab
from pydantic import ValidationError


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


def test_on():
    schedule = On.from_loader(name="every_5_minute_bkk", externals={})
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


def test_on_from_value():
    schedule = On.from_value(
        value={
            "interval": "monthly",
            "day": "monday",
            "time": "12:00",
        },
        externals={},
    )
    assert "Etc/UTC" == schedule.tz
    assert "12 0 1 * 1" == str(schedule.cronjob)

    schedule = On.from_value(
        value={
            "interval": "monthly",
            "day": "monday",
            "time": "12:00",
            "timezone": "Etc/UTC",
        },
        externals={},
    )
    assert "Etc/UTC" == schedule.tz
    assert "12 0 1 * 1" == str(schedule.cronjob)

    schedule = On.from_value(
        value={
            "interval": "monthly",
            "day": "monday",
            "time": "12:00",
            "tz": "Etc/UTC",
        },
        externals={},
    )
    assert "Etc/UTC" == schedule.tz
    assert "12 0 1 * 1" == str(schedule.cronjob)


def test_on_from_loader():
    schedule = On.from_loader(
        name="every_day_noon",
        externals={},
    )
    assert "Etc/UTC" == schedule.tz
    assert "12 0 1 * 1" == str(schedule.cronjob)


def test_on_from_loader_raise(test_path):
    test_file = test_path / "conf/demo/02_on_raise.yml"
    with test_file.open(mode="w") as f:
        yaml.dump(
            {
                "every_day_noon_raise": {
                    "type": "scheduler.Workflow",
                    "interval": "monthly",
                    "day": "monday",
                    "time": "12:00",
                }
            },
            f,
        )

    with pytest.raises(ValueError):
        On.from_loader(
            name="every_day_noon_raise",
            externals={},
        )

    with test_file.open(mode="w") as f:
        yaml.dump(
            {
                "every_day_noon_raise": {
                    "type": "on.On",
                }
            },
            f,
        )

    with pytest.raises(ValueError):
        On.from_loader(
            name="every_day_noon_raise",
            externals={},
        )

    with test_file.open(mode="w") as f:
        yaml.dump(
            {
                "every_day_noon_raise": {
                    "type": "on.On",
                    "cronjob": "* * * * *",
                    "timezone": "NotExists",
                }
            },
            f,
        )

    with pytest.raises(ValidationError):
        On.from_loader(
            name="every_day_noon_raise",
            externals={},
        )

    test_file.unlink()


def test_on_aws():
    schedule = YearOn.from_loader(
        name="aws_every_5_minute_bkk",
        externals={},
    )
    assert "Asia/Bangkok" == schedule.tz


def test_on_every_minute():
    schedule = On.from_loader(
        name="every_minute_bkk",
        externals={},
    )
    current: datetime = datetime(2024, 8, 1, 12, 5, 45)
    adjust: datetime = current.replace(second=0, microsecond=0).astimezone(
        tz=ZoneInfo(schedule.tz)
    )
    gen = schedule.generate(adjust)
    print(f"{gen.next:%Y-%m-%d %H:%M:%S}")


def test_on_every_minute_with_second():
    schedule = On.from_loader(name="every_minute_bkk")
    gen = schedule.next(datetime(2024, 1, 1, 0, 0, 1))
    print(gen.date)


def test_on_every_5_minute_bkk():
    schedule = On.from_loader(name="every_5_minute_bkk")
    schedule.generate("2024-01-01 01:12:00")
    schedule.next("2024-01-01 01:12:00")

    with pytest.raises(TypeError):
        schedule.generate(20240101001200)

    with pytest.raises(TypeError):
        schedule.next(20240101001200)


def test_on_serialize():
    schedule = On.from_loader(
        name="every_minute_bkk",
        externals={},
    )
    print(schedule.model_dump())
