# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import copy
import logging
import urllib.parse
from functools import cached_property
from typing import Any, Callable

from ddeutil.core import (
    clear_cache,
    getdot,
    hasdot,
    import_string,
    setdot,
)
from ddeutil.io import (
    ConfigNotFound,
    Params,
    PathSearch,
    Register,
    YamlEnvFl,
    map_func,
)
from ddeutil.io.__conf import UPDATE_KEY, VERSION_KEY
from fmtutil import Datetime
from typing_extensions import Self

from .__regex import RegexConf
from .__types import DictData, TupleStr
from .exceptions import ConfigArgumentError


class YamlEnvQuote(YamlEnvFl):

    @staticmethod
    def prepare(x: str) -> str:
        return urllib.parse.quote_plus(str(x))


class BaseLoad:
    """Base configuration data loading object for load config data from
    `cls.load_stage` stage. The base loading object contain necessary
    properties and method for type object.

    :param data: dict : A configuration data content with fix keys, `name`,
        `fullname`, and `data`.
    :param params: Optional[dict] : A parameters mapping for some
        subclass of loading use.
    """

    # NOTE: Set loading config for inherit
    load_prefixes: TupleStr = ("conn",)
    load_datetime_name: str = "audit_date"
    load_datetime_fmt: str = "%Y-%m-%d %H:%M:%S"

    # NOTE: Set preparing config for inherit
    data_excluded: TupleStr = (UPDATE_KEY, VERSION_KEY)
    option_key: TupleStr = ("parameters",)
    datetime_key: TupleStr = ("endpoint",)

    @classmethod
    def from_register(
        cls,
        name: str,
        params: Params,
        externals: DictData | None = None,
    ) -> Self:
        """Loading config data from register object.

        :param name: A name of config data catalog that can register.
        :type name: str
        :param params: A params object.
        :type params: Params
        :param externals: A external parameters
        :type externals: DictData | None(=None)
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
        externals: DictData | None = None,
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
        return self.data.get(UPDATE_KEY)

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
                    map_func(
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

        :rtype: Self
        """
        return self.from_register(
            name=self.name,
            params=self.params,
            externals=self.externals,
        )

    @cached_property
    def type(self) -> Any:
        """Return object type which implement in `config_object` key."""
        if not (_typ := self.data.get("type")):
            raise ValueError(
                f"the 'type' value: {_typ} does not exists in config data."
            )
        return import_string(f"ddeutil.pipe.{_typ}")


class SimLoad:
    """Simple Load Object that will search config data by name.

    :param name: A name of config data that will read by Yaml Loader object.
    :param params: A Params model object.
    :param externals: An external parameters

    Note:
        The config data should have ``type`` key for engine can know what is
    config should to do next.
    """

    import_prefix: str = "ddeutil.workflow."

    def __init__(
        self,
        name: str,
        params: Params,
        externals: DictData,
    ) -> None:
        self.data: DictData = {}
        for file in PathSearch(params.engine.paths.conf).files:
            if any(file.suffix.endswith(s) for s in ("yml", "yaml")) and (
                data := YamlEnvFl(file).read().get(name, {})
            ):
                self.data = data
        if not self.data:
            raise ConfigNotFound(f"Config {name!r} does not found on conf path")
        self.__conf_params: Params = params
        self.externals: DictData = externals

    @property
    def conf_params(self) -> Params:
        return self.__conf_params

    @cached_property
    def type(self):
        """Return object type which implement in `config_object` key."""
        if not (_typ := self.data.get("type")):
            raise ValueError(
                f"the 'type' value: {_typ} does not exists in config data."
            )
        try:
            # NOTE: Auto adding module prefix if it does not set
            return import_string(f"ddeutil.workflow.{_typ}")
        except ModuleNotFoundError:
            return import_string(f"{_typ}")

    def params(self) -> dict[str, Callable[[Any], Any]]:
        """Return a mapping of key from params and imported value on params."""
        if not (p := self.data.get("params", {})):
            return p

        try:
            return {i: import_string(f"{self.import_prefix}{p[i]}") for i in p}
        except ModuleNotFoundError as err:
            logging.error(err)
            raise err

    def validate_params(self, param: dict[str, Any]) -> dict[str, Any]:
        """Return parameter that want to catch before workflow running."""
        try:
            return {i: caller(param[i]) for i, caller in self.params().items()}
        except KeyError as err:
            logging.error(f"Parameter: {err} does not exists from passing")
            raise err
        except ValueError as err:
            logging.error("Value that passing to params does not valid")
            raise err


def map_caller(value: str, params: dict[str, Any]) -> Any:
    """Map caller value that found from ``RE_CALLER`` regex.

    :returns: Any value that getter of caller receive from the params.
    """
    if not (found := RegexConf.RE_CALLER.search(value)):
        return value
    # NOTE: get caller value that setting inside; ``${{ <caller-value> }}``
    caller = found.group("caller")
    if not hasdot(caller, params):
        raise ValueError(f"params does not set caller: {caller!r}")
    getter = getdot(caller, params)

    # NOTE: check type of vars
    if isinstance(getter, (str, int)):
        return value.replace(found.group(0), str(getter))

    # NOTE:
    #   If type of getter caller does not formatting, it will return origin
    #   value.
    if value.replace(found.group(0), "") != "":
        raise ValueError(
            "Callable variable should not pass other outside ${{ ... }}"
        )
    return getter
