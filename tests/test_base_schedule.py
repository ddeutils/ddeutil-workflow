import ddeutil.pipe.__schedule as schedule


def test_schedule_cronjob():
    cr1 = schedule.CronJob("*/5 * * * *")
    cr2 = schedule.CronJob("*/5,3,6 9-17/2 * 1-3 1-5")

    assert str(cr1) == "*/5 * * * *"
    assert str(cr2) == "0,3,5-6,10,15,20,25,30,35,40,45,50,55 9-17/2 * 1-3 1-5"
    assert cr1 != cr2
    assert cr1 < cr2

    cr = schedule.CronJob(
        "*/5,3,6 9-17/2 * 1-3 1-5",
        option={
            "output_hashes": True,
        },
    )
    assert (
        str(cr) == "0,3,5-6,10,15,20,25,30,35,40,45,50,55 H(9-17)/2 H 1-3 1-5"
    )
    cr = schedule.CronJob(
        "*/5 9-17/2 * 1-3,5 1-5",
        option={
            "output_weekday_names": True,
            "output_month_names": True,
        },
    )
    print(cr)
    cr = schedule.CronJob("*/30 */12 23 */3 *")
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
    cr = schedule.CronJob("0 */12 1 1 0")
    print(cr.to_list())
    cr = schedule.CronJob("0 */12 1 ? 0")
    print(cr)
