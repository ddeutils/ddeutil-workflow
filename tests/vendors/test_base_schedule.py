from datetime import datetime
from zoneinfo import ZoneInfo

import ddeutil.workflow.vendors.__schedule as schedule

from tests.utils import str2dt


def test_scdl_cronjob():
    cr1 = schedule.CronJob("*/5 * * * *")
    cr2 = schedule.CronJob("*/5,3,6 9-17/2 * 1-3 1-5")

    assert str(cr1) == "*/5 * * * *"
    assert str(cr2) == "0,3,5-6,10,15,20,25,30,35,40,45,50,55 9-17/2 * 1-3 1-5"
    assert cr1 != cr2
    assert cr1 < cr2

    cr = schedule.CronJob("0 */12 1 1 0")
    assert cr.to_list() == [[0], [0, 12], [1], [1], [0]]

    cr = schedule.CronJob("0 */12 1 ? 0")
    assert str(cr) == "0 0,12 1 ? 0"


def test_scdl_option():
    cr = schedule.CronJob(
        "*/5,3,6 9-17/2 * 1-3 1-5",
        option={
            "output_hashes": True,
        },
    )
    assert (
        str(cr) == "0,3,5-6,10,15,20,25,30,35,40,45,50,55 H(9-17)/2 H 1-3 1-5"
    )


def test_scdl_next_previous():
    cr = schedule.CronJob(
        "*/5 9-17/2 * 1-3,5 1-5",
        option={
            "output_weekday_names": True,
            "output_month_names": True,
        },
    )
    assert str(cr) == "*/5 9-17/2 * JAN-MAR,MAY MON-FRI"

    cr = schedule.CronJob("*/30 */12 23 */3 *")
    assert cr.to_list() == [
        [0, 30],
        [0, 12],
        [23],
        [1, 4, 7, 10],
        [0, 1, 2, 3, 4, 5, 6],
    ]

    sch = cr.schedule(
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
