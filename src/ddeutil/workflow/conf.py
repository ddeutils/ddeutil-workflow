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
from inspect import isclass
from pathlib import Path
from typing import Final, Optional, Protocol, TypeVar, Union
from zoneinfo import ZoneInfo

from ddeutil.core import str2bool
from ddeutil.io import YamlFlResolve
from ddeutil.io.paths import glob_files, is_ignored, read_ignore

from .__types import DictData

T = TypeVar("T")
PREFIX: Final[str] = "WORKFLOW"


def env(var: str, default: str | None = None) -> str | None:
    """Get environment variable with uppercase and adding prefix string.

    :param var: (str) A env variable name.
    :param default: (str | None) A default value if an env var does not set.

    :rtype: str | None
    """
    return os.getenv(f"{PREFIX}_{var.upper().replace(' ', '_')}", default)


class Config:  # pragma: no cov
    """Config object for keeping core configurations on the current session
    without changing when if the application still running.

        The config value can change when you call that config property again.
    """

    @property
    def conf_path(self) -> Path:
        """Config path that keep all workflow template YAML files.

        :rtype: Path
        """
        return Path(env("CORE_CONF_PATH", "./conf"))

    @property
    def tz(self) -> ZoneInfo:
        """Timezone value that return with the `ZoneInfo` object and use for all
        datetime object in this workflow engine.

        :rtype: ZoneInfo
        """
        return ZoneInfo(env("CORE_TIMEZONE", "UTC"))

    @property
    def generate_id_simple_mode(self) -> bool:
        """Flag for generate running ID with simple mode. That does not use
        `md5` function after generate simple mode.

        :rtype: bool
        """
        return str2bool(env("CORE_GENERATE_ID_SIMPLE_MODE", "true"))

    @property
    def registry_caller(self) -> list[str]:
        """Register Caller that is a list of importable string for the call
        stage model can get.

        :rtype: list[str]
        """
        regis_call_str: str = env("CORE_REGISTRY_CALLER", ".")
        return [r.strip() for r in regis_call_str.split(",")]

    @property
    def registry_filter(self) -> list[str]:
        """Register Filter that is a list of importable string for the filter
        template.

        :rtype: list[str]
        """
        regis_filter_str: str = env(
            "CORE_REGISTRY_FILTER", "ddeutil.workflow.templates"
        )
        return [r.strip() for r in regis_filter_str.split(",")]

    @property
    def trace_path(self) -> Path:
        return Path(env("LOG_TRACE_PATH", "./logs"))

    @property
    def debug(self) -> bool:
        """Debug flag for echo log that use DEBUG mode.

        :rtype: bool
        """
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

    @property
    def stage_raise_error(self) -> bool:
        return str2bool(env("CORE_STAGE_RAISE_ERROR", "false"))

    @property
    def stage_default_id(self) -> bool:
        return str2bool(env("CORE_STAGE_DEFAULT_ID", "false"))

    @property
    def max_cron_per_workflow(self) -> int:
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
                "Config `WORKFLOW_APP_STOP_BOUNDARY_DELTA` can not parsing to"
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


class FileLoad:
    """Base Load object that use to search config data by given some identity
    value like name of `Workflow` or `On` templates.

    :param name: (str) A name of key of config data that read with YAML
        Environment object.
    :param path: (Path) A config path object.
    :param externals: (DictData) An external config data that want to add to
        loaded config data.
    :param extras: (DictDdata) An extra parameters that use to override core
        config values.

    Noted:
        The config data should have `type` key for modeling validation that
    make this loader know what is config should to do pass to.

        ... <identity-key>:
        ...     type: <importable-object>
        ...     <key-data-1>: <value-data-1>
        ...     <key-data-2>: <value-data-2>
    """

    def __init__(
        self,
        name: str,
        *,
        path: Optional[Union[str, Path]] = None,
        externals: DictData | None = None,
        extras: DictData | None = None,
    ) -> None:
        self.conf_path: Path = Path(dynamic("conf_path", f=path, extras=extras))
        self.externals: DictData = externals or {}
        self.extras: DictData = extras or {}
        self.data: DictData = {}

        for file in glob_files(self.conf_path):

            if self.is_ignore(file, self.conf_path):
                continue

            if data := self.filter_yaml(file, name=name):
                self.data = data

        # VALIDATE: check the data that reading should not empty.
        if not self.data:
            raise ValueError(
                f"Config {name!r} does not found on conf path: "
                f"{self.conf_path}."
            )

        self.data.update(self.externals)

    @classmethod
    def finds(
        cls,
        obj: object,
        *,
        path: Optional[Path] = None,
        included: list[str] | None = None,
        excluded: list[str] | None = None,
        extras: Optional[DictData] = None,
    ) -> Iterator[tuple[str, DictData]]:
        """Find all data that match with object type in config path. This class
        method can use include and exclude list of identity name for filter and
        adds-on.

        :param obj: An object that want to validate matching before return.
        :param path: A config path object.
        :param included: An excluded list of data key that want to reject this
            data if any key exist.
        :param excluded: An included list of data key that want to filter from
            data.
        :param extras: (DictData) An extra parameter that use to override core
            config values.

        :rtype: Iterator[tuple[str, DictData]]
        """
        exclude: list[str] = excluded or []
        conf_path: Path = dynamic("conf_path", f=path, extras=extras)
        for file in glob_files(conf_path):

            if cls.is_ignore(file, conf_path):
                continue

            for key, data in cls.filter_yaml(file).items():

                if key in exclude:
                    continue

                if (
                    data.get("type", "")
                    == (obj if isclass(obj) else obj.__class__).__name__
                ):
                    yield key, (
                        {k: data[k] for k in data if k in included}
                        if included
                        else data
                    )

    @classmethod
    def is_ignore(
        cls,
        file: Path,
        conf_path: Path,
        *,
        ignore_filename: Optional[str] = None,
    ) -> bool:
        """Check this file was ignored.

        :param file: (Path) A file path that want to check.
        :param conf_path: (Path) A config path that want to read the config
            ignore file.
        :param ignore_filename: (str) An ignore filename. Default is
            `.confignore` filename.

        :rtype: bool
        """
        ignore_filename: str = ignore_filename or ".confignore"
        return is_ignored(file, read_ignore(conf_path / ignore_filename))

    @classmethod
    def filter_yaml(cls, file: Path, name: str | None = None) -> DictData:
        """Read a YAML file context from an input file path and specific name.

        :param file: (Path) A file path that want to extract YAML context.
        :param name: (str) A key name that search on a YAML context.

        :rtype: DictData
        """
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
    rs: Optional[T] = getattr(config, key, None) if f is None else f
    if rsx is not None and not isinstance(rsx, type(rs)):
        raise TypeError(
            f"Type of config {key!r} from extras: {rsx!r} does not valid "
            f"as config {type(rs)}."
        )
    return rsx if rsx is not None else rs


class Loader(Protocol):
    type: str
    conf_path: Path
    data: DictData

    def __init__(
        self,
        name: str,
        *,
        path: Optional[Union[str, Path]] = None,
        externals: DictData | None = None,
        extras: DictData | None = None,
    ) -> None: ...

    @classmethod
    def finds(
        cls,
        obj: object,
        *,
        path: Optional[Path] = None,
        included: list[str] | None = None,
        excluded: list[str] | None = None,
        extras: Optional[DictData] = None,
    ): ...
