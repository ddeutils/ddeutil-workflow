# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ddeutil.workflow.result import Result
from ddeutil.workflow.reusables import tag
from pydantic import BaseModel


@tag("polars-dir", alias="el-csv-to-parquet")
def dummy_task_polars_dir(
    source: str,
    sink: str,
    result: Result,
    conversion: Optional[dict[str, Any]] = None,
) -> dict[str, int]:
    result.trace.info("[CALLER]: el-csv-to-parquet@polars-dir")
    result.trace.debug("... Start EL for CSV to Parquet with Polars Engine")
    result.trace.debug(f"... Reading data from {source}")

    conversion: dict[str, Any] = conversion or {}
    if conversion:
        result.trace.debug("... Start Schema Conversion ...")
    result.trace.debug(f"... Writing data to {sink}")
    return {"records": 1}


@tag("polars-dir", alias="async-el-csv-to-parquet")
async def dummy_async_task_polars_dir(
    source: str,
    sink: str,
    result: Result,
    conversion: dict[str, Any] | None = None,
) -> dict[str, int]:
    result.trace.info("[CALLER]: async-el-csv-to-parquet@polars-dir")
    result.trace.debug("... Start EL for CSV to Parquet with Polars Engine")
    result.trace.debug(f"... Reading data from {source}")

    await asyncio.sleep(0.1)
    conversion: dict[str, Any] = conversion or {}
    if conversion:
        result.trace.debug("... Start Schema Conversion ...")
    result.trace.debug(f"... Writing data to {sink}")
    return {"records": 1}


@tag("polars-dir-scan", alias="el-csv-to-parquet")
def dummy_task_polars_dir_scan(
    source: str,
    sink: str,
    result: Result,
    conversion: Optional[dict[str, Any]] | None = None,
) -> dict[str, int]:
    result.trace.info("[CALLER]: el-csv-to-parquet@polars-dir-scan")
    result.trace.debug("... Start EL for CSV to Parquet with Polars Engine")
    result.trace.debug("... ---")
    result.trace.debug(f"... Reading data from {source}")

    conversion: dict[str, Any] = conversion or {}
    if conversion:
        result.trace.debug("... Start Schema Conversion ...")
    result.trace.debug(f"... Writing data to {sink}")
    return {"records": 1}


@tag("odbc", alias="mssql-proc")
def dummy_task_odbc_mssql_procedure(_exec: str, params: dict):
    return {"exec": _exec, "params": params}


@tag("raise", alias="return-type-not-valid")
def dummy_task_raise_return_type_not_valid():
    return True


def simple_function():  # pragma: no cov
    return "bar"


@tag("demo", alias="get-items")
def get_items():
    return {"items": [1, 2, 3, 4]}


class MockModel(BaseModel):  # pragma: no cov
    name: str
    data: dict[str, Any]


@tag("demo", alias="gen-type")
def get_types(
    args1: str,
    args2: Path,
    args3: MockModel,
    *args,
    kwargs1: Optional[datetime] = None,
    kwargs2: Optional[Result] = None,
    **kwargs,
) -> MockModel:
    _ = args1
    _ = args2
    _ = args
    _ = kwargs1
    _ = kwargs2
    result = kwargs["result"]
    result.trace.info("[CALLER]: Test task type.")
    result.trace.info(f"... {type(args3)}: {args3}")
    return MockModel(name="foo", data={"key": "value"})
