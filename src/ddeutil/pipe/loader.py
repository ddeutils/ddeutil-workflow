# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import copy
import urllib.parse
from functools import cached_property
from typing import Any

from ddeutil.core import (
    clear_cache,
    getdot,
    hasdot,
    import_string,
    setdot,
)
from ddeutil.io import Params, Register
from ddeutil.io.__base import YamlEnvFl
from ddeutil.io.exceptions import ConfigNotFound
from ddeutil.io.utils import map_func_to_str
from fmtutil import Datetime
from typing_extensions import Self

from .__types import DictData, TupleStr
from .exceptions import ConfigArgumentError

YamlEnvQuote = YamlEnvFl
YamlEnvQuote.prepare = staticmethod(lambda x: urllib.parse.quote_plus(str(x)))


class BaseLoad:
    """Base configuration data loading object for load config data from
    `cls.load_stage` stage. The base loading object contain necessary
    properties and method for type object.

    :param data: dict : A configuration data content with fix keys, `name`,
        `fullname`, and `data`.
    :param params: Optional[dict] : A parameters mapping for some
        subclass of loading use.
    """

    load_prefixes: TupleStr = ("conn", )
    load_datetime_name: str = "audit_date"
    load_datetime_fmt: str = "%Y-%m-%d %H:%M:%S"

    data_excluded: TupleStr = ("version", "updt")
    option_key: TupleStr = ("parameters", )
    datetime_key: TupleStr = ("endpoint", )

    @classmethod
    def from_register(
        cls,
        name: str,
        params: Params,
        externals: DictData,
    ) -> Self:
        """Catalog load configuration

        :param name: A name of config data catalog that can register.
        :type name: str
        :param params: A params object.
        :type params: Params
        :param externals: A external parameters
        """
        try:
            rs: Register = Register(
                name=name,
                stage=params.stage_final,
                params=params,
                loader=YamlEnvQuote,
            )
        except ConfigNotFound:
            rs: Register = Register(
                name=name,
                params=params,
                loader=YamlEnvQuote,
            ).deploy(stop=params.stage_final)
        return cls(
            name=rs.name,
            data=rs.data().copy(),
            params=params,
            externals=externals,
        )

    def __init__(
        self,
        name: str,
        data: DictData,
        params: Params,
        externals: DictData | None = None
    ) -> None:
        """Main initialize base config object which get a name of configuration
        and load data by the register object.
        """
        self.name: str = name
        self.__data: DictData = data
        self.params: Params = params
        self.externals: DictData = externals or {}

        # NOTE: Validate step of base loading object.
        if not any(
            self.name.startswith(prefix) for prefix in self.load_prefixes
        ):
            raise ConfigArgumentError(
                "prefix",
                (
                    f"{self.name!r} does not starts with the "
                    f"{self.__class__.__name__} prefixes: "
                    f"{self.load_prefixes!r}."
                ),
            )

    @property
    def updt(self):
        return self.data.get("updt")

    @cached_property
    def _map_data(self) -> DictData:
        """Return configuration data without key in the excluded key set."""
        data: DictData = self.__data.copy()
        rs: DictData = {k: data[k] for k in data if k not in self.data_excluded}

        # Mapping datetime format to string value.
        for _ in self.datetime_key:
            if hasdot(_, rs):
                # Fill format datetime object to any type value.
                rs: DictData = setdot(
                    _,
                    rs,
                    map_func_to_str(
                        getdot(_, rs),
                        Datetime.parse(
                            value=self.externals[self.load_datetime_name],
                            fmt=self.load_datetime_fmt,
                        ).format,
                    ),
                )
        return rs

    @property
    def data(self) -> DictData:
        """Return deep copy of the input data.

        :rtype: DictData
        """
        return copy.deepcopy(self._map_data)

    @clear_cache(attrs=("type", "_map_data"))
    def refresh(self) -> Self:
        """Refresh configuration data. This process will use `deploy` method
        of the register object.
        """
        return self.from_register(
            name=self.name,
            params=self.params,
            externals=self.externals,
        )

    @cached_property
    def type(self):
        """Return object type which implement in `config_object` key."""
        if not (_typ := self.data.get("type")):
            raise ValueError(
                f"the 'type' value: {_typ} does not exists in config data."
            )
        return import_string(f"ddeutil.pipe.{_typ}")


class Conn(BaseLoad):
    """Connection loading class.
    YAML file structure for connection object,

        <connection-alias-name>:
            (format 01)
            type: "<connection-object-type>"
            endpoint: `{protocol}://{user}:{password}@{host}:{port}/{database}`

            (format 02)
            type: "<connection-object-type>"
            host: <host>
            port: <port>
            username: <user>
            password: <password>
            database: <database>

            (optional)
            ssh_tunnel:
                ssh_host: <host>
                ssh_port: <port>
                ssh_user: <user>
                ssh_private_key: <private-key-filepath>
    """

    @cached_property
    def type(self) -> Any:
        return super().type

    def link(self):
        """Return the connection instance."""
        return self.type.from_dict(self.data)


