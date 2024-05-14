import copy
import urllib.parse
from functools import cached_property
from typing import (
    Any,
    Optional,
    TypedDict,
)

from ddeutil.core import (
    clear_cache,
    getdot,
    hasdot,
    import_string,
    setdot,
)
from ddeutil.io import Params, Register
from ddeutil.io.__base import YamlEnvFl
from ddeutil.io.utils import map_func_to_str
from fmtutil import Datetime

from ..exceptions import ConfigArgumentError, ConfigNotFound

YamlEnvQuote = YamlEnvFl
YamlEnvQuote.prepare = staticmethod(lambda x: urllib.parse.quote_plus(str(x)))


class LoaderData(TypedDict):
    name: str
    fullname: str
    data: dict[str, Any]


class BaseLoader:
    """Base configuration data loading object for load config data from
    `cls.load_stage` stage. The base loading object contain necessary
    properties and method for type object.
    """

    load_prefixes: tuple[str, ...] = tuple("conn")

    load_datetime_name: str = "audit_date"

    load_datetime_fmt: str = "%Y-%m-%d %H:%M:%S"

    data_excluded: tuple[str, ...] = (
        "version",
        "updt",
    )

    option_key: tuple[str, ...] = ("parameters",)

    datetime_key: tuple[str, ...] = ("endpoint",)

    @classmethod
    def from_catalog(
        cls,
        name: str,
        config: Params,
        *,
        refresh: bool = False,
        params: Optional[dict[str, Any]] = None,
    ) -> "BaseLoader":
        """Catalog load configuration

        :param name: A name of config data catalog that can register.
        :type name: str
        :param config:
        :type config: Params
        :param refresh: A refresh boolean flag for loading data from
            base and auto deploy to `cls.load_stage` again if it set be True.
        :type refresh: bool
        :param params:
        """
        if refresh:
            _regis: Register = Register(
                name=name,
                params=config,
                loader=YamlEnvQuote,
            ).deploy(stop=config.stage_final)
        else:
            try:
                _regis: Register = Register(
                    name=name,
                    stage=config.stage_final,
                    params=config,
                    loader=YamlEnvQuote,
                )
            except ConfigNotFound:
                _regis: Register = Register(
                    name=name,
                    params=config,
                    loader=YamlEnvQuote,
                ).deploy(stop=config.stage_final)

        return cls(
            data={
                "name": _regis.name,
                "fullname": _regis.fullname,
                "data": _regis.data().copy(),
            },
            params=params,
            config=config,
        )

    def __init__(
        self,
        data: LoaderData,
        *,
        params: Optional[dict[str, Any]] = None,
        config: Optional[Params] = None,
    ):
        """Main initialize base config object which get a name of configuration
        and load data by the register object.

        :param data: dict : A configuration data content with fix keys, `name`,
            `fullname`, and `data`.
        :param params: Optional[dict] : A parameters mapping for some
            subclass of loading use.
        """
        self.__data: LoaderData = data
        self.__params: dict[str, Any] = params or {}
        self.__config = config

        self.name: str = data["name"]
        self.fullname: str = data["fullname"]
        self.updt = data["data"].get("updt")
        self.version = data["data"].get("version")

        # Validate step of base loading object.
        if not any(
            self.name.startswith(prefix) for prefix in self.load_prefixes
        ):
            raise ConfigArgumentError(
                "prefix",
                (
                    f"{self.name!r} does not starts with the "
                    f"{self.__class__.__name__} prefix value "
                    f"{self.load_prefixes!r}."
                ),
            )

    @cached_property
    def __map_data(self) -> dict[str, Any]:
        """Return configuration data without key in the excluded key set."""
        _data: dict[str, Any] = self.__data["data"].copy()
        _results: dict[str, Any] = {
            k: _data[k] for k in _data if k not in self.data_excluded
        }

        # # Mapping secrets value.
        # if self._ld_secrets:
        #     _results: dict = map_secret(_results)

        # # Mapping function result value.
        # if self._ld_function:
        #     _results: dict = map_function(_results)

        # Mapping datetime format to string value.
        for _ in self.datetime_key:
            if hasdot(_, _results):
                # Fill format datetime object to any type value.
                _get: Any = getdot(_, _results)
                _results: dict = setdot(
                    _,
                    _results,
                    map_func_to_str(
                        _get,
                        Datetime.parse(
                            value=self.__params[self.load_datetime_name],
                            fmt=self.load_datetime_fmt,
                        ).format,
                    ),
                )
        return _results

    @property
    def data(self) -> dict[str, Any]:
        """Return deep copy of configuration data."""
        return copy.deepcopy(self.__map_data)

    @property
    def params(self) -> dict[str, Any]:
        """Return parameters of this loading object"""
        return self.__params

    @clear_cache(attrs=("type", "_map_data"))
    def refresh(self) -> "BaseLoader":
        """Refresh configuration data. This process will use `deploy` method
        of the register object.
        """
        if self.__config:
            return self.__class__.from_catalog(
                name=self.fullname,
                refresh=True,
                params=self.params,
                config=self.__config,
            )
        raise NotImplementedError(
            f"This {self.__class__.__name__} object does not pass data from "
            f"catalog that support refresh method."
        )

    @cached_property
    def type(self):
        """Return object type which implement in `config_object` key."""
        if not (_typ := self.data.get("type")):
            raise ValueError(
                f"the 'type' value: {_typ} does not exists in config data."
            )
        _obj_prefix: str = "ddeutil.node"
        return import_string(f"{_obj_prefix}.{_typ}")
