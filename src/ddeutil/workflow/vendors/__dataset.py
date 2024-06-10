# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Optional

from fmtutil import Datetime, FormatterGroupType, make_group
from fmtutil.utils import escape_fmt_group
from pydantic import BaseModel, Field
from typing_extensions import Self

from ..__types import DictData, TupleStr
from ..conn import SubclassConn
from ..loader import Loader

EXCLUDED_EXTRAS: TupleStr = ("type",)
OBJ_FMTS: FormatterGroupType = make_group({"datetime": Datetime})


class BaseDataset(BaseModel):
    """Base Dataset Model. This model implement only loading construction."""

    conn: Annotated[SubclassConn, Field(description="Connection Model")]
    endpoint: Annotated[
        Optional[str],
        Field(description="Endpoint of connection"),
    ] = None
    object: str = Field(description="Dataset object that want to contract")
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

        # NOTE: Override ``endpoint`` value to getter connection data.
        if "endpoint" in loader.data:
            # NOTE: Update endpoint path without Pydantic validator.
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

    def format_object(
        self,
        _object: str | None = None,
        dt: str | datetime | None = None,
    ) -> str:
        """Format the object value that implement datetime"""
        if dt is None:
            dt = datetime.now()
        dt: datetime = (
            dt if isinstance(dt, datetime) else datetime.fromisoformat(dt)
        )
        return (
            OBJ_FMTS({"datetime": dt})
            .format(escape_fmt_group(_object or self.object))
            .replace("\\", "")
        )


class FlDataset(Dataset):

    def exists(self) -> bool:
        return self.conn.find_object(self.object)


class TblDataset(Dataset):

    def exists(self) -> bool:
        return self.conn.find_object(self.object)


class FlDataFrame(Dataset):

    def exists(self) -> bool:
        return self.conn.find_object(self.object)


class TblDataFrame(Dataset): ...
