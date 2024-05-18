# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
import abc
from collections.abc import Iterator
from pathlib import Path
from typing import (
    Any,
    NoReturn,
    Optional,
    Union,
)

try:
    import boto3
except ImportError:
    boto3 = None
import sqlalchemy
from ddeutil.core import merge_dict
from sqlalchemy import (
    URL,
    Engine,
    MappingResult,
    make_url,
    text,
)
from sshtunnel import SSHTunnelForwarder

from .exceptions import ConfigArgumentError


class BaseConnABC(abc.ABC):
    """Base Connection Abstract Class that provide the necessary methods for
    any connection instance, so this abstract able to be the Connection
    Protocol.
    """

    @classmethod
    @abc.abstractmethod
    def from_url(cls, *args, **kwargs) -> "BaseConnABC": ...

    @abc.abstractmethod
    def list_objects(self, *args, **kwargs) -> Iterator[Any]: ...

    @abc.abstractmethod
    def exists(self, *args, **kwargs) -> bool: ...

    @abc.abstractmethod
    def remove(self, *args, **kwargs) -> NoReturn: ...

    @abc.abstractmethod
    def upload(self, *args, **kwargs) -> NoReturn: ...

    @abc.abstractmethod
    def download(self, *args, **kwargs) -> Any: ...


class BaseFileStorage(BaseConnABC, abc.ABC):
    """Base File connection that use the endpoint argument for connect to
    the target storage with standard connection string format, like

        {protocol}://{container}/{storage}

    """

    fmt: str = "{protocol}://{container}/{storage}"

    protocol: tuple[str, ...] = ()

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "BaseFileStorage":
        if "endpoint" in data:
            _ep: str = data.pop("endpoint")
            return cls.from_url(
                url=_ep,
                props=data,
            )
        _extract_value = {
            "protocol": data.pop("protocol"),
            "container": data.pop("container"),
            "storage": data.pop("storage", None),
            "props": data,
        }
        return cls(**_extract_value)

    @classmethod
    def from_url(
        cls, url: Union[str, URL], *, props: Optional[dict[str, Any]] = None
    ) -> "BaseFileStorage":
        url: URL = cls._validate_url(url)
        return cls(
            protocol=url.drivername,
            container=url.host,
            storage=url.database,
            props=merge_dict(
                {
                    "username": url.username,
                    "password": url.password,
                    "port": url.port,
                },
                props,
            ),
        )

    @classmethod
    def _validate_url(cls, url: Union[str, URL]) -> URL:
        url: URL = make_url(url) if isinstance(url, str) else url
        if url.query:
            raise ConfigArgumentError(
                "endpoint",
                (
                    "the connection endpoint should not contain any query "
                    "string in the endpoint url."
                ),
            )
        return url

    def __init__(
        self,
        protocol: str,
        container: str,
        storage: Optional[str] = None,
        *,
        props: Optional[dict[str, Any]] = None,
    ):
        self.url: "URL" = URL.create(
            drivername=protocol,
            host=container,
            database=storage,
        )
        self.props: dict[str, Any] = props
        self.validate_protocol()

    def __repr__(self) -> str:
        _p: str = f", props={self.props}" if self.props else ""
        return f"<{self.__class__.__name__}.from_url(url={self.url!r}{_p})>"

    def __str__(self) -> str:
        return str(self.url)

    def validate_protocol(self) -> bool:
        if self.url.drivername not in self.protocol:
            raise ConfigArgumentError(
                "protocol",
                (
                    f"{self.__class__.__name__} does not support for "
                    f"{self.url.drivername} protocol."
                ),
            )


class LocalFileStorage(BaseFileStorage):
    protocol: tuple[str, ...] = (
        "file",
        "local",
    )

    def list_objects(
        self,
        pattern: Optional[str] = None,
    ) -> Iterator[Path]:
        """Return all objects that exists in this endpoint."""
        _p: str = pattern or "*"
        return Path(self.url.database).rglob(_p)

    def exists(self, path: Union[str, Path]) -> bool:
        return (Path(self.url.database) / path).exists()

    def remove(self, *args, **kwargs) -> NoReturn: ...

    def upload(self, *args, **kwargs) -> NoReturn: ...

    def download(self, *args, **kwargs) -> Any: ...


class SFTPStorage(BaseFileStorage):
    """SFTP Storage object.

        SFTP (Secure FTP) is a transferring mechanism called "Secure Shell File
    Transfer Protocol." The SFTP protocol is built upon SSH to establish an
    encrypted tunnel between client and server and transfer files securely
    across insecure networks.
    """

    protocol: tuple[str, ...] = (
        "sftp",
        "ssh",
    )

    def __init__(
        self,
        protocol: str,
        container: str,
        storage: Optional[str] = None,
        *,
        props: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            protocol=protocol,
            container=container,
            storage=storage,
            props=props,
        )

        from .vendors.sftp import WrapSFTPClient

        print(self.props)
        self.sftp_client: WrapSFTPClient = WrapSFTPClient.from_data(
            merge_dict(
                {"hostname": self.url.host},
                self.props.copy(),
            ),
        )

    def list_objects(
        self,
        pattern: Optional[str] = None,
    ) -> Iterator[Path]:
        return self.sftp_client.walk(self.url.database)

    def exists(self, path: str): ...

    def remove(self, *args, **kwargs) -> NoReturn: ...

    def upload(self, *args, **kwargs) -> NoReturn: ...

    def download(self, *args, **kwargs) -> Any: ...


