# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from datetime import timedelta
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Optional, TypeVar
from zoneinfo import ZoneInfo

from ddeutil.core import str2bool
from ddeutil.io import YamlFlResolve
from ddeutil.io.paths import glob_files, is_ignored, read_ignore

from .__types import DictData, TupleStr

T = TypeVar("T")
PREFIX: str = "WORKFLOW"


def env(var: str, default: str | None = None) -> str | None:  # pragma: no cov
    """Get environment variable with uppercase and adding prefix string.

    :rtype: str | None
    """
    return os.getenv(f"{PREFIX}_{var.upper().replace(' ', '_')}", default)


__all__: TupleStr = (
    "api_config",
    "env",
    "get_logger",
    "Config",
    "SimLoad",
    "Loader",
    "config",
    "dynamic",
)


class Config:  # pragma: no cov
    """Config object for keeping core configurations on the current session
    without changing when if the application still running.

        The config value can change when you call that config property again.
    """

    # NOTE: Core
    @property
    def root_path(self) -> Path:
        """Root path or the project path.

        :rtype: Path
        """
        return Path(env("CORE_ROOT_PATH", "."))

    @property
    def conf_path(self) -> Path:
        """Config path that use root_path class argument for this construction.

        :rtype: Path
        """
        return self.root_path / env("CORE_CONF_PATH", "conf")

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(env("CORE_TIMEZONE", "UTC"))

    @property
    def gen_id_simple_mode(self) -> bool:
        return str2bool(env("CORE_GENERATE_ID_SIMPLE_MODE", "true"))

    # NOTE: Register
    @property
    def regis_call(self) -> list[str]:
        """Register Caller module importer str.

        :rtype: list[str]
        """
        regis_call_str: str = env("CORE_REGISTRY_CALLER", ".")
        return [r.strip() for r in regis_call_str.split(",")]

    @property
    def regis_filter(self) -> list[str]:
        """Register Filter module.

        :rtype: list[str]
        """
        regis_filter_str: str = env(
            "CORE_REGISTRY_FILTER", "ddeutil.workflow.templates"
        )
        return [r.strip() for r in regis_filter_str.split(",")]

    # NOTE: Log
    @property
    def log_path(self) -> Path:
        return Path(env("LOG_TRACE_PATH", "./logs"))

    @property
    def debug(self) -> bool:
        return str2bool(env("LOG_DEBUG_MODE", "true"))

    @property
    def log_format(self) -> str:
        return env(
            "LOG_FORMAT",
            (
                "%(asctime)s.%(msecs)03d (%(name)-10s, %(process)-5d, "
                "%(thread)-5d) [%(levelname)-7s] %(message)-120s "
                "(%(filename)s:%(lineno)s)"
            ),
        )

    @property
    def log_format_file(self) -> str:
        return env(
            "LOG_FORMAT_FILE",
            (
                "{datetime} ({process:5d}, {thread:5d}) {message:120s} "
                "({filename}:{lineno})"
            ),
        )

    @property
    def enable_write_log(self) -> bool:
        return str2bool(env("LOG_TRACE_ENABLE_WRITE", "false"))

    @property
    def audit_path(self) -> Path:
        return Path(env("LOG_AUDIT_PATH", "./audits"))

    @property
    def enable_write_audit(self) -> bool:
        return str2bool(env("LOG_AUDIT_ENABLE_WRITE", "false"))

    @property
    def log_datetime_format(self) -> str:
        return env("LOG_DATETIME_FORMAT", "%Y-%m-%d %H:%M:%S")

    # NOTE: Stage
    @property
    def stage_raise_error(self) -> bool:
        return str2bool(env("CORE_STAGE_RAISE_ERROR", "false"))

    @property
    def stage_default_id(self) -> bool:
        return str2bool(env("CORE_STAGE_DEFAULT_ID", "false"))

    # NOTE: Job
    @property
    def job_raise_error(self) -> bool:
        return str2bool(env("CORE_JOB_RAISE_ERROR", "true"))

    @property
    def job_default_id(self) -> bool:
        return str2bool(env("CORE_JOB_DEFAULT_ID", "false"))

    @property
    def max_on_per_workflow(self) -> int:
        """The maximum on value that store in workflow model.

        :rtype: int
        """
        return int(env("CORE_MAX_CRON_PER_WORKFLOW", "5"))

    @property
    def max_queue_complete_hist(self) -> int:
        return int(env("CORE_MAX_QUEUE_COMPLETE_HIST", "16"))

    # NOTE: App
    @property
    def max_schedule_process(self) -> int:
        return int(env("APP_MAX_PROCESS", "2"))

    @property
    def max_schedule_per_process(self) -> int:
        return int(env("APP_MAX_SCHEDULE_PER_PROCESS", "100"))

    @property
    def stop_boundary_delta(self) -> timedelta:
        stop_boundary_delta_str: str = env(
            "APP_STOP_BOUNDARY_DELTA", '{"minutes": 5, "seconds": 20}'
        )
        try:
            return timedelta(**json.loads(stop_boundary_delta_str))
        except Exception as err:
            raise ValueError(
                "Config ``WORKFLOW_APP_STOP_BOUNDARY_DELTA`` can not parsing to"
                f"timedelta with {stop_boundary_delta_str}."
            ) from err


