from __future__ import annotations

import inspect
import shutil
from pathlib import Path
from textwrap import dedent

import pytest
from ddeutil.workflow.call import Registry, make_registry


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
            from ddeutil.workflow.call import tag

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


def test_make_registry_not_found():
    rs: dict[str, Registry] = make_registry("not_found")
    assert rs == {}


def test_make_registry_raise(call_function):

    # NOTE: Raise error duplicate tag name, polars-dir, that set in this module.
    with pytest.raises(ValueError):
        make_registry("new_tasks")


@pytest.mark.skip("Skip because it use for local test only.")
def test_inspec_func():

    def demo_func(
        args_1: str, args_2: Path, *args, kwargs_1: str | None = None, **kwargs
    ):  # pragma: no cov
        pass

    ips = inspect.signature(demo_func)
    for k, v in ips.parameters.items():
        print(k)
        print(v)
        print(v.name)
        print(v.annotation, "type:", type(v.annotation))
        print(v.default)
        print(v.kind)
        print("-----")
