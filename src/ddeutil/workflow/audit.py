# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Audit Log module."""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import ClassVar, Optional, Union

from pydantic import BaseModel, Field
from pydantic.functional_validators import model_validator
from typing_extensions import Self

from .__types import DictData, TupleStr
from .conf import config, get_logger

logger = get_logger("ddeutil.workflow")

__all__: TupleStr = (
    "get_audit",
    "FileAudit",
    "SQLiteAudit",
    "Audit",
)


class BaseAudit(BaseModel, ABC):
    """Base Audit Pydantic Model with abstraction class property that implement
    only model fields. This model should to use with inherit to logging
    subclass like file, sqlite, etc.
    """

    name: str = Field(description="A workflow name.")
    release: datetime = Field(description="A release datetime.")
    type: str = Field(description="A running type before logging.")
    context: DictData = Field(
        default_factory=dict,
        description="A context that receive from a workflow execution result.",
    )
    parent_run_id: Optional[str] = Field(default=None)
    run_id: str
    update: datetime = Field(default_factory=datetime.now)
    execution_time: float = Field(default=0)

    @model_validator(mode="after")
    def __model_action(self) -> Self:
        """Do before the Audit action with WORKFLOW_AUDIT_ENABLE_WRITE env variable.

        :rtype: Self
        """
        if config.enable_write_audit:
            self.do_before()
        return self

    def do_before(self) -> None:  # pragma: no cov
        """To something before end up of initial log model."""

    @abstractmethod
    def save(self, excluded: list[str] | None) -> None:  # pragma: no cov
        """Save this model logging to target logging store."""
        raise NotImplementedError("Audit should implement ``save`` method.")


class FileAudit(BaseAudit):
    """File Audit Pydantic Model that use to saving log data from result of
    workflow execution. It inherits from BaseAudit model that implement the
    ``self.save`` method for file.
    """

    filename_fmt: ClassVar[str] = (
        "workflow={name}/release={release:%Y%m%d%H%M%S}"
    )

    def do_before(self) -> None:
        """Create directory of release before saving log file."""
        self.pointer().mkdir(parents=True, exist_ok=True)

    @classmethod
    def find_audits(cls, name: str) -> Iterator[Self]:
        """Generate the audit data that found from logs path with specific a
        workflow name.

        :param name: A workflow name that want to search release logging data.

        :rtype: Iterator[Self]
        """
        pointer: Path = config.audit_path / f"workflow={name}"
        if not pointer.exists():
            raise FileNotFoundError(f"Pointer: {pointer.absolute()}.")

        for file in pointer.glob("./release=*/*.log"):
            with file.open(mode="r", encoding="utf-8") as f:
                yield cls.model_validate(obj=json.load(f))

    @classmethod
    def find_audit_with_release(
        cls,
        name: str,
        release: datetime | None = None,
    ) -> Self:
        """Return the audit data that found from logs path with specific
        workflow name and release values. If a release does not pass to an input
        argument, it will return the latest release from the current log path.

        :param name: A workflow name that want to search log.
        :param release: A release datetime that want to search log.

        :raise FileNotFoundError:
        :raise NotImplementedError:

        :rtype: Self
        """
        if release is None:
            raise NotImplementedError("Find latest log does not implement yet.")

        pointer: Path = (
            config.audit_path
            / f"workflow={name}/release={release:%Y%m%d%H%M%S}"
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
        if not config.enable_write_audit:
            return False

        # NOTE: create pointer path that use the same logic of pointer method.
        pointer: Path = config.audit_path / cls.filename_fmt.format(
            name=name, release=release
        )

        return pointer.exists()

    def pointer(self) -> Path:
        """Return release directory path that was generated from model data.

        :rtype: Path
        """
        return config.audit_path / self.filename_fmt.format(
            name=self.name, release=self.release
        )

    def save(self, excluded: list[str] | None) -> Self:
        """Save logging data that receive a context data from a workflow
        execution result.

        :param excluded: An excluded list of key name that want to pass in the
            model_dump method.

        :rtype: Self
        """
        from .utils import cut_id

        # NOTE: Check environ variable was set for real writing.
        if not config.enable_write_audit:
            logger.debug(
                f"({cut_id(self.run_id)}) [LOG]: Skip writing log cause "
                f"config was set"
            )
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


class SQLiteAudit(BaseAudit):  # pragma: no cov
    """SQLite Audit Pydantic Model."""

    table_name: ClassVar[str] = "workflow_log"
    schemas: ClassVar[
        str
    ] = """
        workflow        str,
        release         int,
        type            str,
        context         json,
        parent_run_id   int,
        run_id          int,
        update          datetime
        primary key ( run_id )
        """

    def save(self, excluded: list[str] | None) -> SQLiteAudit:
        """Save logging data that receive a context data from a workflow
        execution result.
        """
        from .utils import cut_id

        # NOTE: Check environ variable was set for real writing.
        if not config.enable_write_audit:
            logger.debug(
                f"({cut_id(self.run_id)}) [LOG]: Skip writing log cause "
                f"config was set"
            )
            return self

        raise NotImplementedError("SQLiteAudit does not implement yet.")


class RemoteFileAudit(FileAudit):  # pragma: no cov
    """Remote File Audit Pydantic Model."""

    def save(self, excluded: list[str] | None) -> RemoteFileAudit: ...


class RedisAudit(BaseAudit):  # pragma: no cov
    """Redis Audit Pydantic Model."""

    def save(self, excluded: list[str] | None) -> RedisAudit: ...


Audit = Union[
    FileAudit,
    SQLiteAudit,
]


def get_audit() -> type[Audit]:  # pragma: no cov
    """Get an audit class that dynamic base on the config audit path value.

    :rtype: type[Audit]
    """
    if config.audit_path.is_file():
        return SQLiteAudit
    return FileAudit
