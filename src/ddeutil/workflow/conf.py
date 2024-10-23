# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import json
import os
from collections.abc import Iterator
from datetime import timedelta
from functools import cached_property
from pathlib import Path
from typing import Any, TypeVar
from zoneinfo import ZoneInfo

from ddeutil.core import import_string, str2bool
from ddeutil.io import Paths, PathSearch, YamlFlResolve
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field
from pydantic.functional_validators import model_validator

load_dotenv()
env = os.getenv
DictData = dict[str, Any]
AnyModel = TypeVar("AnyModel", bound=BaseModel)
AnyModelType = type[AnyModel]


class Config:
    """Config object for keeping application configuration on current session
    without changing when if the application still running.
    """

    # NOTE: Core
    root_path: Path = Path(os.getenv("WORKFLOW_ROOT_PATH", "."))
    tz: ZoneInfo = ZoneInfo(env("WORKFLOW_CORE_TIMEZONE", "UTC"))
    workflow_id_simple_mode: bool = str2bool(
        os.getenv("WORKFLOW_CORE_WORKFLOW_ID_SIMPLE_MODE", "true")
    )

    # NOTE: Logging
    debug: bool = str2bool(os.getenv("WORKFLOW_LOG_DEBUG_MODE", "true"))
    enable_write_log: bool = str2bool(
        os.getenv("WORKFLOW_LOG_ENABLE_WRITE", "false")
    )

    # NOTE: Stage
    stage_raise_error: bool = str2bool(
        env("WORKFLOW_CORE_STAGE_RAISE_ERROR", "true")
    )
    stage_default_id: bool = str2bool(
        env("WORKFLOW_CORE_STAGE_DEFAULT_ID", "false")
    )

    # NOTE: Job
    job_default_id: bool = str2bool(
        env("WORKFLOW_CORE_JOB_DEFAULT_ID", "false")
    )

    # NOTE: Workflow
    max_job_parallel: int = int(env("WORKFLOW_CORE_MAX_JOB_PARALLEL", "2"))
    max_poking_pool_worker: int = int(
        os.getenv("WORKFLOW_CORE_MAX_NUM_POKING", "4")
    )

    # NOTE: Schedule App
    max_schedule_process: int = int(env("WORKFLOW_APP_MAX_PROCESS", "2"))
    max_schedule_per_process: int = int(
        env("WORKFLOW_APP_MAX_SCHEDULE_PER_PROCESS", "100")
    )
    __stop_boundary_delta: str = env(
        "WORKFLOW_APP_STOP_BOUNDARY_DELTA", '{"minutes": 5, "seconds": 20}'
    )

    # NOTE: API
    enable_route_workflow: bool = str2bool(
        os.getenv("WORKFLOW_API_ENABLE_ROUTE_WORKFLOW", "true")
    )
    enable_route_schedule: bool = str2bool(
        os.getenv("WORKFLOW_API_ENABLE_ROUTE_SCHEDULE", "true")
    )

    def __init__(self):
        if self.max_job_parallel < 0:
            raise ValueError(
                f"``MAX_JOB_PARALLEL`` should more than 0 but got "
                f"{self.max_job_parallel}."
            )
        try:
            self.stop_boundary_delta: timedelta = timedelta(
                **json.loads(self.__stop_boundary_delta)
            )
        except Exception as err:
            raise ValueError(
                "Config ``WORKFLOW_APP_STOP_BOUNDARY_DELTA`` can not parsing to"
                f"timedelta with {self.__stop_boundary_delta}."
            ) from err

    def refresh_dotenv(self):
        """Reload environment variables from the current stage."""
        self.tz: ZoneInfo = ZoneInfo(env("WORKFLOW_CORE_TIMEZONE", "UTC"))
        self.stage_raise_error: bool = str2bool(
            env("WORKFLOW_CORE_STAGE_RAISE_ERROR", "true")
        )


class Engine(BaseModel):
    """Engine Pydantic Model for keeping application path."""

    paths: Paths = Field(default_factory=Paths)
    registry: list[str] = Field(
        default_factory=lambda: ["ddeutil.workflow"],  # pragma: no cover
    )
    registry_filter: list[str] = Field(
        default_factory=lambda: ["ddeutil.workflow.utils"],  # pragma: no cover
    )

    @model_validator(mode="before")
    def __prepare_registry(cls, values: DictData) -> DictData:
        """Prepare registry value that passing with string type. It convert the
        string type to list of string.
        """
        if (_regis := values.get("registry")) and isinstance(_regis, str):
            values["registry"] = [_regis]
        if (_regis_filter := values.get("registry_filter")) and isinstance(
            _regis, str
        ):
            values["registry_filter"] = [_regis_filter]
        return values


