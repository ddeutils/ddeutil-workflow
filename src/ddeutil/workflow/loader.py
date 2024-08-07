# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import os
from functools import cached_property
from typing import Any, ClassVar, TypeVar

from ddeutil.core import (
    getdot,
    hasdot,
    import_string,
)
from ddeutil.io import (
    PathData,
    PathSearch,
    YamlEnvFl,
)
from pydantic import BaseModel, Field
from pydantic.functional_validators import model_validator

from .__types import DictData, Re

T = TypeVar("T")
BaseModelType = type[BaseModel]
AnyModel = TypeVar("AnyModel", bound=BaseModel)


class Engine(BaseModel):
    """Engine Model"""

    paths: PathData = Field(default_factory=PathData)
    registry: list[str] = Field(
        default_factory=lambda: [
            "ddeutil.workflow",
        ],
    )

    @model_validator(mode="before")
    def __prepare_registry(cls, values: DictData) -> DictData:
        """Prepare registry value that passing with string type. It convert the
        string type to list of string.
        """
        if (_regis := values.get("registry")) and isinstance(_regis, str):
            values["registry"] = [_regis]
        return values


class Params(BaseModel):
    """Params Model"""

    engine: Engine = Field(
        default_factory=Engine,
        description="A engine mapping values.",
    )


class SimLoad:
    """Simple Load Object that will search config data by name.

    :param name: A name of config data that will read by Yaml Loader object.
    :param params: A Params model object.
    :param externals: An external parameters

    Noted:
        The config data should have ``type`` key for engine can know what is
    config should to do next.
    """

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
            raise ValueError(f"Config {name!r} does not found on conf path")
        self.conf_params: Params = params
        self.externals: DictData = externals

    @cached_property
    def type(self) -> BaseModelType:
        """Return object of string type which implement on any registry. The
        object type
        """
        if not (_typ := self.data.get("type")):
            raise ValueError(
                f"the 'type' value: {_typ} does not exists in config data."
            )
        try:
            # NOTE: Auto adding module prefix if it does not set
            return import_string(f"ddeutil.workflow.{_typ}")
        except ModuleNotFoundError:
            for registry in self.conf_params.engine.registry:
                try:
                    return import_string(f"{registry}.{_typ}")
                except ModuleNotFoundError:
                    continue
            return import_string(f"{_typ}")

    def load(self) -> AnyModel:
        """Parsing config data to the object type for initialize with model
        validate method.
        """
        return self.type.model_validate(self.data)


class Loader(SimLoad):
    """Main Loader Object that get the config `yaml` file from current path.

    :param name: A name of config data that will read by Yaml Loader object.
    :param externals: An external parameters
    """

    conf_filename: ClassVar[str] = "workflows-conf"

    def __init__(
        self,
        name: str,
        externals: DictData,
    ) -> None:
        self.data: DictData = {}

        # NOTE: import params object from specific config file
        params: Params = self.config()

        super().__init__(name, params, externals)

    @classmethod
    def config(cls) -> Params:
        """Load Config data from ``workflows-conf.yaml`` file."""
        root_path: str = os.getenv("WORKFLOW_ROOT_PATH", ".")

        regis: list[str] = []
        if regis_env := os.getenv("WORKFLOW_CORE_REGISTRY"):
            regis = [r.strip() for r in regis_env.split(",")]

        conf_path: str = (
            f"{root_path}/{conf_env}"
            if (conf_env := os.getenv("WORKFLOW_CORE_PATH_CONF"))
            else None
        )
        return Params.model_validate(
            {
                "engine": {
                    "registry": regis,
                    "paths": {
                        "root": root_path,
                        "conf": conf_path,
                    },
                },
            }
        )


def map_params(value: Any, params: dict[str, Any]) -> Any:
    """Map caller value that found from ``RE_CALLER`` regular expression.

    :param value: A value that want to mapped with an params
    :param params: A parameter value that getting with matched regular
        expression.

    :rtype: Any
    :returns: An any getter value from the params input.
    """
    if isinstance(value, dict):
        return {k: map_params(value[k], params) for k in value}
    elif isinstance(value, (list, tuple, set)):
        return type(value)([map_params(i, params) for i in value])
    elif not isinstance(value, str):
        return value

    if not (found := Re.RE_CALLER.search(value)):
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
