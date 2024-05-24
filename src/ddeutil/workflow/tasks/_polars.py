# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from typing import Any

from ddeutil.workflow.dataset import PolarsCsv


def csv_to_parquet(
    source: str, sink: str, conversion: dict[str, Any] | None = None
):
    source = PolarsCsv.from_loader(name=source, externals={})
    print(source)
    print(sink)
    print(conversion)
    return "Success CSV to Parquet with Polars engine"