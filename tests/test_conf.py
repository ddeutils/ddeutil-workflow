import json
import os
import shutil
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import pytest
import rtoml
import yaml
from ddeutil.workflow.conf import (
    Config,
    YamlParser,
    config,
    dynamic,
    pass_env,
)


def test_config():
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
        rtoml.dump({"foo": "bar", "env": "${ WORKFLOW_CORE_TIMEZONE }"}, f)

    yield target_p

    shutil.rmtree(target_p)


def test_load_file(target_path: Path):
    with mock.patch.object(Config, "conf_path", target_path):

        with pytest.raises(ValueError):
            YamlParser("test_load_file_raise", path=config.conf_path)

        with pytest.raises(ValueError):
            YamlParser("wf-ignore-inside", path=config.conf_path)

        with pytest.raises(ValueError):
            YamlParser("wf-ignore", path=config.conf_path)

    with (target_path / "test_simple_file_raise.yaml").open(mode="w") as f:
        yaml.dump(
            {
                "test_load_file": {
                    "type": "Workflow",
                    "desc": "Test multi config path",
                    "env": "${WORKFLOW_CORE_TIMEZONE}",
                }
            },
            f,
        )

    load = YamlParser("test_load_file", extras={"conf_paths": [target_path]})
    assert load.data == {
        "type": "Workflow",
        "desc": "Test multi config path",
        "env": "${WORKFLOW_CORE_TIMEZONE}",
    }
    assert pass_env(load.data["env"]) == "Asia/Bangkok"
    assert pass_env(load.data) == {
        "type": "Workflow",
        "desc": "Test multi config path",
        "env": "Asia/Bangkok",
    }

    load = YamlParser(
        "test_load_file", extras={"conf_paths": [target_path]}, obj="Workflow"
    )
    assert load.data == {
        "type": "Workflow",
        "desc": "Test multi config path",
        "env": "${WORKFLOW_CORE_TIMEZONE}",
    }

    # NOTE: Raise because passing `conf_paths` invalid type.
    with pytest.raises(TypeError):
        YamlParser("test_load_file", extras={"conf_paths": target_path})


def test_load_file_finds(target_path: Path):
    dummy_file: Path = target_path / "01_test_simple_file.yaml"
    with dummy_file.open(mode="w") as f:
        yaml.dump(
            {
                "test_load_file_config": {
                    "type": "Config",
                    "foo": "bar",
                },
                "test_load_file": {"type": "Workflow", "data": "foo"},
            },
            f,
        )

    with mock.patch.object(Config, "conf_path", target_path):
        assert [
            (
                "test_load_file_config",
                {"type": "Config", "foo": "bar"},
            )
        ] == list(YamlParser.finds(Config, path=config.conf_path))

        assert [] == list(
            YamlParser.finds(
                Config,
                path=config.conf_path,
                excluded=["test_load_file_config"],
            )
        )

    # NOTE: Create duplicate data with the first order by filename.
    dummy_file_dup: Path = target_path / "00_test_simple_file_duplicate.yaml"
    with dummy_file_dup.open(mode="w") as f:
        yaml.dump(
            {"test_load_file": {"type": "Workflow", "data": "bar"}},
            f,
        )

    assert [
        (
            "test_load_file",
            {"type": "Workflow", "data": "bar"},
        ),
    ] == list(YamlParser.finds("Workflow", path=target_path))

    dummy_file_dup.unlink()

    # NOTE: Create duplicate data with the first order by filename.
    dummy_file_dup: Path = target_path / "00_test_simple_file_duplicate.yaml"
    with dummy_file_dup.open(mode="w") as f:
        yaml.dump(
            {"test_load_file": {"type": "Config", "data": "bar"}},
            f,
        )

    assert [
        (
            "test_load_file",
            {"type": "Workflow", "data": "foo"},
        ),
    ] == list(YamlParser.finds("Workflow", path=target_path))

    load = YamlParser.find("test_load_file", path=target_path, obj="Workflow")
    assert load == {"type": "Workflow", "data": "foo"}

    # NOTE: Load with the same name, but it set different type.
    load = YamlParser.find("test_load_file", path=target_path, obj="Config")
    assert load == {"type": "Config", "data": "bar"}

    load = YamlParser.find("test_load_file", path=target_path, obj="Crontab")
    assert load == {}

    dummy_file.unlink()


def test_load_file_finds_raise(target_path: Path):
    dummy_file: Path = target_path / "test_simple_file_raise.yaml"
    with dummy_file.open(mode="w") as f:
        yaml.dump(
            {"test_load_file": {"type": "Workflow"}},
            f,
        )

    with mock.patch.object(Config, "conf_path", target_path):
        with pytest.raises(ValueError):
            _ = YamlParser("test_load_file_config", path=config.conf_path).type

        assert (
            YamlParser("test_load_file", path=config.conf_path).type
            == "Workflow"
        )


def test_dynamic():
    conf = dynamic("audit_path", extras={"audit_path": Path("/extras-audits")})
    assert conf == Path("/extras-audits")

    conf = dynamic("log_datetime_format", f="%Y%m%d", extras={})
    assert conf == "%Y%m%d"

    conf = dynamic("log_datetime_format", f=None, extras={})
    assert conf == "%Y-%m-%d %H:%M:%S"

    conf = dynamic(
        "log_datetime_format", f="%Y%m%d", extras={"log_datetime_format": "%Y"}
    )
    assert conf == "%Y"

    with pytest.raises(TypeError):
        dynamic("audit_path", extras={"audit_path": "audits"})

    conf = dynamic("max_job_exec_timeout", f=500, extras={})
    assert conf == 500

    conf = dynamic("max_job_exec_timeout", f=0, extras={})
    assert conf == 0
