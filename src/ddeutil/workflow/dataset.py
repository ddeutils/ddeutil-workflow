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


def get_simple_conn(
    name: str, params: str, externals: dict[str, Any]
) -> SubclassConn:
    loader: SimLoad = SimLoad(name, params=params, externals=externals)
    return loader.type.model_validate(loader.data)


class BaseDataset(BaseModel):
    """Base Dataset Model."""

    conn: Annotated[SubclassConn, Field(description="Connection Model")]
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

        # Note: Override ``endpoint`` value to getter connection data
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


class Dataset(BaseDataset):

    def exists(self) -> bool:
        raise NotImplementedError("Object exists does not implement")


class DfDataset(Dataset): ...


class TblDataset(Dataset):

    def exists(self) -> bool: ...


class PandasCSV: ...


class PandasJson: ...


class PandasParq: ...


class PandasDb: ...


class PandasExcel: ...


class PolarsCSVOptions(BaseModel):
    """CSV file should use format rfc4180 as CSV standard format.

    docs: [RFC4180](https://datatracker.ietf.org/doc/html/rfc4180)
    """

    has_header: bool = True
    separator: str = ","
    skip_rows: int = 0
    encoding: str = "utf-8"


class PolarsCSV(DfDataset):
    extras: PolarsCSVOptions

    def exists(self) -> bool:
        return self.conn.find_object(self.object)

    def load(
        self,
        options: dict[str, Any] | None = None,
    ) -> pl.DataFrame:
        """Load CSV file to Polars Dataframe with ``read_csv`` method."""
        return pl.read_csv(
            f"{self.conn.get_spec()}/{self.object}",
            **(self.extras.model_dump() | (options or {})),
        )

    def save(
        self,
        df: pl.DataFrame,
        options: dict[str, Any] | None = None,
    ) -> None:
        """Save Polars Dataframe to CSV file with ``write_csv`` method."""
        return df.write_csv(
            f"{self.conn.get_spec()}/{self.object}",
            **(self.extras.model_dump() | (options or {})),
        )


class PolarsParq: ...


class PostgresTbl(TblDataset): ...


class SqliteTbl(TblDataset): ...