class APIConfig:
    """API Config object."""

    @property
    def prefix_path(self) -> str:
        return env("API_PREFIX_PATH", "/api/v1")

    @property
    def enable_route_workflow(self) -> bool:
        return str2bool(env("API_ENABLE_ROUTE_WORKFLOW", "true"))

    @property
    def enable_route_schedule(self) -> bool:
        return str2bool(env("API_ENABLE_ROUTE_SCHEDULE", "true"))


class SimLoad:
    """Simple Load Object that will search config data by given some identity
    value like name of workflow or on.

    :param name: A name of config data that will read by Yaml Loader object.
    :param conf_path: A config path object.
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
        conf_path: Path,
        externals: DictData | None = None,
    ) -> None:
        self.conf_path: Path = conf_path
        self.externals: DictData = externals or {}

        self.data: DictData = {}
        for file in glob_files(conf_path):

            if self.is_ignore(file, conf_path):
                continue

            if data := self.filter_yaml(file, name=name):
                self.data = data

        # VALIDATE: check the data that reading should not empty.
        if not self.data:
            raise ValueError(f"Config {name!r} does not found on conf path")

        self.data.update(self.externals)

    @classmethod
    def finds(
        cls,
        obj: object,
        conf_path: Path,
        *,
        included: list[str] | None = None,
        excluded: list[str] | None = None,
    ) -> Iterator[tuple[str, DictData]]:
        """Find all data that match with object type in config path. This class
        method can use include and exclude list of identity name for filter and
        adds-on.

        :param obj: An object that want to validate matching before return.
        :param conf_path: A config object.
        :param included: An excluded list of data key that want to reject this
            data if any key exist.
        :param excluded: An included list of data key that want to filter from
            data.

        :rtype: Iterator[tuple[str, DictData]]
        """
        exclude: list[str] = excluded or []
        for file in glob_files(conf_path):

            if cls.is_ignore(file, conf_path):
                continue

            for key, data in cls.filter_yaml(file).items():

                if key in exclude:
                    continue

                if data.get("type", "") == obj.__name__:
                    yield key, (
                        {k: data[k] for k in data if k in included}
                        if included
                        else data
                    )

    @classmethod
    def is_ignore(cls, file: Path, conf_path: Path) -> bool:
        return is_ignored(file, read_ignore(conf_path / ".confignore"))

    @classmethod
    def filter_yaml(cls, file: Path, name: str | None = None) -> DictData:
        if any(file.suffix.endswith(s) for s in (".yml", ".yaml")):
            values: DictData = YamlFlResolve(file).read()
            if values is not None:
                return values.get(name, {}) if name else values
        return {}

    @cached_property
    def type(self) -> str:
        """Return object of string type which implement on any registry. The
        object type.

        :rtype: str
        """
        if _typ := self.data.get("type"):
            return _typ
        raise ValueError(
            f"the 'type' value: {_typ} does not exists in config data."
        )


config: Config = Config()
api_config: APIConfig = APIConfig()


def dynamic(
    key: Optional[str] = None,
    *,
    f: Optional[T] = None,
    extras: Optional[DictData] = None,
) -> Optional[T]:
    """Dynamic get config if extra value was passed at run-time.

    :param key: (str) A config key that get from Config object.
    :param f: An inner config function scope.
    :param extras: An extra values that pass at run-time.
    """
    rsx: Optional[T] = extras[key] if extras and key in extras else None
    rs: Optional[T] = f or getattr(config, key, None)
    if rsx is not None and not isinstance(rsx, type(rs)):
        raise TypeError(
            f"Type of config {key!r} from extras: {rsx!r} does not valid "
            f"as config {type(rs)}."
        )
    return rsx or rs


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
        included: list[str] | None = None,
        excluded: list[str] | None = None,
        path: Path | None = None,
        **kwargs,
    ) -> Iterator[tuple[str, DictData]]:
        """Override the find class method from the Simple Loader object.

        :param obj: An object that want to validate matching before return.
        :param included:
        :param excluded:
        :param path:

        :rtype: Iterator[tuple[str, DictData]]
        """
        return super().finds(
            obj=obj,
            conf_path=(path or config.conf_path),
            included=included,
            excluded=excluded,
        )

    def __init__(self, name: str, externals: DictData) -> None:
        super().__init__(
            name,
            conf_path=dynamic("conf_path", extras=externals),
            externals=externals,
        )


@lru_cache
def get_logger(name: str):
    """Return logger object with an input module name.

    :param name: A module name that want to log.
    """
    logger = logging.getLogger(name)

    # NOTE: Developers using this package can then disable all logging just for
    #   this package by;
    #
    #   `logging.getLogger('ddeutil.workflow').propagate = False`
    #
    logger.addHandler(logging.NullHandler())

    formatter = logging.Formatter(
        fmt=config.log_format,
        datefmt=config.log_datetime_format,
    )
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    logger.setLevel(logging.DEBUG if config.debug else logging.INFO)
    return logger
