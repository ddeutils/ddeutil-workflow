import json
import os
import shutil
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import pytest
import toml
import yaml
from ddeutil.workflow.conf import Config, Loader, SimLoad, config, dynamic
from ddeutil.workflow.scheduler import Schedule
from ddeutil.workflow.workflow import Workflow


@pytest.fixture(scope="function")
def adjust_config():
    origin_max_job = os.getenv("WORKFLOW_CORE_MAX_JOB_PARALLEL")
    origin_stop = os.getenv("WORKFLOW_APP_STOP_BOUNDARY_DELTA")
    os.environ["WORKFLOW_CORE_MAX_JOB_PARALLEL"] = "-1"
    os.environ["WORKFLOW_APP_STOP_BOUNDARY_DELTA"] = "{"

    yield

    os.environ["WORKFLOW_CORE_MAX_JOB_PARALLEL"] = origin_max_job
    os.environ["WORKFLOW_APP_STOP_BOUNDARY_DELTA"] = origin_stop


def test_config(adjust_config):

    with pytest.raises(ValueError):
        _ = Config().max_job_parallel

    with pytest.raises(ValueError):
        _ = Config().stop_boundary_delta

    conf = Config()
    os.environ["WORKFLOW_CORE_TIMEZONE"] = "Asia/Bangkok"
    assert conf.tz == ZoneInfo("Asia/Bangkok")


@pytest.fixture(scope="module")
def target_path(test_path):
    target_p = test_path / "test_simple_load"
    target_p.mkdir(exist_ok=True)

    with (target_p / "test_simple_file.json").open(mode="w") as f:
        json.dump({"foo": "bar"}, f)

    with (target_p / "test_simple_file.toml").open(mode="w") as f:
        toml.dump({"foo": "bar"}, f)

    yield target_p

    shutil.rmtree(target_p)


def test_simple_load(target_path: Path):
    with mock.patch.object(Config, "conf_path", target_path):

        with pytest.raises(ValueError):
            SimLoad("test_simple_load_raise", config.conf_path)

        with pytest.raises(ValueError):
            SimLoad("wf-ignore-inside", config.conf_path)

        with pytest.raises(ValueError):
            SimLoad("wf-ignore", config.conf_path)


def test_simple_load_finds(target_path: Path):
    dummy_file: Path = target_path / "test_simple_file.yaml"
    with dummy_file.open(mode="w") as f:
        yaml.dump(
            {
                "test_simple_load_config": {
                    "type": "Config",
                    "foo": "bar",
                },
                "test_simple_load": {"type": "Workflow"},
            },
            f,
        )

    with mock.patch.object(Config, "conf_path", target_path):
        assert [
            (
                "test_simple_load_config",
                {"type": "Config", "foo": "bar"},
            )
        ] == list(SimLoad.finds(Config, config.conf_path))
        assert [
            (
                "test_simple_load_config",
                {"type": "Config"},
            )
        ] == list(SimLoad.finds(Config, config.conf_path, included=["type"]))
        assert [] == list(
            SimLoad.finds(
                Config, config.conf_path, excluded=["test_simple_load_config"]
            )
        )

    dummy_file.unlink()


def test_simple_load_finds_raise(target_path: Path):
    dummy_file: Path = target_path / "test_simple_file_raise.yaml"
    with dummy_file.open(mode="w") as f:
        yaml.dump(
            {
                "test_simple_load_config": {
                    "foo": "bar",
                },
                "test_simple_load": {"type": "Workflow"},
            },
            f,
        )

    with mock.patch.object(Config, "conf_path", target_path):
        with pytest.raises(ValueError):
            _ = SimLoad("test_simple_load_config", config.conf_path).type


def test_loader_find_schedule():
    for finding in Loader.finds(Schedule, excluded=[]):
        print(finding)

    for finding in Loader.finds(
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
    for finding in Loader.finds(Workflow, excluded=[]):
        print(finding)


def test_dynamic():
    conf = dynamic("audit_path", extras={"audit_path": Path("/extras-audits")})
    assert conf == Path("/extras-audits")

    conf = dynamic("max_job_exec_timeout", f=10, extras={})
    assert conf == 10

    conf = dynamic("max_job_exec_timeout", f=None, extras={})
    assert conf == 600

    with pytest.raises(TypeError):
        dynamic("audit_path", extras={"audit_path": "audits"})
