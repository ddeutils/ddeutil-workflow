# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime, timedelta
from functools import cached_property, lru_cache
from pathlib import Path
from typing import ClassVar, Optional, Union
from zoneinfo import ZoneInfo

from ddeutil.core import str2bool
from ddeutil.io import YamlFlResolve
from pydantic import BaseModel, Field
from pydantic.functional_validators import model_validator
from typing_extensions import Self

from .__types import DictData, TupleStr


def env(var: str, default: str | None = None) -> str | None:  # pragma: no cov
    return os.getenv(f"WORKFLOW_{var}", default)


def glob_files(path: Path) -> Iterator[Path]:  # pragma: no cov
    yield from (file for file in path.rglob("*") if file.is_file())


__all__: TupleStr = (
    "env",
    "get_logger",
    "get_log",
    "Config",
    "SimLoad",
    "Loader",
    "config",
    "logger",
    "FileLog",
    "SQLiteLog",
    "Log",
)


@lru_cache
def get_logger(name: str):
    """Return logger object with an input module name.

    :param name: A module name that want to log.
    """
    lg = logging.getLogger(name)

    # NOTE: Developers using this package can then disable all logging just for
    #   this package by;
    #
    #   `logging.getLogger('ddeutil.workflow').propagate = False`
    #
    lg.addHandler(logging.NullHandler())

    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s.%(msecs)03d (%(name)-10s, %(process)-5d, "
            "%(thread)-5d) [%(levelname)-7s] %(message)-120s "
            "(%(filename)s:%(lineno)s)"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    lg.addHandler(stream)

    lg.setLevel(logging.DEBUG if config.debug else logging.INFO)
    return lg


class Config:  # pragma: no cov
    """Config object for keeping application configuration on current session
    without changing when if the application still running.
    """

    # NOTE: Core
    @property
    def root_path(self) -> Path:
        return Path(env("ROOT_PATH", "."))

    @property
    def conf_path(self) -> Path:
        """Config path that use root_path class argument for this construction.

        :rtype: Path
        """
        return self.root_path / env("CORE_PATH_CONF", "conf")

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(env("CORE_TIMEZONE", "UTC"))

    @property
    def gen_id_simple_mode(self) -> bool:
        return str2bool(env("CORE_GENERATE_ID_SIMPLE_MODE", "true"))

    # NOTE: Register
    @property
    def regis_hook(self) -> list[str]:
        regis_hook_str: str = env("CORE_REGISTRY", "src")
        return [r.strip() for r in regis_hook_str.split(",")]

    @property
    def regis_filter(self) -> list[str]:
        regis_filter_str: str = env(
            "CORE_REGISTRY_FILTER", "ddeutil.workflow.utils"
        )
        return [r.strip() for r in regis_filter_str.split(",")]

    # NOTE: Logging
    @property
    def log_path(self) -> Path:
        return Path(env("LOG_PATH", "./logs"))

    @property
    def debug(self) -> bool:
        return str2bool(env("LOG_DEBUG_MODE", "true"))

    @property
    def enable_write_log(self) -> bool:
        return str2bool(env("LOG_ENABLE_WRITE", "false"))

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

    # NOTE: Workflow
    @property
    def max_job_parallel(self) -> int:
        max_job_parallel = int(env("CORE_MAX_JOB_PARALLEL", "2"))

        # VALIDATE: the MAX_JOB_PARALLEL value should not less than 0.
        if max_job_parallel < 0:
            raise ValueError(
                f"``WORKFLOW_MAX_JOB_PARALLEL`` should more than 0 but got "
                f"{max_job_parallel}."
            )
        return max_job_parallel

    @property
    def max_job_exec_timeout(self) -> int:
        return int(env("CORE_MAX_JOB_EXEC_TIMEOUT", "600"))

    @property
    def max_poking_pool_worker(self) -> int:
        return int(env("CORE_MAX_NUM_POKING", "4"))

    @property
    def max_on_per_workflow(self) -> int:
        return int(env("CORE_MAX_CRON_PER_WORKFLOW", "5"))

    @property
    def max_queue_complete_hist(self) -> int:
        return int(env("CORE_MAX_QUEUE_COMPLETE_HIST", "16"))

    # NOTE: Schedule App
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

    # NOTE: API
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
    :param conf: A Params model object.
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
        conf: Config,
        externals: DictData | None = None,
    ) -> None:
        self.data: DictData = {}
        for file in glob_files(conf.conf_path):

            if data := self.filter_suffix(file, name):
                self.data = data

        # VALIDATE: check the data that reading should not empty.
        if not self.data:
            raise ValueError(f"Config {name!r} does not found on conf path")

        self.conf: Config = conf
        self.externals: DictData = externals or {}
        self.data.update(self.externals)

    @classmethod
    def finds(
        cls,
        obj: object,
        conf: Config,
        *,
        included: list[str] | None = None,
        excluded: list[str] | None = None,
    ) -> Iterator[tuple[str, DictData]]:
        """Find all data that match with object type in config path. This class
        method can use include and exclude list of identity name for filter and
        adds-on.

        :param obj: A object that want to validate matching before return.
        :param conf: A config object.
        :param included:
        :param excluded:

        :rtype: Iterator[tuple[str, DictData]]
        """
        exclude: list[str] = excluded or []
        for file in glob_files(conf.conf_path):

            for key, data in cls.filter_suffix(file).items():

                if key in exclude:
                    continue

                if data["type"] == obj.__name__:
                    yield key, (
                        {k: data[k] for k in data if k in included}
                        if included
                        else data
                    )

    @classmethod
    def filter_suffix(cls, file: Path, name: str | None = None) -> DictData:
        if any(file.suffix.endswith(s) for s in (".yml", ".yaml")):
            values: DictData = YamlFlResolve(file).read()
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
        **kwargs,
    ) -> Iterator[tuple[str, DictData]]:
        """Override the find class method from the Simple Loader object.

        :param obj: A object that want to validate matching before return.
        :param included:
        :param excluded:

        :rtype: Iterator[tuple[str, DictData]]
        """
        return super().finds(
            obj=obj, conf=Config(), included=included, excluded=excluded
        )

    def __init__(self, name: str, externals: DictData) -> None:
        super().__init__(name, conf=Config(), externals=externals)


