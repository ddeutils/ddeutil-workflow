# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import logging
from typing import Any

from ddeutil.workflow.utils import tag


@tag("polars-dir", alias="el-csv-to-parquet")
def dummy_task_polars_dir(
    source: str,
    sink: str,
    conversion: dict[str, Any] | None = None,
) -> dict[str, int]:
    logging.info("[HOOK]: el-csv-to-parquet@polars-dir")
    logging.debug("... Start EL for CSV to Parquet with Polars Engine")
    logging.debug(f"... Reading data from {source}")

    conversion: dict[str, Any] = conversion or {}
    if conversion:
        logging.debug("... Start Schema Conversion ...")
    logging.debug(f"... Writing data to {sink}")
    return {"records": 1}


@tag("polars-dir-scan", alias="el-csv-to-parquet")
def dummy_task_polars_dir_scan(
    source: str,
    sink: str,
    conversion: dict[str, Any] | None = None,
) -> dict[str, int]:
    logging.info("[HOOK]: el-csv-to-parquet@polars-dir-scan")
    logging.debug("... Start EL for CSV to Parquet with Polars Engine")
    logging.debug("... ---")
    logging.debug(f"... Reading data from {source}")

    conversion: dict[str, Any] = conversion or {}
    if conversion:
        logging.debug("... Start Schema Conversion ...")
    logging.debug(f"... Writing data to {sink}")
    return {"records": 1}


@tag("odbc", alias="mssql-proc")
def dummy_task_odbc_mssql_procedure(_exec: str, params: dict):
    return {"exec": _exec, "params": params}


@tag("raise", alias="return-type-not-valid")
def dummy_task_raise_return_type_not_valid():
    return True
