from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from ddeutil.workflow.on import Schedule


def test_on():
    schedule = Schedule.from_loader(
        name="bkk_every_5_minute",
        externals={},
    )
    assert "Asia/Bangkok" == schedule.tz
    assert "*/5 * * * *" == str(schedule.cronjob)

    start_date: datetime = datetime(2024, 1, 1, 12)
    start_date_bkk: datetime = start_date.astimezone(ZoneInfo(schedule.tz))
    cron_runner = schedule.generate(start=start_date)
    assert cron_runner.date.tzinfo == ZoneInfo(schedule.tz)
    assert cron_runner.date == start_date_bkk
    assert cron_runner.next == start_date_bkk
    assert cron_runner.next == start_date_bkk + timedelta(minutes=5)
    assert cron_runner.next == start_date_bkk + timedelta(minutes=10)
    assert cron_runner.next == start_date_bkk + timedelta(minutes=15)

    cron_runner.reset()

    assert cron_runner.date == start_date_bkk
    assert cron_runner.prev == start_date_bkk - timedelta(minutes=5)


def test_on_value():
    schedule = Schedule.from_loader(
        name="every_day_noon",
        externals={},
    )
    assert "Etc/UTC" == schedule.tz
    assert "12 0 1 * *" == str(schedule.cronjob)