class CoreConf(BaseModel):
    """Core Config Model"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tz: ZoneInfo = Field(default_factory=lambda: ZoneInfo("UTC"))


class ConfParams(BaseModel):
    """Params Model"""

    engine: Engine = Field(
        default_factory=Engine,
        description="A engine mapping values.",
    )
    core: CoreConf = Field(
        default_factory=CoreConf,
        description="A core config value",
    )


def load_config() -> ConfParams:
    """Load Config data from ``workflows-conf.yaml`` file.

    Configuration Docs:
    ---
    :var engine.registry:
    :var engine.registry_filter:
    :var paths.root:
    :var paths.conf:
    """
    root_path: str = config.root_path

    regis: list[str] = ["ddeutil.workflow"]
    if regis_env := os.getenv("WORKFLOW_CORE_REGISTRY"):
        regis = [r.strip() for r in regis_env.split(",")]

    regis_filter: list[str] = ["ddeutil.workflow.utils"]
    if regis_filter_env := os.getenv("WORKFLOW_CORE_REGISTRY_FILTER"):
        regis_filter = [r.strip() for r in regis_filter_env.split(",")]

    conf_path: str = (
        f"{root_path}/{conf_env}"
        if (conf_env := os.getenv("WORKFLOW_CORE_PATH_CONF"))
        else None
    )
    return ConfParams.model_validate(
        obj={
            "engine": {
                "registry": regis,
                "registry_filter": regis_filter,
                "paths": {
                    "root": root_path,
                    "conf": conf_path,
                },
            },
        }
    )


class SimLoad:
    """Simple Load Object that will search config data by given some identity
    value like name of workflow or on.

    :param name: A name of config data that will read by Yaml Loader object.
    :param params: A Params model object.
    :param externals: An external parameters

    Noted:

        The config data should have ``type`` key for modeling validation that
    make this loader know what is config should to do pass to.

        ... <identity-key>:
        ...     type: <importable-object>
        ...     <key-data>: <value-data>
        ...     ...

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

        # VALIDATE: check the data that reading should not empty.
        if not self.data:
            raise ValueError(f"Config {name!r} does not found on conf path")

        self.conf_params: ConfParams = params
        self.externals: DictData = externals or {}
        self.data.update(self.externals)

    @classmethod
    def finds(
        cls,
        obj: object,
        params: ConfParams,
        *,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
    ) -> Iterator[tuple[str, DictData]]:
        """Find all data that match with object type in config path. This class
        method can use include and exclude list of identity name for filter and
        adds-on.

        :param obj:
        :param params:
        :param include:
        :param exclude:
        :rtype: Iterator[tuple[str, DictData]]
        """
        exclude: list[str] = exclude or []
        for file in PathSearch(params.engine.paths.conf).files:
            if any(file.suffix.endswith(s) for s in (".yml", ".yaml")) and (
                values := YamlFlResolve(file).read()
            ):
                for key, data in values.items():
                    if key in exclude:
                        continue
                    if issubclass(get_type(data["type"], params), obj) and (
                        include is None or all(i in data for i in include)
                    ):
                        yield key, data

    @cached_property
    def type(self) -> AnyModelType:
        """Return object of string type which implement on any registry. The
        object type.

        :rtype: AnyModelType
        """
        if not (_typ := self.data.get("type")):
            raise ValueError(
                f"the 'type' value: {_typ} does not exists in config data."
            )
        return get_type(_typ, self.conf_params)


class Loader(SimLoad):
    """Loader Object that get the config `yaml` file from current path.

    :param name: A name of config data that will read by Yaml Loader object.
    :param externals: An external parameters
    """

    @classmethod
    def finds(
        cls,
        obj: object,
        *,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
        **kwargs,
    ) -> DictData:
        """Override the find class method from the Simple Loader object.

        :param obj:
        :param include:
        :param exclude:
        """
        return super().finds(
            obj=obj, params=load_config(), include=include, exclude=exclude
        )

    def __init__(self, name: str, externals: DictData) -> None:
        super().__init__(name, load_config(), externals)


def get_type(t: str, params: ConfParams) -> AnyModelType:
    """Return import type from string importable value in the type key.

    :param t: A importable type string.
    :param params: A config parameters that use registry to search this
        type.
    :rtype: AnyModelType
    """
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


config = Config()
