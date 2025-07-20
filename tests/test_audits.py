import shutil
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest
from ddeutil.workflow.audits import (
    NORMAL,
    AuditData,
    BaseAudit,
    FileAudit,
    SQLiteAudit,
    get_audit,
)
from ddeutil.workflow.conf import Config


def test_get_audit_model():
    model = get_audit()
    assert isinstance(model, FileAudit)

    model = get_audit(
        extras={"audit_conf": {"type": "sqlite", "path": "./audit.db"}}
    )
    assert isinstance(model, SQLiteAudit)


def test_audit_data():
    audit = AuditData.model_validate(
        {
            "name": "wf-scheduling",
            "type": "normal",
            "release": datetime(2024, 1, 1, 1),
            "run_id": "558851633820240817184358131811",
        }
    )
    assert audit.name == "wf-scheduling"


@mock.patch.multiple(BaseAudit, __abstractmethods__=set())
def test_base_audit():
    log = BaseAudit.model_validate(
        {
            "type": "test",
            "extras": {
                "foo": "bar",
                "datetime": datetime(2024, 1, 1, 1, 15),
            },
        }
    )
    assert log.model_dump() == {
        "type": "test",
        "extras": {"foo": "bar", "datetime": datetime(2024, 1, 1, 1, 15)},
    }


@mock.patch.object(Config, "enable_write_audit", False)
def test_audit_file():
    log = FileAudit(path="./audits")
    audit = AuditData.model_validate(
        obj={
            "name": "wf-scheduling-not-exists",
            "type": NORMAL,
            "release": datetime(2024, 1, 1, 1),
            "context": {
                "params": {"name": "foo"},
            },
            "parent_run_id": None,
            "run_id": "558851633820240817184358131811",
            "update": datetime.now(),
        },
    )
    log.save(audit, excluded=None)

    assert not log.is_pointed(audit)


@mock.patch.object(Config, "enable_write_audit", True)
def test_audit_file_do_first():
    log = FileAudit(path="./audits")
    audit = AuditData.model_validate(
        {
            "name": "wf-demo-logging",
            "type": "normal",
            "release": datetime(2024, 1, 1, 1),
            "context": {
                "params": {"name": "logging"},
            },
            "parent_run_id": None,
            "run_id": "558851633820240817184358131811",
            "update": datetime.now(),
        }
    )
    log.save(data=audit, excluded=None)
    pointer = log.pointer(audit)
    assert pointer.exists()
    #
    # log = FileAudit.find_audit_with_release(
    #     name="wf-demo-logging",
    #     release=datetime(2024, 1, 1, 1),
    # )
    # assert log.name == "wf-demo-logging"
    #
    # shutil.rmtree(pointer.parent)


@mock.patch.object(Config, "enable_write_audit", True)
def test_audit_file_find(root_path):
    log = FileAudit(path="./audits")
    audit = AuditData.model_validate(
        {
            "name": "wf-scheduling",
            "type": "normal",
            "release": datetime(2024, 1, 1, 1),
            "context": {
                "params": {"name": "foo"},
            },
            "parent_run_id": None,
            "run_id": "558851633820240817184358131811",
            "update": datetime.now(),
        }
    )
    log.save(data=audit, excluded=None)

    assert log.is_pointed(audit)

    audit = next(log.find_audits(name="wf-scheduling"))
    assert isinstance(audit, AuditData)
    assert audit.name == "wf-scheduling"
    assert audit.release == datetime(2024, 1, 1, 1)

    audit = log.find_audit_with_release(name="wf-scheduling")
    assert isinstance(audit, AuditData)
    assert audit.name == "wf-scheduling"
    assert audit.release == datetime(2024, 1, 1, 1)

    audit = log.find_audit_with_release(
        name="wf-scheduling", release=datetime(2024, 1, 1, 1)
    )
    assert isinstance(audit, AuditData)
    assert audit.name == "wf-scheduling"
    assert audit.release == datetime(2024, 1, 1, 1)


def test_audit_file_find_empty():
    wf_log_path = Path("./audits/workflow=wf-no-release-log/")
    wf_log_path.mkdir(exist_ok=True)
    log = FileAudit()
    assert list(log.find_audits(name="wf-no-release-log")) == []

    with pytest.raises(FileNotFoundError):
        log.find_audit_with_release(name="wf-no-release-log")

    wf_log_release_path = wf_log_path / "release=20240101010000"
    wf_log_release_path.mkdir(exist_ok=True)
    assert list(log.find_audits(name="wf-no-release-log")) == []

    with pytest.raises(FileNotFoundError):
        log.find_audit_with_release(name="wf-no-release-log")

    shutil.rmtree(wf_log_path)


def test_audit_file_find_raise():
    log = FileAudit()
    with pytest.raises(FileNotFoundError):
        next(log.find_audits(name="wf-file-not-found"))


def test_audit_file_find_with_release():
    log = FileAudit()
    with pytest.raises(FileNotFoundError):
        log.find_audit_with_release(
            name="wf-file-not-found",
            release=datetime(2024, 1, 1, 1),
        )

    with pytest.raises(FileNotFoundError):
        log.find_audit_with_release(name="wf-file-not-found")