class BaseDB(BaseConnABC, abc.ABC):
    """The Base Database connection system that use the sqlalchemy for engine
    creation. This object will design necessary properties and methods for
    any kind of Database subclass system.

        {protocol}://{username}:{password}@{host}:{port}/{database}

    """

    fmt: str = "{protocol}://{username}:{password}@{host}:{port}/{database}"

    protocol: tuple[str, ...] = ()

    query_flag: bool = False

    @classmethod
    def from_url(
        cls, url: Union[str, URL], *, props: Optional[dict[str, Any]] = None
    ) -> "BaseDB":
        url: URL = cls._validate_url(url)
        return cls(
            protocol=url.drivername,
            host=url.host,
            username=url.username,
            password=url.password,
            database=url.database,
            port=url.port,
            query=url.query,
            props=props,
        )

    @classmethod
    def _validate_url(cls, url: Union[str, URL]) -> URL:
        url: URL = make_url(url) if isinstance(url, str) else url
        return url

    def __init__(
        self,
        protocol: str,
        host: str,
        username: str,
        password: str,
        database: str,
        port: Optional[int] = None,
        query: Optional[Union[tuple[str, ...], str]] = None,
        *,
        props: Optional[dict[str, Any]] = None,
    ) -> None:
        self.url: "URL" = URL.create(
            drivername=protocol,
            host=host,
            username=username,
            password=password,
            database=database,
            port=port,
            query=query,
        )
        self.props: dict[str, Any] = merge_dict(
            {
                "encoding": "utf-8",
                "echo": False,
                "pool_pre_ping": True,
            },
            (props or {}),
        )
        self.validate_protocol()

    def validate_protocol(self) -> bool:
        if self.url.drivername not in self.protocol:
            raise ConfigArgumentError(
                "protocol",
                (
                    f"{self.__class__.__name__} does not support for "
                    f"{self.url.drivername} protocol."
                ),
            )
        if self.url.query and not self.query_flag:
            raise ConfigArgumentError(
                (
                    "url",
                    "query",
                ),
                f"{self.__class__.__name__} should not contain any "
                f"query string in url.",
            )

    # @property
    # def assets(self):
    #     """Return a assets with match with `self.driver_name` key."""
    #     # TODO: filter assets version with `self.asset_version`
    #     assets = AssetConf("src/core/object/assets")
    #     return getattr(assets, self.driver_name)

    @property
    def engine(self) -> Engine:
        if self.is_private:
            self._conn_server = SSHTunnelForwarder(
                **{
                    "ssh_address_or_host": (
                        self._ssh_tunnel["ssh_host"],
                        int(self._ssh_tunnel.get("ssh_port", 22)),
                    ),
                    "ssh_username": self._ssh_tunnel["ssh_user"],
                    "ssh_private_key": self._ssh_tunnel["ssh_private_key"],
                    "remote_bind_address": (
                        self._conn_url.host,
                        int(self._conn_url.port),
                    ),
                    "local_bind_address": (
                        "localhost",
                        int(self._conn_url.port),
                    ),
                }
            )
            if not self._conn_server.is_alive:
                self._conn_server.start()
        return sqlalchemy.create_engine(
            self.bind_url(self._conn_url), **self.properties
        )

    def bind_url(self, url: URL) -> URL:
        """Return URL with binding host if private connection via SSH Tunnel."""
        return (
            URL.create(
                drivername=url.drivername,
                host="localhost",
                username=url.username,
                password=url.password,
                database=url.database,
                port=url.port,
            )
            if self.is_private
            else url
        )

    def execute(self, *args, **kwargs):
        return self._conn_connect.execute(*args, **kwargs)

    def rowcount(self, *args, **kwargs) -> int:
        return self.execute(*args, **kwargs).rowcount

    def select(self, *args, **kwargs) -> MappingResult:
        return self.execute(*args, **kwargs).mappings()

    def columns(self, table: str) -> list:
        """Return the list of all column properties of a table in the RDBMS
        subclass system.
        """
        raise NotImplementedError

    def tables(self) -> list:
        """Return the list of all table in the RDBMS subclass system."""
        raise NotImplementedError

    def table_exists(self, table: str) -> bool:
        """Return True if a input table exists in the RDMS subclass system."""
        raise NotImplementedError

    def get_schema(
        self, table: str, schema: Optional[str] = None
    ) -> tuple[str, str]:
        """Return pair of table and schema."""
        if "." not in table:
            _schema: str = schema or self.default_schema
        else:
            _schema, table = table.rsplit(".", maxsplit=1)
        return _schema, table


class SQLiteDB(BaseDB):
    protocol: tuple[str, ...] = ("sqlite",)

    def columns(self, table: str) -> list:
        with self as conn:
            rows = conn.select(
                text(self.assets.base.show.columns.format(table=table))
            )
            result: list = rows.all()
        return result

    def tables(self) -> list:
        """Return the list of all table in the SQLite database."""
        with self as conn:
            rows = conn.select(text(self.assets.base.show.tables))
            result: list = rows.all()
        return result

    def table_exists(self, table: str) -> bool:
        """Return True if a input table exists in the SQLite database."""
        with self as conn:
            rows = conn.execute(
                text(self.assets.base.exists.table.format(table=table))
            )
            result = rows.fetchone()
        return bool(result[0])
