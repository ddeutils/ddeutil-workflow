# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from typing import Any

import ddeutil.workflow.dataset as ds


def csv_to_parquet(
    source: str,
    sink: str,
    conversion: dict[str, Any] | None = None,
):
    # STEP 01: Read the source data to Polars.
    source = ds.PolarsCsv.from_loader(name=source, externals={})
    print(source)

    # STEP 02: Schema conversion on Polars DataFrame.
    conversion: dict[str, Any] = conversion or {}
    print(conversion)

    # STEP 03: Write data to parquet file format.
    sink = ds.PolarsParq.from_loader(name=sink, externals={})
    print(sink)
    return "Success CSV to Parquet with Polars engine"
