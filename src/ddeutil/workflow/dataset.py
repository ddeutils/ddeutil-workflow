# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from typing import Annotated, Any, Optional

from ddeutil.io import Params
from pydantic import BaseModel, Field
from typing_extensions import Self

try:
    import polars as pl
except ImportError:
    raise ImportError(
        "Please install polars package\n\t\t$ pip install polars"
    ) from None

from .__types import DictData, TupleStr
from .loader import SimLoad

EXCLUDED_EXTRAS: TupleStr = ("type",)


def get_simple_conn(name: str, params: str, externals: dict[str, Any]):
    loader: SimLoad = SimLoad(name, params=params, externals=externals)
    print(loader.data)
    return loader.type().model_validate(loader.data)


class BaseDataset(BaseModel):
    conn: str
    endpoint: Annotated[
        Optional[str],
        Field(description="Endpoint of connection"),
    ] = None
    object: str
    features: list = Field(default_factory=list)
    extras: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_loader(
        cls,
        name: str,
        params: Params,
        externals: DictData,
    ) -> Self:
        """Construct Connection with Loader object with specific config name.

        :param name:
        :param params:
        :param externals:
        """
        loader: SimLoad = SimLoad(name, params=params, externals=externals)
        filter_data: DictData = {
            k: loader.data.pop(k)
            for k in loader.data.copy()
            if k not in cls.model_fields and k not in EXCLUDED_EXTRAS
        }
        return cls.model_validate(
            obj={
                "extras": (
                    loader.data.pop("extras", {}) | filter_data | externals
                ),
                **loader.data,
            }
        )


class DfDataset(BaseDataset): ...


class TblDataset(BaseDataset):

    def exists(self) -> bool: ...


class PandasCSV: ...


class PandasJson: ...


class PandasParq: ...


class PandasDb: ...


class PandasExcel: ...


class PolarsCSV(DfDataset):

    def load(self) -> pl.DataFrame:
        return pl.read_csv(f"local:///{self.endpoint}/{self.object}")


class PolarsParq: ...


class PostgresTbl(TblDataset): ...


class SqliteTbl(TblDataset): ...
