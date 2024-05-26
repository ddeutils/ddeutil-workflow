from functools import partial
from typing import Any

from ddeutil.core import lazy

registries: dict[str, Any] = {
    "postgres-proc": {
        "pysycopg": lazy("ddeutil.workflow.tasks._postgres.postgres_procedure"),
    },
}
