# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated, Any, Literal, Optional, TypeVar

from ddeutil.io import Params
from ddeutil.model.conn import Conn as ConnModel
from pydantic import BaseModel, ConfigDict, Field
from pydantic.functional_validators import field_validator
from pydantic.types import SecretStr
from typing_extensions import Self

from .__types import DictData, TupleStr
from .loader import SimLoad

EXCLUDED_EXTRAS: TupleStr = (
    "type",
    "url",
)


class BaseConn(BaseModel):
    """Base Conn (Connection) Model"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # NOTE: This is fields
    dialect: str
    host: Optional[str] = None
    port: Optional[int] = None
    user: Optional[str] = None
    pwd: Optional[SecretStr] = None
    endpoint: str
    extras: Annotated[
        DictData,
        Field(default_factory=dict, description="Extras mapping of parameters"),
    ]

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
        if loader.type != cls:
            raise ValueError(f"Type {loader.type} does not match")
        filter_data: DictData = {
            k: loader.data.pop(k)
            for k in loader.data.copy()
            if k not in cls.model_fields and k not in EXCLUDED_EXTRAS
        }
        if "url" in loader.data:
            url: ConnModel = ConnModel.from_url(loader.data.pop("url"))
            return cls(
                dialect=url.dialect,
                host=url.host,
                port=url.port,
                user=url.user,
                pwd=url.pwd,
                # NOTE:
                #   I will replace None endpoint with memory value for SQLite
                #   connection string.
                endpoint=url.endpoint or "memory",
                # NOTE: This order will show that externals this the top level.
                extras=(url.options | filter_data | externals),
            )
        return cls.model_validate(
            obj={
                "extras": (
                    loader.data.pop("extras", {}) | filter_data | externals
                ),
                **loader.data,
            }
        )

    @field_validator("endpoint")
    def __prepare_slash(cls, value: str) -> str:
        if value.startswith("/"):
            return value[1:]
        return value


class Conn(BaseConn):
    """Conn (Connection) Model that implement any necessary methods. This object
    should be the base for abstraction to any connection model object.
    """

    def ping(self) -> bool:
        """Ping the connection that able to use with this field value."""
        raise NotImplementedError("Ping does not implement")

    def glob(self, pattern: str) -> Iterator[Any]:
        """Return a list of object from the endpoint of this connection."""
        raise NotImplementedError("Glob does not implement")

    def get_spec(self) -> str:
        """Return full connection url that construct from all fields."""
        return f"{self.dialect}:///{self.endpoint}"


class FlSys(Conn):
    """File System Connection."""

    dialect: Literal["local"] = "local"

    def ping(self) -> bool:
        return Path(self.endpoint).exists()

    def glob(self, pattern: str) -> Iterator[Path]:
        yield from Path(self.endpoint).rglob(pattern=pattern)


class SFTP(Conn):
    """SFTP Server Connection."""

    dialect: Literal["sftp"] = "sftp"

    def __client(self):
        from .vendors.sftp_wrapped import WrapSFTP

        return WrapSFTP(
            host=self.host,
            port=self.port,
            user=self.user,
            pwd=self.pwd.get_secret_value(),
        )

    def ping(self) -> bool:
        with self.__client().simple_client():
            return True

    def glob(self, pattern: str) -> Iterator[str]:
        yield from self.__client().walk(pattern=pattern)


class Db(Conn):
    """RDBMS System Connection"""

    def ping(self) -> bool:
        from sqlalchemy import create_engine
        from sqlalchemy.engine import URL, Engine
        from sqlalchemy.exc import OperationalError

        engine: Engine = create_engine(
            url=URL.create(
                self.dialect,
                username=self.user,
                password=self.pwd.get_secret_value() if self.pwd else None,
                host=self.host,
                port=self.port,
                database=self.endpoint,
                query={},
            ),
            execution_options={},
        )
        try:
            return engine.connect()
        except OperationalError as err:
            logging.warning(str(err))
            return False


class SQLite(Db):
    dialect: Literal["sqlite"]


class ODBC(Conn): ...


class Doc(Conn):
    """No SQL System Connection"""


class Mongo(Doc): ...


class SSHCred(BaseModel):
    ssh_host: str
    ssh_user: str
    ssh_password: Optional[SecretStr] = Field(default=None)
    ssh_private_key: Optional[str] = Field(default=None)
    ssh_private_key_pwd: Optional[SecretStr] = Field(default=None)
    ssh_port: int = Field(default=22)


class S3Cred(BaseModel):
    aws_access_key: str
    aws_secret_access_key: SecretStr
    region: str = Field(default="ap-southeast-1")
    role_arn: Optional[str] = Field(default=None)
    role_name: Optional[str] = Field(default=None)
    mfa_serial: Optional[str] = Field(default=None)


class AZServPrinCred(BaseModel):
    tenant: str
    client_id: str
    secret_id: SecretStr


class GoogleCred(BaseModel):
    google_json_path: str


SubclassConn = TypeVar("SubclassConn", bound=Conn)
