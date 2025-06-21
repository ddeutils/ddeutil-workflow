import os
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import pytest
from ddeutil.workflow.utils import (
    UTC,
    cut_id,
    dump_all,
    filter_func,
    gen_id,
    get_d_now,
    get_diff_sec,
    get_dt_now,
    make_exec,
    obj_name,
    prepare_newline,
    reach_next_minute,
)
from freezegun import freeze_time
from pydantic import BaseModel, Field


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
    assert "20240101011330000000T1354680202" == gen_id("{}", unique=True)
    assert "20240101011330000000T1354680202" == gen_id(
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
        "url": urlparse("file:./test"),
    }
    assert filter_func(raw_rs) == {
        "echo": "echo",
        "list": ["1", 2, "echo"],
        "dict": {"foo": open, "echo": "echo"},
        "url": urlparse("file:./test"),
    }


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


def test_trace_meta_prepare_msg():
    print()
    rs = prepare_newline(
        "[STAGE]: StageError: PyStage:\nRaise error from python code."
    )
    print(rs)

    rs = prepare_newline(
        "[STAGE]: StageError: PyStage:\nRaise error from python code\n"
        "with newline statement (this is the last line for this message)."
    )
    print(rs)

    rs = prepare_newline("hello world\nand this is newline to echo")
    print(rs)

    rs = prepare_newline("\nhello world")
    assert rs == "hello world"

    rs = prepare_newline("\nhello world\n")
    assert rs == "hello world"


class DumpField(BaseModel):  # pragma: no cov
    name: str = Field(default="foo", alias="field")
    age: int = 10


class DumpModel(BaseModel):  # pragma: no cov
    name: str
    info: DumpField


def test_dump_all():
    assert dump_all({"test": {"foo": "bar"}}) == {"test": {"foo": "bar"}}
    assert dump_all("demo") == "demo"
    assert dump_all(1) == 1
    assert dump_all(urlparse("file:./test")) == urlparse("file:./test")

    assert dump_all(DumpModel(name="model", info=DumpField())) == {
        "name": "model",
        "info": {"name": "foo", "age": 10},
    }

    assert dump_all({"key": DumpModel(name="model", info=DumpField())}) == {
        "key": {"name": "model", "info": {"name": "foo", "age": 10}}
    }

    assert dump_all(
        [
            DumpModel(name="first", info=DumpField()),
            DumpModel(name="second", info=DumpField()),
        ]
    ) == [
        {"name": "first", "info": {"name": "foo", "age": 10}},
        {"name": "second", "info": {"name": "foo", "age": 10}},
    ]

    assert dump_all(
        [
            DumpModel(name="first", info=DumpField()),
            DumpModel(name="second", info=DumpField()),
        ],
        by_alias=True,
    ) == [
        {"name": "first", "info": {"field": "foo", "age": 10}},
        {"name": "second", "info": {"field": "foo", "age": 10}},
    ]


def test_obj_name():
    assert obj_name() is None
    assert obj_name("datetime") == "datetime"
    assert obj_name(datetime) == "datetime"
    assert obj_name(datetime(2025, 1, 1, 1)) == "datetime"
