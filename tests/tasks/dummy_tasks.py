# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import logging
from typing import Any

from ddeutil.workflow.caller import tag
from ddeutil.workflow.result import Result

logger = logging.getLogger("ddeutil.workflow")


@tag("polars-dir", alias="el-csv-to-parquet")
def dummy_task_polars_dir(
    source: str,
    sink: str,
    result: Result,
    conversion: dict[str, Any] | None = None,
) -> dict[str, int]:
    result.trace.info("[HOOK]: el-csv-to-parquet@polars-dir")
    result.trace.debug("... Start EL for CSV to Parquet with Polars Engine")
    result.trace.debug(f"... Reading data from {source}")

    conversion: dict[str, Any] = conversion or {}
    if conversion:
        result.trace.debug("... Start Schema Conversion ...")
    result.trace.debug(f"... Writing data to {sink}")
    return {"records": 1}


@tag("polars-dir-scan", alias="el-csv-to-parquet")
def dummy_task_polars_dir_scan(
    source: str,
    sink: str,
    conversion: dict[str, Any] | None = None,
) -> dict[str, int]:
    logger.info("[HOOK]: el-csv-to-parquet@polars-dir-scan")
    logger.debug("... Start EL for CSV to Parquet with Polars Engine")
    logger.debug("... ---")
    logger.debug(f"... Reading data from {source}")

    conversion: dict[str, Any] = conversion or {}
    if conversion:
        logger.debug("... Start Schema Conversion ...")
    logger.debug(f"... Writing data to {sink}")
    return {"records": 1}


@tag("odbc", alias="mssql-proc")
def dummy_task_odbc_mssql_procedure(_exec: str, params: dict):
    return {"exec": _exec, "params": params}


@tag("raise", alias="return-type-not-valid")
def dummy_task_raise_return_type_not_valid():
    return True


def simple_function():  # pragma: no cov
    return "bar"
