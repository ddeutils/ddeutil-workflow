from datetime import datetime, timedelta

import pytest
from ddeutil.workflow.__cron import CronJob
from ddeutil.workflow.conf import config
from ddeutil.workflow.workflow import Release, ReleaseType


def test_release():
    dt: datetime = datetime(2024, 1, 1, 1)
    release = Release(
        date=dt,
        offset=0,
        end_date=dt + timedelta(days=1),
        runner=CronJob("* * * * *").schedule(dt.replace(tzinfo=config.tz)),
    )
    assert repr(release) == repr("2024-01-01 01:00:00")
    assert release.type == ReleaseType.DEFAULT

    release = Release(
        date=dt,
        offset=0,
        end_date=dt + timedelta(days=1),
        runner=CronJob("* * * * *").schedule(dt.replace(tzinfo=config.tz)),
        type="poking",
    )
    assert release.type == ReleaseType.POKE


def test_release_from_dt():
    release = Release.from_dt(dt=datetime(2024, 1, 1, 1))

    assert repr(release) == repr("2024-01-01 01:00:00")
    assert str(release) == "2024-01-01 01:00:00"

    assert release == datetime(2024, 1, 1, 1)
    assert not release < datetime(2024, 1, 1, 1)
    assert not release == 2024010101

    release = Release.from_dt(dt="2024-01-01")

    assert repr(release) == repr("2024-01-01 00:00:00")
    assert str(release) == "2024-01-01 00:00:00"
    assert release == datetime.fromisoformat("2024-01-01")
    assert release < datetime.fromisoformat("2024-01-02")

    # NOTE: Compare type error between Release and int
    with pytest.raises(TypeError):
        assert release < 1

    # NOTE: Compare type error between int and Release
    with pytest.raises(TypeError):
        assert 1 < release

    release = Release.from_dt(dt="2024-01-01 01:02:03")

    assert str(release) == "2024-01-01 01:02:03"
    assert release == datetime.fromisoformat("2024-01-01 01:02:03")

    # NOTE: Raise because type not valid.
    with pytest.raises(TypeError):
        Release.from_dt(19900101)
