# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fmtutil import Datetime, FormatterGroupType, make_group
from pydantic import BaseModel, Field

try:
    import polars as pl
except ImportError:
    raise ImportError(
        "Please install polars package\n\t\t$ pip install polars"
    ) from None

from ..__types import TupleStr
from .__dataset import FlDataFrame, TblDataFrame

EXCLUDED_EXTRAS: TupleStr = ("type",)
OBJ_FMTS: FormatterGroupType = make_group({"datetime": Datetime})


class PolarsCsvArgs(BaseModel):
    """CSV file should use format rfc4180 as CSV standard format.

    docs: [RFC4180](https://datatracker.ietf.org/doc/html/rfc4180)
    """

    header: bool = True
    separator: str = ","
    skip_rows: int = 0
    encoding: str = "utf-8"


class PolarsCsv(FlDataFrame):
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


class PolarsJson(FlDataFrame):

    def load(
        self,
        _object: str | None = None,
        options: dict[str, Any] | None = None,
        *,
        dt: str | datetime | None = None,
    ):
        """Load Json file to Polars Dataframe with ``read_json`` method."""
        # FIXME: Load Json does not support for the fsspec file url.
        return pl.read_json(
            f"{self.conn.endpoint}/"
            f"{self.format_object(_object or self.object, dt=dt)}",
            **(options or {}),
        )

    def save(
        self,
        df: pl.DataFrame,
        _object: str | None = None,
        options: dict[str, Any] | None = None,
    ): ...


class PolarsNdJson(FlDataFrame): ...


class PolarsParqArgs(BaseModel):
    compression: Optional[str] = None
    use_pyarrow: bool = False
    pyarrow_options: dict[str, Any] = Field(default_factory=dict)


class PolarsParq(FlDataFrame):
    extras: PolarsParqArgs

    def save_options(self):
        excluded: list[str] = []
        if not self.extras.pyarrow_options:
            excluded.append("pyarrow_options")
        return self.extras.model_dump(exclude=excluded)

    def save(
        self,
        df: pl.DataFrame,
        _object: str | None = None,
        options: dict[str, Any] | None = None,
    ):
        print(
            f"Start write parquet to "
            f"{self.conn.endpoint}/{_object or self.object}"
        )
        return df.write_parquet(
            f"{self.conn.endpoint}/{_object or self.object}",
            **(self.save_options() | (options or {})),
        )


class PolarsPostgres(TblDataFrame): ...
