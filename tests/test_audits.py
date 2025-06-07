import shutil
from datetime import datetime
from unittest import mock

import pytest
from ddeutil.workflow.audits import FileAudit
from ddeutil.workflow.conf import Config


@mock.patch.object(Config, "enable_write_audit", False)
def test_conf_log_file():
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

    assert not FileAudit.is_pointed(
        name="wf-scheduling", release=datetime(2024, 1, 1, 1)
    )


@mock.patch.object(Config, "enable_write_audit", True)
def test_conf_log_file_do_first(root_path):
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

    shutil.rmtree((root_path / pointer).parent)


@mock.patch.object(Config, "enable_write_audit", True)
def test_conf_log_file_find_traces(root_path):
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

    log = next(FileAudit.find_audits(name="wf-scheduling"))
    assert isinstance(log, FileAudit)

    wf_log_path = root_path / "audits/workflow=wf-no-release-log/"
    wf_log_path.mkdir(exist_ok=True)

    for log in FileAudit.find_audits(name="wf-no-release-log"):
        assert isinstance(log, FileAudit)
        log.model_dump(
            by_alias=True,
            exclude_none=True,
            exclude_unset=True,
            exclude_defaults=True,
        )


def test_conf_log_file_find_traces_raise():
    with pytest.raises(FileNotFoundError):
        next(FileAudit.find_audits(name="wf-file-not-found"))


def test_conf_log_file_find_log_with_release():
    with pytest.raises(FileNotFoundError):
        FileAudit.find_audit_with_release(
            name="wf-file-not-found",
            release=datetime(2024, 1, 1, 1),
        )
