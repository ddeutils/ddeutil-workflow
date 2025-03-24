from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from .__types import DictData


class ErrorContext(BaseModel):  # pragma: no cov
    model_config = ConfigDict(arbitrary_types_allowed=True)

    obj: Exception = Field(alias="class")
    name: str = Field(description="A name of exception class.")
    message: str = Field(description="A exception message.")


class OutputContext(BaseModel):  # pragma: no cov
    outputs: DictData = Field(default_factory=dict)
    errors: Optional[ErrorContext] = Field(default=None)
    skipped: bool = Field(default=False)

    def is_exception(self) -> bool:
        return self.errors is not None


class StageContext(BaseModel):  # pragma: no cov
    stages: dict[str, OutputContext]
    errors: Optional[ErrorContext] = Field(default=None)

    def is_exception(self) -> bool:
        return self.errors is not None


class MatrixContext(StageContext):  # pragma: no cov
    matrix: DictData = Field(default_factory=dict)


MatrixStageContext = dict[
    str, Union[MatrixContext, StageContext]
]  # pragma: no cov


class StrategyContext(BaseModel):  # pragma: no cov
    strategies: MatrixStageContext
    errors: Optional[ErrorContext] = Field(default=None)

    def is_exception(self) -> bool:
        return self.errors is not None


StrategyMatrixContext = Union[
    StrategyContext, MatrixStageContext
]  # pragma: no cov


class JobContext(BaseModel):  # pragma: no cov
    params: DictData = Field(description="A parameterize value")
    jobs: dict[str, StrategyMatrixContext]
    errors: Optional[ErrorContext] = Field(default=None)
    skipped: bool = Field(default=False)
