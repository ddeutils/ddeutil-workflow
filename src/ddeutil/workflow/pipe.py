from typing import Any, Optional

from ddeutil.io import Params
from pydantic import BaseModel, Field
from typing_extensions import Self

from .__types import DictData
from .exceptions import PipeArgumentError
from .loader import SimLoad


class Stage(BaseModel):
    name: str
    run: Optional[str] = None


class Job(BaseModel):
    stages: list[Stage]


class Pipeline(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)
    jobs: dict[str, Job]

    @classmethod
    def from_loader(
        cls,
        name: str,
        params: Params,
        externals: DictData,
    ) -> Self:
        loader: SimLoad = SimLoad(name, params=params, externals=externals)
        if "jobs" not in loader.data:
            raise PipeArgumentError("jobs", "Config does not set ``jobs``")
        return cls(
            jobs=loader.data["jobs"],
            params=loader.data.get("params", {}),
        )
