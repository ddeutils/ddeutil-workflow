from functools import partial
from typing import Any

from ddeutil.core import import_string


def lazy(module: str):
    return partial(import_string, module)


registries: dict[str, Any] = {
    "el-csv-to-parquet": {
        "polars": lazy("ddeutil.workflow.tasks._polars.csv_to_parquet")
    },
}
