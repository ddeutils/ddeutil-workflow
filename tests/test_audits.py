import shutil
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest
from ddeutil.workflow.audits import (
    BaseAudit,
    FileAudit,
    SQLiteAudit,
    get_audit_model,
)
from ddeutil.workflow.conf import Config
from pydantic import ValidationError


def test_get_audit_model():
    model = get_audit_model(extras={"audit_url": "demo/test"})
    assert model is FileAudit

    model = get_audit_model(extras={"audit_url": None})
    assert model is FileAudit

    model = get_audit_model(extras={"audit_url": "sqlite:///demo/foo.db"})
    assert model is SQLiteAudit

    with mock.patch.object(Config, "audit_url", None):
        assert get_audit_model() is FileAudit


@mock.patch.multiple(BaseAudit, __abstractmethods__=set())
def test_base_audit():
    audit = BaseAudit.model_validate(
        {
            "name": "wf-scheduling",
            "type": "manual",
            "release": datetime(2024, 1, 1, 1),
            "run_id": "558851633820240817184358131811",
        }
    )
    assert audit.do_before() is None

    # NOTE: Raise because extras field should be dict or None.
    with pytest.raises(ValidationError):
        BaseAudit.model_validate(
            {
                "name": "wf-scheduling",
                "type": "manual",
                "release": datetime(2024, 1, 1, 1),
                "run_id": "558851633820240817184358131811",
                "extras": "foo",
            }
        )


@mock.patch.object(Config, "enable_write_audit", False)
def test_audit_file():
    log = FileAudit.model_validate(
        obj={
            "name": "wf-scheduling",
            "type": "manual",
            "release": datetime(2024, 1, 1, 1),
            "context": {
                "params": {"name": "foo"},
            },
            "parent_run_id": None,
            "run_id": "558851633820240817184358131811",
            "update": datetime.now(),
            "extras": None,
        },
    )
    log.save(excluded=None)

    assert not FileAudit.is_pointed(
        name="wf-scheduling", release=datetime(2024, 1, 1, 1)
    )


@mock.patch.object(Config, "enable_write_audit", True)
def test_audit_file_enable():
    with mock.patch.object(Config, "audit_url", None):
        assert not FileAudit.is_pointed(
            "not-exists", release=datetime(2025, 1, 1)
        )


def test_audit_file_raise():
    with mock.patch.object(Config, "audit_url", None):
        with pytest.raises(ValueError):
            next(FileAudit.find_audits(name="bar"))


@mock.patch.object(Config, "enable_write_audit", True)
def test_audit_file_do_first():
    log = FileAudit.model_validate(
        obj={
            "name": "wf-demo-logging",
            "type": "manual",
            "release": datetime(2024, 1, 1, 1),
            "context": {
                "params": {"name": "logging"},
            },
            "parent_run_id": None,
            "run_id": "558851633820240817184358131811",
            "update": datetime.now(),
        },
    )
    log.save(excluded=None)
    pointer = log.pointer()

    log = FileAudit.find_audit_with_release(
        name="wf-demo-logging",
        release=datetime(2024, 1, 1, 1),
    )
    assert log.name == "wf-demo-logging"

    shutil.rmtree(pointer.parent)


@mock.patch.object(Config, "enable_write_audit", True)
def test_audit_file_find(root_path):
    log = FileAudit.model_validate(
        obj={
            "name": "wf-scheduling",
            "type": "manual",
            "release": datetime(2024, 1, 1, 1),
            "context": {
                "params": {"name": "foo"},
            },
            "parent_run_id": None,
            "run_id": "558851633820240817184358131811",
            "update": datetime.now(),
        },
    )
    log.save(excluded=None)

    assert FileAudit.is_pointed(
        name="wf-scheduling", release=datetime(2024, 1, 1, 1)
    )

    with mock.patch.object(Config, "audit_url", None):
        with pytest.raises(ValueError):
            log.pointer()

    log = next(FileAudit.find_audits(name="wf-scheduling"))
    assert isinstance(log, FileAudit)
    assert log.name == "wf-scheduling"
    assert log.release == datetime(2024, 1, 1, 1)

    log = FileAudit.find_audit_with_release(name="wf-scheduling")
    assert isinstance(log, FileAudit)
    assert log.name == "wf-scheduling"
    assert log.release == datetime(2024, 1, 1, 1)

    log = FileAudit.find_audit_with_release(
        name="wf-scheduling", release=datetime(2024, 1, 1, 1)
    )
    assert isinstance(log, FileAudit)
    assert log.name == "wf-scheduling"
    assert log.release == datetime(2024, 1, 1, 1)


def test_audit_file_find_empty():
    wf_log_path = Path("audits/workflow=wf-no-release-log/")
    wf_log_path.mkdir(exist_ok=True)

    assert list(FileAudit.find_audits(name="wf-no-release-log")) == []

    with pytest.raises(FileNotFoundError):
        FileAudit.find_audit_with_release(name="wf-no-release-log")

    wf_log_release_path = wf_log_path / "release=20240101010000"
    wf_log_release_path.mkdir(exist_ok=True)
    assert list(FileAudit.find_audits(name="wf-no-release-log")) == []

    with pytest.raises(FileNotFoundError):
        FileAudit.find_audit_with_release(name="wf-no-release-log")

    shutil.rmtree(wf_log_path)


def test_audit_file_find_raise():
    with pytest.raises(FileNotFoundError):
        next(FileAudit.find_audits(name="wf-file-not-found"))


def test_audit_file_find_with_release():
    with pytest.raises(FileNotFoundError):
        FileAudit.find_audit_with_release(
            name="wf-file-not-found",
            release=datetime(2024, 1, 1, 1),
        )

    with pytest.raises(FileNotFoundError):
        FileAudit.find_audit_with_release(name="wf-file-not-found")

    with mock.patch.object(Config, "audit_url", None):
        with pytest.raises(ValueError):
            FileAudit.find_audit_with_release(
                name="audit_path is None",
                release=datetime(2024, 1, 1, 1),
            )

        with pytest.raises(ValueError):
            FileAudit.find_audit_with_release(name="audit_path is None")
