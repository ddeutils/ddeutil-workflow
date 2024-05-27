# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from typing import Any
from uuid import uuid4

import polars as pl
import pyarrow.parquet as pq
from ddeutil.workflow.dataset import PolarsCsv, PolarsParq
from ddeutil.workflow.utils import tag


@tag("polars-dir", ref_name="el-csv-to-parquet")
def csv_to_parquet_dir(
    source: str,
    sink: str,
    conversion: dict[str, Any] | None = None,
):
    print("Start EL for CSV to Parquet with Polars Engine")
    print("---")
    # STEP 01: Read the source data to Polars.
    src_dataset: PolarsCsv = PolarsCsv.from_loader(name=source, externals={})
    src_df = src_dataset.load()
    print(src_df)

    # STEP 02: Schema conversion on Polars DataFrame.
    conversion: dict[str, Any] = conversion or {}
    if conversion:
        print("Start Schema Conversion ...")

    # STEP 03: Write data to parquet file format.
    sink = PolarsParq.from_loader(name=sink, externals={})
    pq.write_to_dataset(
        table=src_df.to_arrow(),
        root_path=f"{sink.conn.endpoint}/{sink.object}",
        compression="snappy",
        basename_template=f"{sink.object}-{uuid4().hex}-{{i}}.snappy.parquet",
    )
    return {"records": src_df.select(pl.len()).item()}
