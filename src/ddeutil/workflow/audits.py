# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Audit and Execution Tracking Module.

This module provides comprehensive audit capabilities for workflow execution
tracking and monitoring. It supports multiple audit backends for capturing
execution metadata, status information, and detailed logging.

The audit system tracks workflow, job, and stage executions with configurable
storage backends including file-based JSON storage and database persistence.

Classes:
    Audit: Pydantic model for audit data validation
    FileAudit: File-based audit storage implementation

Functions:
    get_audit_model: Factory function for creating audit instances

Example:
    ```python
    from ddeutil.workflow.audits import get_audit_model

    # Create file-based audit
    audit = get_audit_model(run_id="run-123")
    audit.info("Workflow execution started")
    audit.success("Workflow completed successfully")
    ```

Note:
    Audit instances are automatically configured based on the workflow
    configuration and provide detailed execution tracking capabilities.
"""
from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import ClassVar, Optional, Union
from urllib.parse import ParseResult

from pydantic import BaseModel, Field
from pydantic.functional_serializers import field_serializer
from pydantic.functional_validators import model_validator
from typing_extensions import Self

from .__types import DictData
from .conf import dynamic
from .traces import Trace, get_trace, set_logging

logger = logging.getLogger("ddeutil.workflow")


class BaseAudit(BaseModel, ABC):
    """Base Audit Pydantic Model with abstraction class property that implement
    only model fields. This model should to use with inherit to logging
    subclass like file, sqlite, etc.
    """

    extras: DictData = Field(
        default_factory=dict,
        description="An extras parameter that want to override core config",
    )
    name: str = Field(description="A workflow name.")
    release: datetime = Field(description="A release datetime.")
    type: str = Field(description="A running type before logging.")
    context: DictData = Field(
        default_factory=dict,
        description="A context that receive from a workflow execution result.",
    )
    parent_run_id: Optional[str] = Field(
        default=None, description="A parent running ID."
    )
    run_id: str = Field(description="A running ID")
    execution_time: float = Field(default=0, description="An execution time.")

    @model_validator(mode="after")
    def __model_action(self) -> Self:
        """Do before the Audit action with WORKFLOW_AUDIT_ENABLE_WRITE env variable.

        :rtype: Self
        """
        if dynamic("enable_write_audit", extras=self.extras):
            self.do_before()

        # NOTE: Start setting log config in this line with cache.
        set_logging("ddeutil.workflow")
        return self

    @classmethod
    @abstractmethod
    def is_pointed(
        cls,
        name: str,
        release: datetime,
        *,
        extras: Optional[DictData] = None,
    ) -> bool:
        raise NotImplementedError(
            "Audit should implement `is_pointed` class-method"
        )

    @classmethod
    @abstractmethod
    def find_audits(
        cls,
        name: str,
        *,
        extras: Optional[DictData] = None,
    ) -> Iterator[Self]:
        raise NotImplementedError(
            "Audit should implement `find_audits` class-method"
        )

    @classmethod
    @abstractmethod
    def find_audit_with_release(
        cls,
        name: str,
        release: Optional[datetime] = None,
        *,
        extras: Optional[DictData] = None,
    ) -> Self:
        raise NotImplementedError(
            "Audit should implement `find_audit_with_release` class-method"
        )

    def do_before(self) -> None:  # pragma: no cov
        """To something before end up of initial log model."""

    @abstractmethod
    def save(self, excluded: Optional[list[str]]) -> None:  # pragma: no cov
        """Save this model logging to target logging store."""
        raise NotImplementedError("Audit should implement `save` method.")


class FileAudit(BaseAudit):
    """File Audit Pydantic Model that use to saving log data from result of
    workflow execution. It inherits from BaseAudit model that implement the
    ``self.save`` method for file.
    """

    filename_fmt: ClassVar[str] = (
        "workflow={name}/release={release:%Y%m%d%H%M%S}"
    )

    @field_serializer("extras")
    def __serialize_extras(self, value: DictData) -> DictData:
        return {
            k: (v.geturl() if isinstance(v, ParseResult) else v)
            for k, v in value.items()
        }

    def do_before(self) -> None:
        """Create directory of release before saving log file."""
        self.pointer().mkdir(parents=True, exist_ok=True)

    @classmethod
    def find_audits(
        cls, name: str, *, extras: Optional[DictData] = None
    ) -> Iterator[Self]:
        """Generate the audit data that found from logs path with specific a
        workflow name.

        :param name: A workflow name that want to search release logging data.
        :param extras: An extra parameter that want to override core config.

        :rtype: Iterator[Self]
        """
        pointer: Path = (
            Path(dynamic("audit_url", extras=extras).path) / f"workflow={name}"
        )
        if not pointer.exists():
            raise FileNotFoundError(f"Pointer: {pointer.absolute()}.")

        for file in pointer.glob("./release=*/*.log"):
            with file.open(mode="r", encoding="utf-8") as f:
                yield cls.model_validate(obj=json.load(f))

    @classmethod
    def find_audit_with_release(
        cls,
        name: str,
        release: Optional[datetime] = None,
        *,
        extras: Optional[DictData] = None,
    ) -> Self:
        """Return the audit data that found from logs path with specific
        workflow name and release values. If a release does not pass to an input
        argument, it will return the latest release from the current log path.

        :param name: (str) A workflow name that want to search log.
        :param release: (datetime) A release datetime that want to search log.
        :param extras: An extra parameter that want to override core config.

        :raise FileNotFoundError:
        :raise NotImplementedError: If an input release does not pass to this
            method. Because this method does not implement latest log.

        :rtype: Self
        """
        if release is None:
            raise NotImplementedError("Find latest log does not implement yet.")

        pointer: Path = (
            Path(dynamic("audit_url", extras=extras).path)
            / f"workflow={name}/release={release:%Y%m%d%H%M%S}"
        )
        if not pointer.exists():
            raise FileNotFoundError(
                f"Pointer: ./logs/workflow={name}/"
                f"release={release:%Y%m%d%H%M%S} does not found."
            )

        latest_file: Path = max(pointer.glob("./*.log"), key=os.path.getctime)
        with latest_file.open(mode="r", encoding="utf-8") as f:
            return cls.model_validate(obj=json.load(f))

    @classmethod
    def is_pointed(
        cls,
        name: str,
        release: datetime,
        *,
        extras: Optional[DictData] = None,
    ) -> bool:
        """Check the release log already pointed or created at the destination
        log path.

        :param name: (str) A workflow name.
        :param release: (datetime) A release datetime.
        :param extras: An extra parameter that want to override core config.

        :rtype: bool
        :return: Return False if the release log was not pointed or created.
        """
        # NOTE: Return False if enable writing log flag does not set.
        if not dynamic("enable_write_audit", extras=extras):
            return False

        # NOTE: create pointer path that use the same logic of pointer method.
        pointer: Path = Path(
            dynamic("audit_url", extras=extras).path
        ) / cls.filename_fmt.format(name=name, release=release)

        return pointer.exists()

    def pointer(self) -> Path:
        """Return release directory path that was generated from model data.

        :rtype: Path
        """
        return Path(
            dynamic("audit_url", extras=self.extras).path
        ) / self.filename_fmt.format(name=self.name, release=self.release)

    def save(self, excluded: Optional[list[str]] = None) -> Self:
        """Save logging data that receive a context data from a workflow
        execution result.

        :param excluded: An excluded list of key name that want to pass in the
            model_dump method.

        :rtype: Self
        """
        trace: Trace = get_trace(
            self.run_id,
            parent_run_id=self.parent_run_id,
            extras=self.extras,
        )

        # NOTE: Check environ variable was set for real writing.
        if not dynamic("enable_write_audit", extras=self.extras):
            trace.debug("[AUDIT]: Skip writing log cause config was set")
            return self

        log_file: Path = (
            self.pointer() / f"{self.parent_run_id or self.run_id}.log"
        )
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

    table_name: ClassVar[str] = "audits"
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

    @classmethod
    def is_pointed(
        cls,
        name: str,
        release: datetime,
        *,
        extras: Optional[DictData] = None,
    ) -> bool: ...

    @classmethod
    def find_audits(
        cls,
        name: str,
        *,
        extras: Optional[DictData] = None,
    ) -> Iterator[Self]: ...

    @classmethod
    def find_audit_with_release(
        cls,
        name: str,
        release: Optional[datetime] = None,
        *,
        extras: Optional[DictData] = None,
    ) -> Self: ...

    def save(self, excluded: Optional[list[str]]) -> SQLiteAudit:
        """Save logging data that receive a context data from a workflow
        execution result.
        """
        trace: Trace = get_trace(
            self.run_id,
            parent_run_id=self.parent_run_id,
            extras=self.extras,
        )

        # NOTE: Check environ variable was set for real writing.
        if not dynamic("enable_write_audit", extras=self.extras):
            trace.debug("[AUDIT]: Skip writing log cause config was set")
            return self

        raise NotImplementedError("SQLiteAudit does not implement yet.")


Audit = Union[
    FileAudit,
    SQLiteAudit,
]


def get_audit_model(
    extras: Optional[DictData] = None,
) -> type[Audit]:  # pragma: no cov
    """Get an audit model that dynamic base on the config audit path value.

    :param extras: An extra parameter that want to override the core config.

    :rtype: type[Audit]
    """
    # NOTE: Allow you to override trace model by the extra parameter.
    map_audit_models: dict[str, type[Trace]] = extras.get(
        "audit_model_mapping", {}
    )
    url: ParseResult
    if (url := dynamic("audit_url", extras=extras)).scheme and (
        url.scheme == "sqlite"
        or (url.scheme == "file" and Path(url.path).is_file())
    ):
        return map_audit_models.get("sqlite", FileAudit)
    elif url.scheme and url.scheme != "file":
        raise NotImplementedError(
            f"Does not implement the audit model support for URL: {url}"
        )
    return map_audit_models.get("file", FileAudit)
