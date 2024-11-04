from datetime import datetime
from unittest import mock

import pytest
from ddeutil.workflow.conf import Config, FileLog


@mock.patch.object(Config, "enable_write_log", False)
def test_conf_log_file():
    log = FileLog.model_validate(
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

    assert not FileLog.is_pointed(
        name="wf-scheduling", release=datetime(2024, 1, 1, 1)
    )


@mock.patch.object(Config, "enable_write_log", True)
def test_conf_log_file_do_first():
    log = FileLog.model_validate(
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
    log = FileLog.find_log_latest(
        name="wf-demo-logging",
        release=datetime(2024, 1, 1, 1),
    )
    assert log.name == "wf-demo-logging"


@mock.patch.object(Config, "enable_write_log", True)
def test_conf_log_file_find_logs(root_path):
    log = FileLog.model_validate(
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

    assert FileLog.is_pointed(
        name="wf-scheduling", release=datetime(2024, 1, 1, 1)
    )

    log = next(FileLog.find_logs(name="wf-scheduling"))
    assert isinstance(log, FileLog)

    wf_log_path = root_path / "logs/workflow=wf-no-release-log/"
    wf_log_path.mkdir(exist_ok=True)

    for log in FileLog.find_logs(name="wf-no-release-log"):
        assert isinstance(log, FileLog)


def test_conf_log_file_find_logs_raise():
    with pytest.raises(FileNotFoundError):
        next(FileLog.find_logs(name="wf-file-not-found"))


def test_conf_log_file_find_log_latest():
    with pytest.raises(FileNotFoundError):
        FileLog.find_log_latest(
            name="wf-file-not-found",
            release=datetime(2024, 1, 1, 1),
        )
