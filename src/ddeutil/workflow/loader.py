# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from functools import cached_property
from typing import Any, ClassVar, TypeVar

from ddeutil.core import (
    getdot,
    hasdot,
    import_string,
)
from ddeutil.io import (
    ConfigNotFound,
    Params,
    PathSearch,
    YamlEnvFl,
)
from pydantic import BaseModel

from .__regex import RegexConf
from .__types import DictData

T = TypeVar("T")
BaseModelType = type[BaseModel]
AnyModel = TypeVar("AnyModel", bound=BaseModel)


class SimLoad:
    """Simple Load Object that will search config data by name.

    :param name: A name of config data that will read by Yaml Loader object.
    :param params: A Params model object.
    :param externals: An external parameters

    Note:
        The config data should have ``type`` key for engine can know what is
    config should to do next.
    """

    import_prefix: ClassVar[str] = "ddeutil.workflow"

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
    def type(self) -> BaseModelType:
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

    def load(self) -> AnyModel:
        return self.type.model_validate(self.data)


class Loader(SimLoad):
    """Main Loader Object that get the config `yaml` file from current path.

    :param name: A name of config data that will read by Yaml Loader object.
    :param externals: An external parameters
    """

    conf_name: ClassVar[str] = "workflows-conf"

    def __init__(
        self,
        name: str,
        externals: DictData,
        *,
        path: str | None = None,
    ) -> None:
        self.data: DictData = {}

        # NOTE: import params object from specific config file
        params: Params = self.config(path)

        super().__init__(name, params, externals)

    @classmethod
    def config(cls, path: str | None = None) -> Params:
        """Load Config data from ``workflows-conf.yaml`` file."""
        return Params.model_validate(
            YamlEnvFl(path or f"./{cls.conf_name}.yaml").read()
        )


def map_params(value: Any, params: dict[str, Any]) -> Any:
    """Map caller value that found from ``RE_CALLER`` regex.

    :rtype: Any
    :returns: An any getter value from the params input.
    """
    if isinstance(value, dict):
        return {k: map_params(value[k], params) for k in value}
    elif isinstance(value, (list, tuple, set)):
        return type(value)([map_params(i, params) for i in value])
    elif not isinstance(value, str):
        return value

    if not (found := RegexConf.RE_CALLER.search(value)):
        return value

    # NOTE: get caller value that setting inside; ``${{ <caller-value> }}``
    caller: str = found.group("caller")
    if not hasdot(caller, params):
        raise ValueError(f"params does not set caller: {caller!r}")
    getter: Any = getdot(caller, params)

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
