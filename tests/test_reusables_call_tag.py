from __future__ import annotations

import shutil
from pathlib import Path
from textwrap import dedent

import pytest
from ddeutil.workflow.reusables import (
    Registry,
    extract_call,
    make_registry,
)


@pytest.fixture(scope="module")
def call_function(test_path: Path):
    new_tasks_path: Path = test_path / "new_tasks"
    new_tasks_path.mkdir(exist_ok=True)

    with open(new_tasks_path / "__init__.py", mode="w") as f:
        f.write("from .dummy import *\n")

    with open(new_tasks_path / "dummy.py", mode="w") as f:
        f.write(
            dedent(
                """
            from ddeutil.workflow.reusables import tag

            @tag("polars-dir", alias="el-csv-to-parquet")
            def dummy_task(source: str, sink: str) -> dict[str, int]:
                return {"records": 1}

            @tag("polars-dir", alias="el-csv-to-delta")
            def dummy_task_delta(source: str, sink: str) -> dict[str, int]:
                return {"records": util_task()}

            def util_task():
                return 10

            def util_generate():
                return "Foo"

            util_generate.name = "util_generate"
            """.strip(
                    "\n"
                )
            )
        )

    yield

    shutil.rmtree(new_tasks_path)


@pytest.fixture(scope="module")
def call_function_dup(test_path: Path):
    new_tasks_path: Path = test_path / "new_tasks_dup"
    new_tasks_path.mkdir(exist_ok=True)

    with open(new_tasks_path / "__init__.py", mode="w") as f:
        f.write("from .dummy import *\n")

    with open(new_tasks_path / "dummy.py", mode="w") as f:
        f.write(
            dedent(
                """
            from ddeutil.workflow.reusables import tag

            @tag("polars-dir", alias="el-csv-to-parquet")
            def dummy_task(source: str, sink: str) -> dict[str, int]:
                return {"records": 1}

            @tag("polars-dir", alias="el-csv-to-parquet")
            def dummy_task_override(source: str, sink: str) -> dict[str, int]:
                return {"records": 1}
            """.strip(
                    "\n"
                )
            )
        )

    yield

    shutil.rmtree(new_tasks_path)


def test_make_registry(call_function):
    rs: dict[str, Registry] = make_registry("new_tasks")
    assert "util_task" not in rs
    assert "el-csv-to-parquet" in rs
    assert rs["el-csv-to-parquet"]["polars-dir"]().tag == "polars-dir"

    assert "el-csv-to-delta" in rs
    assert rs["el-csv-to-delta"]["polars-dir"]().tag == "polars-dir"


def test_make_registry_from_env():
    rs: dict[str, Registry] = make_registry("tasks")
    assert set(rs.keys()) == {
        "gen-type",
        "get-groups-from-priority",
        "get-items",
        "get-processes-from-group",
        "get-stream-info",
        "private-args-task",
        "private-args-task-not-special",
        "return-type-not-valid",
        "routing-01",
        "routing-02",
        "simple-task",
        "simple-csv-task",
        "simple-task-async",
        "start-process",
        "start-stream",
    }

    # NOTE: multiple tags
    assert "demo" in rs["get-items"]
    assert "demo2" in rs["get-items"]


def test_make_registry_not_found():
    # NOTE: Not found because module does not exist.
    rs: dict[str, Registry] = make_registry("not_found")
    assert rs == {}

    # NOTE: Not found because module does not implement.
    rs: dict[str, Registry] = make_registry(
        "workflow", registries=["ddeutil.workflow"]
    )
    assert rs == {}


def test_make_registry_raise(call_function_dup):

    # NOTE: Raise error duplicate tag name, polars-dir, that set in this module.
    with pytest.raises(ValueError):
        make_registry("new_tasks_dup")


def test_extract_caller():
    func = extract_call("tasks/simple-task@demo")
    call_func = func()
    assert call_func.name == "simple-task"
    assert call_func.tag == "demo"
    assert call_func.mark == "tag"
