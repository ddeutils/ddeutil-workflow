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
from .conn import SubclassConn
from .loader import SimLoad

EXCLUDED_EXTRAS: TupleStr = ("type",)


def get_simple_conn(name: str, params: str, externals: dict[str, Any]):
    loader: SimLoad = SimLoad(name, params=params, externals=externals)
    print(loader.data)
    return loader.type().model_validate(loader.data)


class BaseDataset(BaseModel):
    """Base Dataset Model."""

    conn: SubclassConn
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

        :param name: A name of dataset that want to load from config file.
        :param params: A params instance that use with the Loader object.
        :param externals: An external parameters.
        """
        loader: SimLoad = SimLoad(name, params=params, externals=externals)
        filter_data: DictData = {
            k: loader.data.pop(k)
            for k in loader.data.copy()
            if k not in cls.model_fields and k not in EXCLUDED_EXTRAS
        }

        if "conn" not in loader.data:
            raise ValueError("Dataset config does not set ``conn`` value")

        # NOTE: Start loading connection config
        conn_loader: SimLoad = SimLoad(
            loader.data.pop("conn"),
            params=params,
            externals=externals,
        )

        if "endpoint" in loader.data:
            conn_loader.data["endpoint"] = loader.data["endpoint"]
        else:
            loader.data.update({"endpoint": conn_loader.data["endpoint"]})

        return cls.model_validate(
            obj={
                "extras": (
                    loader.data.pop("extras", {}) | filter_data | externals
                ),
                "conn": conn_loader.type.model_validate(obj=conn_loader.data),
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
