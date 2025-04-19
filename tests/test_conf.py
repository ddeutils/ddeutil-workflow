import json
import os
import shutil
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import pytest
import toml
import yaml
from ddeutil.workflow.conf import Config, FileLoad, config, dynamic
from ddeutil.workflow.scheduler import Schedule
from ddeutil.workflow.workflow import Workflow


def test_config():
    origin_stop = os.getenv("WORKFLOW_APP_STOP_BOUNDARY_DELTA")
    os.environ["WORKFLOW_APP_STOP_BOUNDARY_DELTA"] = "{"

    with pytest.raises(ValueError):
        _ = Config().stop_boundary_delta

    os.environ["WORKFLOW_APP_STOP_BOUNDARY_DELTA"] = origin_stop

    conf = Config()
    os.environ["WORKFLOW_CORE_TIMEZONE"] = "Asia/Bangkok"
    assert conf.tz == ZoneInfo("Asia/Bangkok")


@pytest.fixture(scope="module")
def target_path(test_path):
    target_p = test_path / "test_load_file"
    target_p.mkdir(exist_ok=True)

    with (target_p / "test_simple_file.json").open(mode="w") as f:
        json.dump({"foo": "bar"}, f)

    with (target_p / "test_simple_file.toml").open(mode="w") as f:
        toml.dump({"foo": "bar"}, f)

    yield target_p

    shutil.rmtree(target_p)


def test_load_file(target_path: Path):
    with mock.patch.object(Config, "conf_path", target_path):

        with pytest.raises(ValueError):
            FileLoad("test_load_file_raise", path=config.conf_path)

        with pytest.raises(ValueError):
            FileLoad("wf-ignore-inside", path=config.conf_path)

        with pytest.raises(ValueError):
            FileLoad("wf-ignore", path=config.conf_path)


def test_load_file_finds(target_path: Path):
    dummy_file: Path = target_path / "test_simple_file.yaml"
    with dummy_file.open(mode="w") as f:
        yaml.dump(
            {
                "test_load_file_config": {
                    "type": "Config",
                    "foo": "bar",
                },
                "test_load_file": {"type": "Workflow"},
            },
            f,
        )

    with mock.patch.object(Config, "conf_path", target_path):
        assert [
            (
                "test_load_file_config",
                {"type": "Config", "foo": "bar"},
            )
        ] == list(FileLoad.finds(Config, path=config.conf_path))
        assert [
            (
                "test_load_file_config",
                {"type": "Config"},
            )
        ] == list(
            FileLoad.finds(Config, path=config.conf_path, included=["type"])
        )
        assert [] == list(
            FileLoad.finds(
                Config,
                path=config.conf_path,
                excluded=["test_load_file_config"],
            )
        )

    dummy_file.unlink()


def test_load_file_finds_raise(target_path: Path):
    dummy_file: Path = target_path / "test_simple_file_raise.yaml"
    with dummy_file.open(mode="w") as f:
        yaml.dump(
            {
                "test_load_file_config": {
                    "foo": "bar",
                },
                "test_load_file": {"type": "Workflow"},
            },
            f,
        )

    with mock.patch.object(Config, "conf_path", target_path):
        with pytest.raises(ValueError):
            _ = FileLoad("test_load_file_config", path=config.conf_path).type


def test_loader_find_schedule():
    for finding in FileLoad.finds(Schedule, excluded=[]):
        print(finding)

    for finding in FileLoad.finds(
        Schedule,
        excluded=[
            "schedule-common-wf",
            "schedule-multi-on-wf",
            "schedule-every-minute-wf",
            "schedule-every-minute-wf-parallel",
        ],
    ):
        print(finding[0])


def test_loader_find_workflow():
    for finding in FileLoad.finds(Workflow, excluded=[]):
        print(finding)


def test_dynamic():
    conf = dynamic("audit_path", extras={"audit_path": Path("/extras-audits")})
    assert conf == Path("/extras-audits")

    conf = dynamic("max_cron_per_workflow", f=10, extras={})
    assert conf == 10

    conf = dynamic("max_cron_per_workflow", f=None, extras={})
    assert conf == 5

    with pytest.raises(TypeError):
        dynamic("audit_path", extras={"audit_path": "audits"})

    conf = dynamic("max_job_exec_timeout", f=500, extras={})
    assert conf == 500

    conf = dynamic("max_job_exec_timeout", f=0, extras={})
    assert conf == 0