# class Catalog(BaseLoad):
#     """Catalog loading class.
#     YAML file structure for catalog object,
#
#         <catalog-alias-name>:
#
#             (format 01)
#             type: '<catalog-object-type>'
#             connection: <connection-alias-name>
#             endpoint: `{schema}.{table}`
#
#             (format 02)
#             type: '<catalog-object-type>'
#             connection: <connection-alias-name>
#             endpoint: `{sub-path}/{filename}.{file-extension}`
#
#             (optional)
#             schemas:
#                 <column-name>:
#                     alias: <source-column-name>::<data-type>,
#                     nullable: boolean,
#                     pk: boolean,
#                     default: <default-value>,
#                     unique: boolean
#                     ...
#                 <column-name>: ...
#     """
#
#     load_prefix: set = {
#         "catl",
#         "catalog",
#     }
#
#     @property
#     def connection(self) -> Connection:
#         """Return a connection of catalog"""
#         _conn: Union[str, dict] = self.data.get("connection")
#         if not _conn:
#             raise ConfigArgumentError(
#                 "connection", "does not set in Catalog template."
#             )
#         elif isinstance(_conn, str):
#             return Connection.from_catalog(
#                 name=_conn,
#                 parameters=self.parameters,
#             )
#         return Connection.from_dict(
#             name=f"conn_form_{self.name}",
#             content=_conn,
#             parameters=self.parameters,
#         )
#
#     def load(
#         self,
#         limit: Optional[int] = None,
#         option: Optional[dict] = None,
#     ) -> pd.DataFrame:
#         """Return loading object from the catalog type."""
#         with self.connection.connect() as conn:
#             return self.type.from_data(self.data).load(
#                 conn,
#                 limit=limit,
#                 option=option,
#             )
#
#     def save(self, output, option: Optional[dict] = None) -> None:
#         """Saving object to the catalog type from output argument."""
#         with self.connection.connect() as conn:
#             self.type.from_data(self.data).save(output, conn, option=option)
#
#
# class Node(BaseLoad):
#     """Node loading class.
#     YAML file structure for node object,
#
#         <node-alias-name>:
#
#             (format 01)
#             type: '<node-object-type>'
#             input:
#                 - alias: <input-alias-name>
#                   from: <input-catalog-alias-name>
#                   ...
#                 - ...
#             transform:
#                 - alias: <transform-output-alias-name>
#                   input: [<input-alias-name>, ...]
#                   actions:
#                       - type: <action-object-type>
#                         ...
#                       - ...
#                 - ...
#             output:
#                 - from: <input-alias-name>
#                   to: <output-catalog-alias-name>
#                   ...
#                 - ...
#     """
#
#     load_prefix: set = {
#         "node",
#         "trans",
#         "transform",
#     }
#
#     datetime_key: set = {
#         "input",
#         "output",
#     }
#
#     def catalog(self, name: Union[str, dict]) -> Catalog:
#         """Return Catalog object."""
#         if isinstance(name, str):
#             return Catalog.from_catalog(name, parameters=self.parameters)
#         return Catalog.from_dict(
#             name=f"catl_form_{self.name}",
#             content=name,
#             parameters=self.parameters,
#         )
#
#     def _map_catalog(
#         self, mappings: dict, alias: str, data: str
#     ) -> Dict[str, dict]:
#         """Return mapping of the Catalog object and parameters."""
#         return {
#             mapping.pop(alias): {
#                 "data": self.catalog(name=mapping.pop(data)),
#                 "params": mapping,
#             }
#             for mapping in mappings
#         }
#
#     @property
#     def loading(self) -> Dict[str, dict]:
#         """Return loading mapping with Catalog object"""
#         return self._map_catalog(
#             mappings=self.data.get("input", {}), alias="alias", data="from"
#         )
#
#     @property
#     def saving(self) -> Dict[str, dict]:
#         """Return saving mapping with Catalog object"""
#         return self._map_catalog(
#             mappings=self.data.get("output", {}), alias="from", data="to"
#         )
#
#     def catch(
#         self,
#         source: Optional[dict] = None,
#     ) -> Any:
#         """Return output of node transform."""
#         # TODO: apply source parameter for override input mapping.
#         return self.type.from_data(
#             {
#                 "input": (source or self.loading),
#                 "transform": self.data.get("transform", []),
#             }
#         ).runner(catch=True)
#
#     def deploy(
#         self,
#         source: Optional[dict] = None,
#         sink: Optional[dict] = None,
#     ) -> None:
#         """Deploy node transform to saving catalog."""
#         # TODO: apply source and sick parameters for override input and output mapping.
#         return self.type.from_data(
#             {
#                 "input": (source or self.loading),
#                 "output": (sink or self.saving),
#                 "transform": self.data.get("transform", []),
#             }
#         ).runner(catch=False)
#
#
# class Schedule(BaseLoad):
#     """Schedule loading class
#     YAML file structure for schedule object,
#
#         <schedule-alias-name>:
#
#             (format 01)
#             type: '<schedule-object-type>'
#             cron: <cron>
#
#     """
#
#     load_prefix: set = {
#         "schd",
#         "schedule",
#     }
#
#     @property
#     def cronjob(self) -> CronJob:
#         """Return the schedule instance."""
#         return self.type.from_data(self.data).cron
#
#     def generate(self, start: str) -> CronRunner:
#         return self.type.from_data(self.data).schedule(start)
#
#
# StatusItem: Type = Tuple[int, Optional[str]]
#
#
# class Status(enum.IntEnum):
#     """Status enumerations, which are a set of symbolic names (members)
#     bound to unique, constant values
#
#     :usage:
#         >>> for sts in Status:
#         ...    print(f"Status name: {sts.name!r} have value: {sts.value}")
#         Status name: 'READY' have value: -1
#         Status name: 'SUCCESS' have value: 0
#         Status name: 'FAILED' have value: 1
#         Status name: 'PROCESSES' have value: 2
#
#         >>> Status['SUCCESS']
#         <Status.SUCCESS: (0, 'Successful')>
#
#         >>> Status(2)
#         <Status.PROCESSES: (2, 'Processing')>
#
#         >>> isinstance(Status.SUCCESS, Status)
#         True
#
#         >>> Status.SUCCESS is Status.FAILED
#         False
#
#         >>> for sts in Status:
#         ...     if sts <= Status.FAILED:
#         ...         print(sts)
#         READY
#         SUCCESS
#         FAILED
#     """
#
#     READY: StatusItem = -1, "Ready"
#     SUCCESS: StatusItem = 0, "Successful"
#     DONE: StatusItem = 0, "Successful"
#     FAILED: StatusItem = 1, "Error"
#     ERROR: StatusItem = 1, "Error"
#     PROCESSES: StatusItem = 2, "Processing"
#     WAITING: StatusItem = 2, "Processing"
#
#     def __new__(cls, value, *args, **kwargs):
#         obj = int.__new__(cls, value)
#         obj._value_ = value
#         return obj
#
#     def __init__(self, _: int, desc: Optional[str] = None):
#         self._description_: str = desc or self.name
#
#     def __repr__(self):
#         return (
#             f"<{self.__class__.__name__}.{self.name}: "
#             f"({self.value}, {self.desc!r})>"
#         )
#
#     def __str__(self):
#         return self.name
#
#     @property
#     def desc(self):
#         return self._description_
#
#
# class Pipeline(BaseLoad):
#     """Pipeline loading class"""
#
#     load_prefix: set = {
#         "pipe",
#         "pipeline",
#     }
#
#     def schedule(self) -> Schedule:
#         ...
#
#     def node(self) -> Node:
#         ...
#
#     def generate_report(self, style: str):
#         ...
#
#     def tracking(self):
#         ...
#
#     def process(self):
#         ...
#
#
# __all__ = [
#     "Connection",
#     "Catalog",
#     "Node",
#     "Schedule",
#     "Pipeline",
# ]
#
#
# def test_conn_search():
#     conn_local = Connection("demo:conn_local_data_with_datetime")
#     print(conn_local.data.pop("endpoint"))
#     conn_local.option("parameters", {"audit_date": "2021-01-01 00:00:00"})
#     print(conn_local.data.pop("endpoint"))
#
#
# def test_node_load():
#     node_test = Node("demo:node_seller_prepare")
#     node_test.option("parameters", {"audit_date": "2021-01-01 00:00:00"})
#     print(node_test.saving)
#     results = node_test.catch()
#     for k in results:
#         print(f'Result {k}: {"-" * 120}')
#         print(results[k])
#         # print(results[k].dtypes)
#     print(node_test.parameters)
#     # node_test.deploy()
#
#
# def test_node_trans():
#     node_test = Node("demo:node_seller_transform")
#     node_test.option("parameters", {"audit_date": "2021-01-01 00:00:00"})
#     print(node_test.loading)
#     results = node_test.catch()
#     for k in results:
#         print(f'Result {k}: {"-" * 120}')
#         print(results[k])
#         # print(results[k].dtypes)
#     # node_test.deploy()
#
#
# if __name__ == "__main__":
#     test_conn_search()
#     # test_node_load()
#     # test_node_trans()
