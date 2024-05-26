from functools import partial
from typing import Any

from ddeutil.core import lazy

registries: dict[str, Any] = {
    "el-csv-to-parquet": {
        "polars": lazy("ddeutil.workflow.tasks._polars.csv_to_parquet"),
        "polars-dir": lazy("ddeutil.workflow.tasks._polars.csv_to_parquet_dir"),
    },
}
