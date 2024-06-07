# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

try:
    import polars as pl

    logging.debug(f"Polars version: {pl.__version__}")
except ImportError:
    raise ImportError(
        "Please install polars if you want to use any relate task"
    ) from None
import pyarrow.parquet as pq
from ddeutil.workflow.dataset import PolarsCsv, PolarsParq
from ddeutil.workflow.utils import tag


def polars_dtype():
    return {
        "str": pl.Utf8,
        "int": pl.Int32,
    }


@tag("polars-dir", name="el-csv-to-parquet")
def csv_to_parquet_dir(
    source: str,
    sink: str,
    conversion: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Extract Load data from CSV to Parquet file.

    :param source:
    :param sink:
    :param conversion:
    """
    print("Start EL for CSV to Parquet with Polars Engine")
    print("---")
    # STEP 01: Read the source data to Polars.
    src_dataset: PolarsCsv = PolarsCsv.from_loader(name=source, externals={})
    src_df: pl.DataFrame = src_dataset.load()
    print(src_df)

    # STEP 02: Schema conversion on Polars DataFrame.
    conversion: dict[str, Any] = conversion or {}
    if conversion:
        src_df = src_df.with_columns(
            *[pl.col(c).cast(col.type).alias(col.name) for c, col in conversion]
        )
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


@tag("polars-dir-scan", name="el-csv-to-parquet")
def csv_to_parquet_dir_scan(
    source: str,
    sink: str,
    conversion: dict[str, Any] | None = None,
) -> dict[str, int]:
    print("Start EL for CSV to Parquet with Polars Engine")
    print("---")
    # STEP 01: Read the source data to Polars.
    src_dataset: PolarsCsv = PolarsCsv.from_loader(name=source, externals={})
    src_df: pl.LazyFrame = src_dataset.scan()

    if conversion:
        ...

    sink = PolarsParq.from_loader(name=sink, externals={})
    pq.write_to_dataset(
        table=src_df.collect().to_arrow(),
        root_path=f"{sink.conn.endpoint}/{sink.object}",
        compression="snappy",
        basename_template=f"{sink.object}-{uuid4().hex}-{{i}}.snappy.parquet",
    )
    return {"records": src_df.select(pl.len()).collect().item()}
