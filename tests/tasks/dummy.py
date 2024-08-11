# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from typing import Any

from ddeutil.workflow.utils import tag


@tag("polars-dir", name="el-csv-to-parquet")
def dummy_task_1(
    source: str,
    sink: str,
    conversion: dict[str, Any] | None = None,
) -> dict[str, int]:
    print("[HOOK]: el-csv-to-parquet@polars-dir")
    print("... Start EL for CSV to Parquet with Polars Engine")
    print(f"... Reading data from {source}")

    conversion: dict[str, Any] = conversion or {}
    if conversion:
        print("... Start Schema Conversion ...")
    print(f"... Writing data to {sink}")
    return {"records": 1}


@tag("polars-dir-scan", name="el-csv-to-parquet")
def dummy_task_2(
    source: str,
    sink: str,
    conversion: dict[str, Any] | None = None,
) -> dict[str, int]:
    print("[HOOK]: el-csv-to-parquet@polars-dir-scan")
    print("... Start EL for CSV to Parquet with Polars Engine")
    print("... ---")
    print(f"... Reading data from {source}")

    conversion: dict[str, Any] = conversion or {}
    if conversion:
        print("... Start Schema Conversion ...")
    print(f"... Writing data to {sink}")
    return {"records": 1}
