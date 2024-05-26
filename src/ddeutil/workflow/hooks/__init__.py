from functools import partial
from typing import Any

from ddeutil.core import import_string


def lazy(module: str):
    return partial(import_string, module)


registries: dict[str, Any] = {
    "postgres-proc": {
        "pysycopg": lazy("ddeutil.workflow.tasks._postgres.postgres_procedure"),
    },
}
