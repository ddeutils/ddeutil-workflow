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
    BaseAudit: Abstract base class for audit implementations
    FileAudit: File-based audit storage implementation
    SQLiteAudit: SQLite database audit storage implementation

Functions:
    get_audit_model: Factory function for creating audit instances

Example:
    ```python
    from ddeutil.workflow.audits import get_audit_model

    # Create file-based Audit
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
    """Base Audit Pydantic Model with abstraction class property.

    This model implements only model fields and should be used as a base class
    for logging subclasses like file, sqlite, etc.

    Attributes:
        extras: An extras parameter that want to override core config.
        name: A workflow name.
        release: A release datetime.
        type: A running type before logging.
        context: A context that receive from a workflow execution result.
        parent_run_id: A parent running ID.
        run_id: A running ID.
        runs_metadata: A runs metadata that will use to tracking this audit log.
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
    runs_metadata: DictData = Field(
        default_factory=dict,
        description="A runs metadata that will use to tracking this audit log.",
    )

    @model_validator(mode="after")
    def __model_action(self) -> Self:
        """Perform actions before Audit initialization.

        This method checks the WORKFLOW_AUDIT_ENABLE_WRITE environment variable
        and performs necessary setup actions.

        Returns:
            Self: The validated model instance.
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
        """Check if audit data exists for the given workflow and release.

        Args:
            name: The workflow name to check.
            release: The release datetime to check.
            extras: Optional extra parameters to override core config.

        Returns:
            bool: True if audit data exists, False otherwise.

        Raises:
            NotImplementedError: If the method is not implemented by subclass.
        """
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
        """Find all audit data for a given workflow name.

        Args:
            name: The workflow name to search for.
            extras: Optional extra parameters to override core config.

        Returns:
            Iterator[Self]: Iterator of audit instances.

        Raises:
            NotImplementedError: If the method is not implemented by subclass.
        """
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
        """Find audit data for a specific workflow and release.

        Args:
            name: The workflow name to search for.
            release: Optional release datetime. If None, returns latest release.
            extras: Optional extra parameters to override core config.

        Returns:
            Self: The audit instance for the specified workflow and release.

        Raises:
            NotImplementedError: If the method is not implemented by subclass.
        """
        raise NotImplementedError(
            "Audit should implement `find_audit_with_release` class-method"
        )

    def do_before(self) -> None:  # pragma: no cov
        """Perform actions before the end of initial log model setup.

        This method is called during model validation and can be overridden
        by subclasses to perform custom initialization actions.
        """

    @abstractmethod
    def save(self, excluded: Optional[list[str]]) -> None:  # pragma: no cov
        """Save this model logging to target logging store.

        Args:
            excluded: Optional list of field names to exclude from saving.

        Raises:
            NotImplementedError: If the method is not implemented by subclass.
        """
        raise NotImplementedError("Audit should implement `save` method.")


class FileAudit(BaseAudit):
    """File Audit Pydantic Model for saving log data from workflow execution.

    This class inherits from BaseAudit and implements file-based storage
    for audit logs. It saves workflow execution results to JSON files
    in a structured directory hierarchy.

    Attributes:
        filename_fmt: Class variable defining the filename format for audit files.
    """

    filename_fmt: ClassVar[str] = (
        "workflow={name}/release={release:%Y%m%d%H%M%S}"
    )

    @field_serializer("extras")
    def __serialize_extras(self, value: DictData) -> DictData:
        """Serialize extras field, converting ParseResult objects to URLs.

        Args:
            value: The extras dictionary to serialize.

        Returns:
            DictData: Serialized extras with ParseResult objects converted to URLs.
        """
        return {
            k: (v.geturl() if isinstance(v, ParseResult) else v)
            for k, v in value.items()
        }

    def do_before(self) -> None:
        """Create directory of release before saving log file.

        This method ensures the target directory exists before attempting
        to save audit log files.
        """
        self.pointer().mkdir(parents=True, exist_ok=True)

    @classmethod
    def find_audits(
        cls, name: str, *, extras: Optional[DictData] = None
    ) -> Iterator[Self]:
        """Generate audit data found from logs path for a specific workflow name.

        Args:
            name: The workflow name to search for release logging data.
            extras: Optional extra parameters to override core config.

        Returns:
            Iterator[Self]: Iterator of audit instances found for the workflow.

        Raises:
            FileNotFoundError: If the workflow directory does not exist.
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
        """Return audit data found from logs path for specific workflow and release.

        If a release is not provided, it will return the latest release from
        the current log path.

        Args:
            name: The workflow name to search for.
            release: Optional release datetime to search for.
            extras: Optional extra parameters to override core config.

        Returns:
            Self: The audit instance for the specified workflow and release.

        Raises:
            FileNotFoundError: If the specified workflow/release directory does not exist.
            NotImplementedError: If release is None (latest log not implemented yet).
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
        """Check if the release log already exists at the destination log path.

        Args:
            name: The workflow name.
            release: The release datetime.
            extras: Optional extra parameters to override core config.

        Returns:
            bool: True if the release log exists, False otherwise.
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
        """Return release directory path generated from model data.

        Returns:
            Path: The directory path for the current workflow and release.
        """
        return Path(
            dynamic("audit_url", extras=self.extras).path
        ) / self.filename_fmt.format(name=self.name, release=self.release)

    def save(self, excluded: Optional[list[str]] = None) -> Self:
        """Save logging data received from workflow execution result.

        Args:
            excluded: Optional list of field names to exclude from saving.

        Returns:
            Self: The audit instance after saving.
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
    """SQLite Audit model for database-based audit storage.

    This class inherits from BaseAudit and implements SQLite database storage
    for audit logs. Currently not fully implemented.

    Attributes:
        table_name: Class variable defining the database table name.
        schemas: Class variable defining the database schema.
    """

    table_name: ClassVar[str] = "audits"
    schemas: ClassVar[
        str
    ] = """
        workflow          str
        , release         int
        , type            str
        , context         JSON
        , parent_run_id   int
        , run_id          int
        , metadata        JSON
        , created_at      datetime
        , updated_at      datetime
        primary key ( workflow, release )
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
        """Save logging data received from workflow execution result.

        Args:
            excluded: Optional list of field names to exclude from saving.

        Returns:
            SQLiteAudit: The audit instance after saving.

        Raises:
            NotImplementedError: SQLiteAudit is not yet implemented.
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
    BaseAudit,
]


def get_audit_model(
    extras: Optional[DictData] = None,
) -> type[Audit]:  # pragma: no cov
    """Get an audit model dynamically based on the config audit path value.

    Args:
        extras: Optional extra parameters to override the core config.

    Returns:
        type[Audit]: The appropriate audit model class based on configuration.

    Raises:
        NotImplementedError: If the audit URL scheme is not supported.
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