config = Config()
logger = get_logger("ddeutil.workflow")


class BaseLog(BaseModel, ABC):
    """Base Log Pydantic Model with abstraction class property that implement
    only model fields. This model should to use with inherit to logging
    sub-class like file, sqlite, etc.
    """

    name: str = Field(description="A workflow name.")
    release: datetime = Field(description="A release datetime.")
    type: str = Field(description="A running type before logging.")
    context: DictData = Field(
        default_factory=dict,
        description=(
            "A context data that receive from a workflow execution result.",
        ),
    )
    parent_run_id: Optional[str] = Field(default=None)
    run_id: str
    update: datetime = Field(default_factory=datetime.now)

    @model_validator(mode="after")
    def __model_action(self) -> Self:
        """Do before the Log action with WORKFLOW_LOG_ENABLE_WRITE env variable.

        :rtype: Self
        """
        if config.enable_write_log:
            self.do_before()
        return self

    def do_before(self) -> None:  # pragma: no cov
        """To something before end up of initial log model."""

    @abstractmethod
    def save(self, excluded: list[str] | None) -> None:  # pragma: no cov
        """Save this model logging to target logging store."""
        raise NotImplementedError("Log should implement ``save`` method.")


class FileLog(BaseLog):
    """File Log Pydantic Model that use to saving log data from result of
    workflow execution. It inherit from BaseLog model that implement the
    ``self.save`` method for file.
    """

    filename_fmt: ClassVar[str] = (
        "workflow={name}/release={release:%Y%m%d%H%M%S}"
    )

    def do_before(self) -> None:
        """Create directory of release before saving log file."""
        self.pointer().mkdir(parents=True, exist_ok=True)

    @classmethod
    def find_logs(cls, name: str) -> Iterator[Self]:
        """Generate the logging data that found from logs path with specific a
        workflow name.

        :param name: A workflow name that want to search release logging data.

        :rtype: Iterator[Self]
        """
        pointer: Path = config.log_path / f"workflow={name}"
        if not pointer.exists():
            raise FileNotFoundError(f"Pointer: {pointer.absolute()}.")

        for file in pointer.glob("./release=*/*.log"):
            with file.open(mode="r", encoding="utf-8") as f:
                yield cls.model_validate(obj=json.load(f))

    @classmethod
    def find_log_with_release(
        cls,
        name: str,
        release: datetime | None = None,
    ) -> Self:
        """Return the logging data that found from logs path with specific
        workflow name and release values. If a release does not pass to an input
        argument, it will return the latest release from the current log path.

        :param name:
        :param release:

        :raise FileNotFoundError:
        :raise NotImplementedError:

        :rtype: Self
        """
        if release is None:
            raise NotImplementedError("Find latest log does not implement yet.")

        pointer: Path = (
            config.log_path / f"workflow={name}/release={release:%Y%m%d%H%M%S}"
        )
        if not pointer.exists():
            raise FileNotFoundError(
                f"Pointer: ./logs/workflow={name}/"
                f"release={release:%Y%m%d%H%M%S} does not found."
            )

        with max(pointer.glob("./*.log"), key=os.path.getctime).open(
            mode="r", encoding="utf-8"
        ) as f:
            return cls.model_validate(obj=json.load(f))

    @classmethod
    def is_pointed(cls, name: str, release: datetime) -> bool:
        """Check the release log already pointed or created at the destination
        log path.

        :param name: A workflow name.
        :param release: A release datetime.

        :rtype: bool
        :return: Return False if the release log was not pointed or created.
        """
        # NOTE: Return False if enable writing log flag does not set.
        if not config.enable_write_log:
            return False

        # NOTE: create pointer path that use the same logic of pointer method.
        pointer: Path = config.log_path / cls.filename_fmt.format(
            name=name, release=release
        )

        return pointer.exists()

    def pointer(self) -> Path:
        """Return release directory path that was generated from model data.

        :rtype: Path
        """
        return config.log_path / self.filename_fmt.format(
            name=self.name, release=self.release
        )

    def save(self, excluded: list[str] | None) -> Self:
        """Save logging data that receive a context data from a workflow
        execution result.

        :param excluded: An excluded list of key name that want to pass in the
            model_dump method.

        :rtype: Self
        """
        # NOTE: Check environ variable was set for real writing.
        if not config.enable_write_log:
            return self

        log_file: Path = self.pointer() / f"{self.run_id}.log"
        log_file.write_text(
            json.dumps(
                self.model_dump(exclude=excluded),
                default=str,
                indent=2,
            ),
            encoding="utf-8",
        )
        return self


class SQLiteLog(BaseLog):  # pragma: no cov

    table: str = "workflow_log"
    ddl: str = """
        workflow        str,
        release         int,
        type            str,
        context         json,
        parent_run_id   int,
        run_id          int,
        update          datetime
        primary key ( run_id )
        """

    def save(self, excluded: list[str] | None) -> None:
        raise NotImplementedError("SQLiteLog does not implement yet.")


Log = Union[
    FileLog,
    SQLiteLog,
]


def get_log() -> Log:  # pragma: no cov
    if config.log_path.is_file():
        return SQLiteLog
    return FileLog
