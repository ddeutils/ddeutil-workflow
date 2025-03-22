from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from .__types import DictData


class ErrorContext(BaseModel):  # pragma: no cov
    model_config = ConfigDict(arbitrary_types_allowed=True)

    obj: Exception = Field(alias="class")
    name: str = Field(description="A name of exception class.")
    message: str = Field(description="A exception message.")


class StageContext(BaseModel):  # pragma: no cov
    outputs: DictData = Field(default_factory=dict)
    errors: Optional[ErrorContext] = Field(default=None)

    def is_exception(self) -> bool:
        return self.errors is not None


class StrategyContext(BaseModel):  # pragma: no cov
    matrix: DictData = Field(default_factory=dict)
    stages: dict[str, StageContext]
    errors: Optional[ErrorContext] = Field(default=None)

    def is_exception(self) -> bool:
        return self.errors is not None


MapStrategyContext = dict[str, StrategyContext]  # pragma: no cov


class JobStrategyContext(BaseModel):  # pragma: no cov
    strategies: MapStrategyContext
    errors: Optional[ErrorContext] = Field(default=None)

    def is_exception(self) -> bool:
        return self.errors is not None


JobContext = Union[JobStrategyContext, MapStrategyContext]  # pragma: no cov


class WorkflowContext(BaseModel):  # pragma: no cov
    params: DictData = Field(description="A parameterize value")
    jobs: dict[str, JobContext]
    errors: Optional[ErrorContext] = Field(default=None)
