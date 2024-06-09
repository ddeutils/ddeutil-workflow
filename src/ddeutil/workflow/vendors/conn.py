# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Literal, Optional, TypeVar

from pydantic import BaseModel, Field
from pydantic.types import SecretStr

from .__conn import Conn


class FlSys(Conn):
    """File System Connection."""

    dialect: Literal["local"] = "local"

    def ping(self) -> bool:
        return Path(self.endpoint).exists()

    def glob(self, pattern: str) -> Iterator[Path]:
        yield from Path(self.endpoint).rglob(pattern=pattern)

    def find_object(self, _object: str) -> bool:
        return (Path(self.endpoint) / _object).exists()


class SFTP(Conn):
    """SFTP Server Connection."""

    dialect: Literal["sftp"] = "sftp"

    def __client(self):
        from .wf_sftp import WrapSFTP

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
