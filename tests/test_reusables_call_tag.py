from __future__ import annotations

import asyncio
import inspect
import shutil
from pathlib import Path
from textwrap import dedent

import pytest
from ddeutil.workflow.reusables import Registry, make_registry


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
    print(rs)


def test_make_registry_not_found():
    rs: dict[str, Registry] = make_registry("not_found")
    assert rs == {}


def test_make_registry_raise(call_function_dup):

    # NOTE: Raise error duplicate tag name, polars-dir, that set in this module.
    with pytest.raises(ValueError):
        make_registry("new_tasks_dup")


@pytest.mark.skip("Skip because it uses for local test only.")
def test_inspec_func():

    def demo_func(
        args_1: str, args_2: Path, *args, kwargs_1: str | None = None, **kwargs
    ):  # pragma: no cov
        pass

    assert inspect.isfunction(demo_func)

    ips = inspect.signature(demo_func)
    for k, v in ips.parameters.items():
        print(k)
        print(ips.parameters[k].default)
        print(v)
        print(v.name)
        print(v.annotation, "type:", type(v.annotation))
        print(v.default)
        print(v.kind, " (", type(v.kind), ")")
        print("-----")

    async def ademo_func(
        args_1: str, args_2: Path, *args, kwargs_1: str | None = None, **kwargs
    ):  # pragma: no cov
        await asyncio.sleep(0.1)
        pass

    print(inspect.isfunction(ademo_func))
    print(inspect.isasyncgenfunction(ademo_func))
    print(inspect.isasyncgen(ademo_func))
    print(inspect.iscoroutinefunction(ademo_func))

    # ips = inspect.signature(demo_func)
    # for k, v in ips.parameters.items():
    #     print(k)
    #     print(ips.parameters[k].default)
    #     print(v)
    #     print(v.name)
    #     print(v.annotation, "type:", type(v.annotation))
    #     print(v.default)
    #     print(v.kind, " (", type(v.kind), ")")
    #     print("-----")
