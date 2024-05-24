# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from typing import Annotated, Any, Optional

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
from .loader import Loader

EXCLUDED_EXTRAS: TupleStr = ("type",)


def get_simple_conn(
    name: str,
    externals: dict[str, Any],
) -> SubclassConn:
    """Get Connection config with Simple Loader object."""
    loader: Loader = Loader(name, externals=externals)
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
        externals: DictData,
    ) -> Self:
        """Construct Connection with Loader object with specific config name.

        :param name: A name of dataset that want to load from config file.
        :param externals: An external parameters.
        """
        loader: Loader = Loader(name, externals=externals)

        # NOTE: Validate the config type match with current dataset model
        if loader.type != cls:
            raise ValueError(f"Type {loader.type} does not match with {cls}")

        filter_data: DictData = {
            k: loader.data.pop(k)
            for k in loader.data.copy()
            if k not in cls.model_fields and k not in EXCLUDED_EXTRAS
        }

        if "conn" not in loader.data:
            raise ValueError("Dataset config does not set ``conn`` value")

        # NOTE: Start loading connection config
        conn_name: str = loader.data.pop("conn")
        conn_loader: Loader = Loader(conn_name, externals=externals)
        conn_model: SubclassConn = conn_loader.type.from_loader(
            name=conn_name, externals=externals
        )

        # Note: Override ``endpoint`` value to getter connection data
        if "endpoint" in loader.data:
            conn_model.__dict__["endpoint"] = loader.data["endpoint"]
        else:
            loader.data.update({"endpoint": conn_model.endpoint})
        return cls.model_validate(
            obj={
                "extras": (
                    loader.data.pop("extras", {}) | filter_data | externals
                ),
                "conn": conn_model,
                **loader.data,
            }
        )


class Dataset(BaseDataset):

    def exists(self) -> bool:
        raise NotImplementedError("Object exists does not implement")


class DfDataset(Dataset):

    def exists(self) -> bool:
        return self.conn.find_object(self.object)


class TblDataset(Dataset):

    def exists(self) -> bool:
        return self.conn.find_object(self.object)


class PandasCSV: ...


class PandasJson: ...


class PandasParq: ...


class PandasDb: ...


class PandasExcel: ...


class PolarsCsvArgs(BaseModel):
    """CSV file should use format rfc4180 as CSV standard format.

    docs: [RFC4180](https://datatracker.ietf.org/doc/html/rfc4180)
    """

    header: bool = True
    separator: str = ","
    skip_rows: int = 0
    encoding: str = "utf-8"


class PolarsCsv(DfDataset):
    extras: PolarsCsvArgs

    def load_options(self) -> dict[str, Any]:
        return {
            "has_header": self.extras.header,
            "separator": self.extras.separator,
            "skip_rows": self.extras.skip_rows,
            "encoding": self.extras.encoding,
        }

    def load(
        self,
        _object: str | None = None,
        options: dict[str, Any] | None = None,
        *,
        override: bool = False,
    ) -> pl.DataFrame:
        """Load CSV file to Polars DataFrame with ``read_csv`` method."""
        return pl.read_csv(
            f"{self.conn.get_spec()}/{_object or self.object}",
            **(
                (options or {})
                if override
                else (self.load_options() | (options or {}))
            ),
        )

    def scan(
        self,
        _object: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> pl.LazyFrame:
        """Load CSV file to Polars LazyFrame with ``scan_csv`` method."""
        # FIXME: Save Csv does not support for the fsspec file url.
        return pl.scan_csv(
            f"{self.conn.endpoint}/{_object or self.object}",
            **(self.load_options() | (options or {})),
        )

    def save_options(self) -> dict[str, Any]:
        return {
            "include_header": self.extras.header,
            "separator": self.extras.separator,
        }

    def save(
        self,
        df: pl.DataFrame,
        _object: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> None:
        """Save Polars Dataframe to CSV file with ``write_csv`` method."""
        # FIXME: Save Csv does not support for the fsspec file url.
        return df.write_csv(
            f"{self.conn.endpoint}/{_object or self.object}",
            **(self.save_options() | (options or {})),
        )

    def sink(
        self,
        df: pl.LazyFrame,
        _object: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> None:
        """Save Polars Dataframe to CSV file with ``sink_csv`` method."""
        # FIXME: Save Csv does not support for the fsspec file url.
        return df.sink_csv(
            f"{self.conn.endpoint}/{_object or self.object}",
            **(self.save_options() | (options or {})),
        )


class PolarsJson(DfDataset):

    def load(
        self,
        _object: str | None = None,
        options: dict[str, Any] | None = None,
    ):
        """Load Json file to Polars Dataframe with ``read_json`` method."""
        # FIXME: Load Json does not support for the fsspec file url.
        return pl.read_json(
            f"{self.conn.endpoint}/{_object or self.object}",
            **(options or {}),
        )

    def save(
        self,
        df: pl.DataFrame,
        _object: str | None = None,
        options: dict[str, Any] | None = None,
    ): ...


class PolarsNdJson(DfDataset): ...


class PolarsParq(DfDataset):

    def save(
        self,
        df: pl.DataFrame,
        _object: str | None = None,
        options: dict[str, Any] | None = None,
    ):
        return df.write_parquet(...)


class PostgresTbl(TblDataset): ...


class SqliteTbl(TblDataset): ...
