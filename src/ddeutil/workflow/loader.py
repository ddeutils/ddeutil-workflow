# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from collections.abc import Iterator
from functools import cached_property
from typing import TypeVar

from ddeutil.core import import_string
from ddeutil.io import PathSearch, YamlFlResolve
from pydantic import BaseModel

from .__types import DictData
from .utils import ConfParams, config

AnyModel = TypeVar("AnyModel", bound=BaseModel)
AnyModelType = type[AnyModel]


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
        params: ConfParams,
        externals: DictData | None = None,
    ) -> None:
        self.data: DictData = {}
        for file in PathSearch(params.engine.paths.conf).files:
            if any(file.suffix.endswith(s) for s in (".yml", ".yaml")) and (
                data := YamlFlResolve(file).read().get(name, {})
            ):
                self.data = data
        if not self.data:
            raise ValueError(f"Config {name!r} does not found on conf path")

        # TODO: Validate the version of template data that mean if version of
        #   Template were change it should raise to upgrade package version.
        #   ---
        #   <pipeline-name>:
        #       version: 1
        #       type: pipeline.Pipeline
        #
        self.conf_params: ConfParams = params
        self.externals: DictData = externals or {}
        self.data.update(self.externals)

    @classmethod
    def find(
        cls,
        obj: object,
        params: ConfParams,
        *,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
    ) -> Iterator[tuple[str, DictData]]:
        """Find all object"""
        exclude: list[str] = exclude or []
        for file in PathSearch(params.engine.paths.conf).files:
            if any(file.suffix.endswith(s) for s in (".yml", ".yaml")) and (
                values := YamlFlResolve(file).read()
            ):
                for key, data in values.items():
                    if key in exclude:
                        continue
                    if (
                        (t := data.get("type"))
                        and issubclass(cls.get_type(t, params), obj)
                        and all(i in data for i in (include or data.keys()))
                    ):
                        yield key, data

    @classmethod
    def get_type(cls, t: str, params: ConfParams) -> AnyModelType:
        try:
            # NOTE: Auto adding module prefix if it does not set
            return import_string(f"ddeutil.workflow.{t}")
        except ModuleNotFoundError:
            for registry in params.engine.registry:
                try:
                    return import_string(f"{registry}.{t}")
                except ModuleNotFoundError:
                    continue
            return import_string(f"{t}")

    @cached_property
    def type(self) -> AnyModelType:
        """Return object of string type which implement on any registry. The
        object type
        """
        if not (_typ := self.data.get("type")):
            raise ValueError(
                f"the 'type' value: {_typ} does not exists in config data."
            )
        return self.get_type(_typ, self.conf_params)


class Loader(SimLoad):
    """Loader Object that get the config `yaml` file from current path.

    :param name: A name of config data that will read by Yaml Loader object.
    :param externals: An external parameters
    """

    @classmethod
    def find(
        cls,
        obj,
        *,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
        **kwargs,
    ) -> DictData:
        return super().find(
            obj=obj, params=config(), include=include, exclude=exclude
        )

    def __init__(self, name: str, externals: DictData) -> None:
        super().__init__(name, config(), externals)
