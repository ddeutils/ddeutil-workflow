# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Audit and Execution Tracking Module.

This module provides comprehensive audit capabilities for workflow execution
tracking and monitoring. It supports multiple audit backends for capturing
execution metadata, status information, and detailed logging.

Be noted that, you can set only one audit backend setting for the current
run-time because it will conflinct audit data if it set more than one audit
backend pointer.

The audit system tracks workflow, job, and stage executions with configurable
storage backends including file-based JSON storage, database persistence, and
more (Up to this package already implement).

That is mean if you release the workflow with the same release date with force mode,
it will overwrite the previous release log. By the way, if you do not pass any
release mode, it will not overwrite the previous release log and return the skip
status to you because it already releases.

Classes:
    BaseAudit: Abstract base class for audit implementations
    FileAudit: File-based audit storage implementation
    SQLiteAudit: SQLite database audit storage implementation

Functions:
    get_audit_model: Factory function for creating audit instances

Example:

    >>> from ddeutil.workflow.audits import get_audit_model
    >>> audit = get_audit_model(run_id="run-123")
    >>> audit.info("Workflow execution started")
    >>> audit.success("Workflow completed successfully")

Note:
    Audit instances are automatically configured based on the workflow
    configuration and provide detailed execution tracking capabilities.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import zlib
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar, Optional, TypeVar, Union
from urllib.parse import ParseResult, urlparse

from pydantic import BaseModel, Field
from pydantic.functional_serializers import field_serializer
from pydantic.functional_validators import field_validator, model_validator
from typing_extensions import Self

from .__types import DictData
from .conf import dynamic
from .traces import TraceManager, get_trace, set_logging

logger = logging.getLogger("ddeutil.workflow")


class BaseAudit(BaseModel, ABC):
    """Base Audit Pydantic Model with abstraction class property.

    This model implements only model fields and should be used as a base class
    for logging subclasses like file, sqlite, etc.
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

    @field_validator("extras", mode="before")
    def validate_extras(cls, v: Any) -> DictData:
        """Validate extras field to ensure it's a dictionary."""
        if v is None:
            return {}
        return v

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

    def do_before(self) -> None:
        """Perform actions before the end of initial log model setup.

        This method is called during model validation and can be overridden
        by subclasses to perform custom initialization actions.
        """

    @abstractmethod
    def save(
        self, excluded: Optional[list[str]] = None
    ) -> Self:  # pragma: no cov
        """Save this model logging to target logging store.

        Args:
            excluded: Optional list of field names to exclude from saving.

        Returns:
            Self: The audit instance after saving.

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
        audit_url = dynamic("audit_url", extras=extras)
        if audit_url is None:
            raise ValueError("audit_url configuration is not set")

        audit_url_parse: ParseResult = urlparse(audit_url)
        pointer: Path = Path(audit_url_parse.path) / f"workflow={name}"
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
            ValueError: If no releases found when release is None.
        """
        if release is None:
            # Find the latest release
            audit_url = dynamic("audit_url", extras=extras)
            if audit_url is None:
                raise ValueError("audit_url configuration is not set")

            audit_url_parse: ParseResult = urlparse(audit_url)
            pointer: Path = Path(audit_url_parse.path) / f"workflow={name}"
            if not pointer.exists():
                raise FileNotFoundError(f"Pointer: {pointer.absolute()}.")

            if not any(pointer.glob("./release=*")):
                raise FileNotFoundError(
                    f"No releases found for workflow: {name}"
                )

            # NOTE: Get the latest release directory
            release_pointer = max(
                pointer.glob("./release=*"), key=os.path.getctime
            )
        else:
            audit_url = dynamic("audit_url", extras=extras)
            if audit_url is None:
                raise ValueError("audit_url configuration is not set")

            audit_url_parse: ParseResult = urlparse(audit_url)
            release_pointer: Path = (
                Path(audit_url_parse.path)
                / f"workflow={name}/release={release:%Y%m%d%H%M%S}"
            )
            if not release_pointer.exists():
                raise FileNotFoundError(
                    f"Pointer: {release_pointer} does not found."
                )

        if not any(release_pointer.glob("./*.log")):
            raise FileNotFoundError(
                f"Pointer: {release_pointer} does not contain any log."
            )

        latest_file: Path = max(
            release_pointer.glob("./*.log"), key=os.path.getctime
        )
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
        audit_url: Optional[str] = dynamic("audit_url", extras=extras)
        if audit_url is None:
            return False

        audit_url_parse: ParseResult = urlparse(audit_url)
        pointer: Path = Path(audit_url_parse.path) / cls.filename_fmt.format(
            name=name, release=release
        )

        return pointer.exists()

    def pointer(self) -> Path:
        """Return release directory path generated from model data.

        Returns:
            Path: The directory path for the current workflow and release.
        """
        audit_url = dynamic("audit_url", extras=self.extras)
        if audit_url is None:
            raise ValueError("audit_url configuration is not set")

        audit_url_parse: ParseResult = urlparse(audit_url)
        return Path(audit_url_parse.path) / self.filename_fmt.format(
            name=self.name, release=self.release
        )

    def save(self, excluded: Optional[list[str]] = None) -> Self:
        """Save logging data received from workflow execution result.

        Args:
            excluded: Optional list of field names to exclude from saving.

        Returns:
            Self: The audit instance after saving.
        """
        trace: TraceManager = get_trace(
            self.run_id,
            parent_run_id=self.parent_run_id,
            extras=self.extras,
        )

        # NOTE: Check environ variable was set for real writing.
        if not dynamic("enable_write_audit", extras=self.extras):
            trace.debug("[AUDIT]: Skip writing audit log cause config was set.")
            return self

        log_file: Path = (
            self.pointer() / f"{self.parent_run_id or self.run_id}.log"
        )

        # NOTE: Convert excluded list to set for pydantic compatibility
        exclude_set = set(excluded) if excluded else None
        trace.info(
            f"[AUDIT]: Start writing audit log with "
            f"release: {self.release:%Y%m%d%H%M%S}"
        )
        log_file.write_text(
            json.dumps(
                self.model_dump(exclude=exclude_set),
                default=str,
                indent=2,
            ),
            encoding="utf-8",
        )
        return self

    def cleanup(self, max_age_days: int = 180) -> int:  # pragma: no cov
        """Clean up old audit files based on its age.

        Args:
            max_age_days: Maximum age in days for audit files to keep.

        Returns:
            int: Number of files cleaned up.
        """
        audit_url = dynamic("audit_url", extras=self.extras)
        if audit_url is None:
            return 0

        audit_url_parse: ParseResult = urlparse(audit_url)
        base_path = Path(audit_url_parse.path)
        cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 3600)
        cleaned_count: int = 0

        for workflow_dir in base_path.glob("workflow=*"):
            for release_dir in workflow_dir.glob("release=*"):
                if release_dir.stat().st_mtime < cutoff_time:
                    import shutil

                    shutil.rmtree(release_dir)
                    cleaned_count += 1

        return cleaned_count


