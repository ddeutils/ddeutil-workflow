from typing import Any

from ddeutil.model.datasets.col import Col
from pydantic import BaseModel, Field


class Source(BaseModel):
    conn: str


class EL(BaseModel):
    source: dict[str, Any] = Field(default_factory=dict)
    conversion: dict[str, Col] = Field(default_factory=dict)
    sink: dict[str, Any] = Field(default_factory=dict)


class PostgresToDelta(EL): ...
