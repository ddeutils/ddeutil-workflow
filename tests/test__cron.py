from datetime import datetime, timedelta, timezone
from functools import partial
from zoneinfo import ZoneInfo

import ddeutil.workflow.__cron as cron
import pytest

from tests.utils import str2dt


def test_timezone():
    jan1_in_utc = datetime.fromisoformat("2024-01-01T08:00").replace(
        tzinfo=ZoneInfo("UTC")
    )

    assert timedelta(0) == ZoneInfo("UTC").utcoffset(jan1_in_utc)

    jan1_in_utc = datetime.fromisoformat("2024-01-01T08:00").replace(
        tzinfo=timezone.utc
    )

    assert timedelta(0) == timezone.utc.utcoffset(jan1_in_utc)


def test_cron_cron_part():
    cron_part = cron.CronPart(
        unit=cron.Unit(
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
        values="3,5-8",
        options=cron.Options(),
    )
    assert [3, 5, 6, 7, 8] == cron_part.values
    assert repr(cron_part) == (
        "CronPart(unit=<class 'ddeutil.workflow.__cron.Unit'>(name='month', "
        "range=functools.partial(<class 'range'>, 1, 13),min=1, max=12, "
        "alt=['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', "
        "'OCT', 'NOV', 'DEC']), values='3,5-8')"
    )

    cron_part = cron.CronPart(cron.CRON_UNITS[1], [1, 12], cron.Options())
    assert [1, 12] == cron_part.values
    assert cron_part > [1]
    assert cron_part == [1, 12]

    with pytest.raises(ValueError):
        cron.CronPart(cron.CRON_UNITS[1], [45], cron.Options())

    with pytest.raises(TypeError):
        cron.CronPart(cron.CRON_UNITS[1], 45, cron.Options())


def test_cron_cronjob():
    cr1 = cron.CronJob("*/5 * * * *")
    cr2 = cron.CronJob("*/5,3,6 9-17/2 * 1-3 1-5")

    assert str(cr1) == "*/5 * * * *"
    assert str(cr2) == "0,3,5-6,10,15,20,25,30,35,40,45,50,55 9-17/2 * 1-3 1-5"
    assert cr1 != cr2
    assert cr1 < cr2

    cr = cron.CronJob("0 */12 1 ? 0")
    assert str(cr) == "0 0,12 1 ? 0"

    cr = cron.CronJob("*/4 0 1 * 1")
    assert str(cr) == "*/4 0 1 * 1"

    cr = cron.CronJob("*/4 */3 1 * 1")
    assert str(cr) == "*/4 */3 1 * 1"

    with pytest.raises(ValueError):
        cron.CronJob("*/4 */3 1 *")


def test_cron_cronjob_to_list():
    cr = cron.CronJob("0 */12 1 1 0")
    assert cr.to_list() == [[0], [0, 12], [1], [1], [0]]

    cr = cron.CronJob("*/4 */3 1 * 1")
    assert cr.to_list() == [
        [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
        [0, 3, 6, 9, 12, 15, 18, 21],
        [1],
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        [1],
    ]

    cr = cron.CronJob("*/30 */12 23 */3 *")
    assert cr.to_list() == [
        [0, 30],
        [0, 12],
        [23],
        [1, 4, 7, 10],
        [0, 1, 2, 3, 4, 5, 6],
    ]


def test_cron_option():
    cr = cron.CronJob(
        "*/5,3,6 9-17/2 * 1-3 1-5",
        option={
            "output_hashes": True,
        },
    )
    assert (
        str(cr) == "0,3,5-6,10,15,20,25,30,35,40,45,50,55 H(9-17)/2 H 1-3 1-5"
    )
    cr = cron.CronJob(
        "*/5 9-17/2 * 1-3,5 1-5",
        option={
            "output_weekday_names": True,
            "output_month_names": True,
        },
    )
    assert str(cr) == "*/5 9-17/2 * JAN-MAR,MAY MON-FRI"


def test_cron_next_previous():
    sch = cron.CronJob("*/30 */12 23 */3 *").schedule(
        date=datetime(2024, 1, 1, 12, tzinfo=ZoneInfo("Asia/Bangkok")),
    )
    t = sch.next
    assert t.tzinfo == str2dt("2024-01-23 00:00:00").tzinfo
    assert f"{t:%Y%m%d%H%M%S}" == "20240123000000"
    assert t == str2dt("2024-01-23 00:00:00")
    assert sch.next == str2dt("2024-01-23 00:30:00")
    assert sch.next == str2dt("2024-01-23 12:00:00")
    assert sch.next == str2dt("2024-01-23 12:30:00")

    sch.reset()

    assert sch.prev == str2dt("2023-10-23 12:30:00")
    assert sch.prev == str2dt("2023-10-23 12:00:00")
    assert sch.prev == str2dt("2023-10-23 00:30:00")
    assert sch.prev == str2dt("2023-10-23 00:00:00")
    assert sch.prev == str2dt("2023-07-23 12:30:00")
    assert sch.prev == str2dt("2023-07-23 12:00:00")
    assert sch.prev == str2dt("2023-07-23 00:30:00")
    assert sch.date == str2dt("2023-07-23 00:30:00")

    sch.reset()

    assert sch.next == str2dt("2024-01-23 00:00:00")
    assert sch.next == str2dt("2024-01-23 00:30:00")

    # sch = cron.CronJob("0 0 23 1 ?").schedule(
    #     date=datetime(2024, 1, 1, 12, tzinfo=ZoneInfo("Asia/Bangkok")),
    # )
    # assert sch.next == str2dt("2025-01-23 00:00:00")
    # assert sch.next == str2dt("2026-01-23 00:00:00")


def test_cron_cronjob_year():
    cr = cron.CronJobYear("*/5 * * * * */8,1999")
    assert str(cr) == (
        "*/5 * * * * 1990,1998-1999,2006,2014,2022,2030,2038,2046,2054,2062,"
        "2070,2078,2086,2094"
    )


def test_cron_next_year():
    sch = cron.CronJob("0 0 1 * *").schedule(
        date=datetime(2024, 10, 1, 12, tzinfo=ZoneInfo("Asia/Bangkok")),
    )
    assert sch.next == str2dt("2024-11-01 00:00:00")
    assert sch.next == str2dt("2024-12-01 00:00:00")
    assert sch.next == str2dt("2025-01-01 00:00:00")


def test_cron_year_next_year():
    sch = cron.CronJobYear("0 0 1 * * *").schedule(
        date=datetime(2024, 10, 1, 12, tzinfo=ZoneInfo("Asia/Bangkok")),
    )
    assert sch.next == str2dt("2024-11-01 00:00:00")
    assert sch.next == str2dt("2024-12-01 00:00:00")
    assert sch.next == str2dt("2025-01-01 00:00:00")


def test_cron_year_next_year_raise():
    sch = cron.CronJobYear("0 0 1 * * 2023").schedule(
        date=datetime(2024, 10, 1, 12, tzinfo=ZoneInfo("Asia/Bangkok")),
    )
    with pytest.raises(cron.CronYearLimit):
        _ = sch.next
