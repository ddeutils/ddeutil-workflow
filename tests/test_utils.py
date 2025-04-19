import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from ddeutil.workflow.utils import (
    NEWLINE,
    UTC,
    batch,
    cut_id,
    filter_func,
    gen_id,
    get_d_now,
    get_diff_sec,
    get_dt_now,
    make_exec,
    reach_next_minute,
    replace_newline,
)
from freezegun import freeze_time


@pytest.fixture(scope="function")
def adjust_config_gen_id():
    origin_simple = os.getenv("WORKFLOW_CORE_GENERATE_ID_SIMPLE_MODE")
    os.environ["WORKFLOW_CORE_GENERATE_ID_SIMPLE_MODE"] = "false"

    yield

    os.environ["WORKFLOW_CORE_GENERATE_ID_SIMPLE_MODE"] = origin_simple


@freeze_time("2024-01-01 01:13:30")
def test_get_dt_now():
    rs = get_dt_now()
    assert rs == datetime(2024, 1, 1, 1, 13, 30, tzinfo=ZoneInfo("UTC"))

    rs = get_dt_now(offset=30)
    assert rs == datetime(2024, 1, 1, 1, 13, 00, tzinfo=ZoneInfo("UTC"))

    rs = get_d_now()
    assert rs == date(2024, 1, 1)


def test_gen_id():
    assert "1354680202" == gen_id("{}")
    assert "1354680202" == gen_id("{}", sensitive=False)


@freeze_time("2024-01-01 01:13:30")
def test_gen_id_unique():
    assert "20240101081330000000T1354680202" == gen_id("{}", unique=True)
    assert "20240101081330000000T1354680202" == gen_id(
        "{}", unique=True, sensitive=False
    )


@freeze_time("2024-01-01 01:13:30")
def test_get_diff_sec():
    assert 2820 == get_diff_sec(datetime(2024, 1, 1, 2, 0, 30, tzinfo=UTC))
    assert 2819 == get_diff_sec(
        datetime(2024, 1, 1, 2, 0, 30, tzinfo=UTC), offset=1
    )


def test_gen_id_not_simple(adjust_config_gen_id):
    assert "99914b932bd37a50b983c5e7c90ae93b" == gen_id("{}")


def test_filter_func():
    _locals = locals()
    exec("def echo():\n\tprint('Hello World')", globals(), _locals)
    _extract_func = _locals["echo"]
    raw_rs = {
        "echo": _extract_func,
        "list": ["1", 2, _extract_func],
        "dict": {
            "foo": open,
            "echo": _extract_func,
        },
    }
    assert filter_func(raw_rs) == {
        "echo": "echo",
        "list": ["1", 2, "echo"],
        "dict": {"foo": open, "echo": "echo"},
    }


def test_batch():
    with pytest.raises(ValueError):
        next(batch(range(10), n=-1))

    assert [[0, 1], [2, 3], [4, 5], [6, 7], [8, 9]] == [
        list(i) for i in batch(range(10), n=2)
    ]


def test_make_exec():
    test_file: str = "./tmp_test_make_exec.txt"

    with open(test_file, mode="w") as f:
        f.write("Hello world")

    make_exec(test_file)

    Path(test_file).unlink()


def test_cut_id():
    assert (
        cut_id(run_id="20240101081330000000T1354680202") == "202401010813680202"
    )
    assert (
        cut_id(run_id="3509917790201200503600070303500") == "350991779020303500"
    )


@freeze_time("2024-01-01 01:13:30")
def test_reach_next_minute():
    assert not reach_next_minute(datetime(2024, 1, 1, 1, 13, 1, tzinfo=UTC))
    assert not reach_next_minute(datetime(2024, 1, 1, 1, 13, 59, tzinfo=UTC))
    assert reach_next_minute(datetime(2024, 1, 1, 1, 14, 1, tzinfo=UTC))

    # NOTE: Raise because this datetime gather than the current time.
    with pytest.raises(ValueError):
        reach_next_minute(datetime(2024, 1, 1, 1, 12, 55, tzinfo=UTC))


def test_replace_newline():
    message: str = (
        f"[JOB]: JobException:{NEWLINE}This is error message from job "
        f"execution."
    )
    print(replace_newline(message))
    assert replace_newline(message) == (
        f"{NEWLINE}[JOB]: JobException:{NEWLINE}| ...\tThis is error message "
        f"from job execution."
    )
    print(replace_newline(replace_newline(message)))
    assert replace_newline(replace_newline(message)) == (
        f"{NEWLINE}{NEWLINE}| ...\t[JOB]: JobException:{NEWLINE}| ...\t| ...\t"
        f"This is error message from job execution."
    )
