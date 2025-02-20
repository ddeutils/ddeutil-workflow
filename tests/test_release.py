from datetime import datetime

import pytest
from ddeutil.workflow.workflow import Release


def test_release():
    release = Release.from_dt(dt=datetime(2024, 1, 1, 1))

    assert repr(release) == repr("2024-01-01 01:00:00")
    assert str(release) == "2024-01-01 01:00:00"

    assert release == datetime(2024, 1, 1, 1)
    assert not release < datetime(2024, 1, 1, 1)
    assert not release == 2024010101


def test_release_from_dt():
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