class SQLiteAudit(BaseAudit):  # pragma: no cov
    """SQLite Audit model for database-based audit storage.

    This class inherits from BaseAudit and implements SQLite database storage
    for audit logs with compression support.

    Attributes:
        table_name: Class variable defining the database table name.
        schemas: Class variable defining the database schema.
    """

    table_name: ClassVar[str] = "audits"
    schemas: ClassVar[
        str
    ] = """
        CREATE TABLE IF NOT EXISTS audits (
            workflow        TEXT NOT NULL
            , release       TEXT NOT NULL
            , type          TEXT NOT NULL
            , context       BLOB NOT NULL
            , parent_run_id TEXT
            , run_id        TEXT NOT NULL
            , metadata      BLOB NOT NULL
            , created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            , updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            , PRIMARY KEY ( workflow, release )
        )
        """

    def _ensure_table_exists(self) -> None:
        """Ensure the audit table exists in the database."""
        audit_url = dynamic("audit_url", extras=self.extras)
        if audit_url is None or not audit_url.path:
            raise ValueError(
                "SQLite audit_url must specify a database file path"
            )

        audit_url_parse: ParseResult = urlparse(audit_url)
        db_path = Path(audit_url_parse.path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(db_path) as conn:
            conn.execute(self.schemas)
            conn.commit()

    @classmethod
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
        """
        if not dynamic("enable_write_audit", extras=extras):
            return False

        audit_url = dynamic("audit_url", extras=extras)
        if audit_url is None or not audit_url.path:
            return False

        audit_url_parse: ParseResult = urlparse(audit_url)
        db_path = Path(audit_url_parse.path)
        if not db_path.exists():
            return False

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM audits WHERE workflow = ? AND release = ?",
                (name, release.isoformat()),
            )
            return cursor.fetchone()[0] > 0

    @classmethod
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
        """
        audit_url = dynamic("audit_url", extras=extras)
        if audit_url is None or not audit_url.path:
            return

        audit_url_parse: ParseResult = urlparse(audit_url)
        db_path = Path(audit_url_parse.path)
        if not db_path.exists():
            return

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM audits WHERE workflow = ? ORDER BY release DESC",
                (name,),
            )
            for row in cursor.fetchall():
                # Decompress context and metadata
                context = json.loads(cls._decompress_data(row[3]))
                metadata = json.loads(cls._decompress_data(row[6]))

                yield cls(
                    name=row[0],
                    release=datetime.fromisoformat(row[1]),
                    type=row[2],
                    context=context,
                    parent_run_id=row[4],
                    run_id=row[5],
                    runs_metadata=metadata,
                    extras=extras or {},
                )

    @classmethod
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
            FileNotFoundError: If the specified workflow/release is not found.
        """
        audit_url = dynamic("audit_url", extras=extras)
        if audit_url is None or not audit_url.path:
            raise FileNotFoundError("SQLite database not configured")

        audit_url_parse: ParseResult = urlparse(audit_url)
        db_path = Path(audit_url_parse.path)
        if not db_path.exists():
            raise FileNotFoundError(f"Database file not found: {db_path}")

        with sqlite3.connect(db_path) as conn:
            if release is None:
                # Get latest release
                cursor = conn.execute(
                    "SELECT * FROM audits WHERE workflow = ? ORDER BY release DESC LIMIT 1",
                    (name,),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM audits WHERE workflow = ? AND release = ?",
                    (name, release.isoformat()),
                )

            row = cursor.fetchone()
            if not row:
                raise FileNotFoundError(
                    f"Audit not found for workflow: {name}, release: {release}"
                )

            # Decompress context and metadata
            context = json.loads(cls._decompress_data(row[3]))
            metadata = json.loads(cls._decompress_data(row[6]))

            return cls(
                name=row[0],
                release=datetime.fromisoformat(row[1]),
                type=row[2],
                context=context,
                parent_run_id=row[4],
                run_id=row[5],
                runs_metadata=metadata,
                extras=extras or {},
            )

    @staticmethod
    def _compress_data(data: str) -> bytes:
        """Compress audit data for storage efficiency.

        Args:
            data: JSON string data to compress.

        Returns:
            bytes: Compressed data.
        """
        return zlib.compress(data.encode("utf-8"))

    @staticmethod
    def _decompress_data(data: bytes) -> str:
        """Decompress audit data.

        Args:
            data: Compressed data to decompress.

        Returns:
            str: Decompressed JSON string.
        """
        return zlib.decompress(data).decode("utf-8")

    def save(self, excluded: Optional[list[str]] = None) -> Self:
        """Save logging data received from workflow execution result.

        Args:
            excluded: Optional list of field names to exclude from saving.

        Returns:
            Self: The audit instance after saving.

        Raises:
            ValueError: If SQLite database is not properly configured.
        """
        trace: TraceManager = get_trace(
            self.run_id,
            parent_run_id=self.parent_run_id,
            extras=self.extras,
        )

        # NOTE: Check environ variable was set for real writing.
        if not dynamic("enable_write_audit", extras=self.extras):
            trace.debug("[AUDIT]: Skip writing audit log cause config was set.")
            return self

        audit_url = dynamic("audit_url", extras=self.extras)
        if audit_url is None or not audit_url.path:
            raise ValueError(
                "SQLite audit_url must specify a database file path"
            )

        audit_url_parse: ParseResult = urlparse(audit_url)
        db_path = Path(audit_url_parse.path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Prepare data for storage
        exclude_set = set(excluded) if excluded else None
        model_data = self.model_dump(exclude=exclude_set)

        # Compress context and metadata
        context_blob = self._compress_data(
            json.dumps(model_data.get("context", {}))
        )
        metadata_blob = self._compress_data(
            json.dumps(model_data.get("runs_metadata", {}))
        )

        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO audits
                (workflow, release, type, context, parent_run_id, run_id, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    self.name,
                    self.release.isoformat(),
                    self.type,
                    context_blob,
                    self.parent_run_id,
                    self.run_id,
                    metadata_blob,
                ),
            )
            conn.commit()

        return self

    def cleanup(self, max_age_days: int = 180) -> int:
        """Clean up old audit records based on age.

        Args:
            max_age_days: Maximum age in days for audit records to keep.

        Returns:
            int: Number of records cleaned up.
        """
        audit_url = dynamic("audit_url", extras=self.extras)
        if audit_url is None or not audit_url.path:
            return 0

        audit_url_parse: ParseResult = urlparse(audit_url)
        db_path = Path(audit_url_parse.path)
        if not db_path.exists():
            return 0

        cutoff_date = (
            datetime.now() - timedelta(days=max_age_days)
        ).isoformat()

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM audits WHERE release < ?", (cutoff_date,)
            )
            conn.commit()
            return cursor.rowcount


Audit = Union[
    FileAudit,
    SQLiteAudit,
]
AuditType = TypeVar("AuditType", bound=BaseAudit)


def get_audit_model(
    *,
    extras: Optional[DictData] = None,
) -> type[AuditType]:  # pragma: no cov
    """Get an audit model dynamically based on the config audit path value.

    Args:
        extras: Optional extra parameters to override the core config.
            This function allow you to pass `audit_model_mapping` for override
            the audit model object with your custom model.

    Returns:
        type[Audit]: The appropriate audit model class based on configuration.

    Raises:
        NotImplementedError: If the audit URL scheme is not supported.
    """
    # NOTE: Allow you to override audit model by the extra parameter.
    map_audit_models: dict[str, type[AuditType]] = (extras or {}).get(
        "audit_model_mapping", {}
    )

    audit_url = dynamic("audit_url", extras=extras)
    if audit_url is None:
        return map_audit_models.get("file", FileAudit)

    audit_url_parse: ParseResult = urlparse(audit_url)
    if not audit_url_parse.scheme:
        return map_audit_models.get("file", FileAudit)

    if audit_url_parse.scheme == "sqlite" or (
        audit_url_parse.scheme == "file"
        and Path(audit_url_parse.path).is_file()
    ):
        return map_audit_models.get("sqlite", SQLiteAudit)
    elif audit_url_parse.scheme != "file":
        raise NotImplementedError(
            f"Does not implement the audit model support for URL: {audit_url_parse}"
        )
    return map_audit_models.get("file", FileAudit)
