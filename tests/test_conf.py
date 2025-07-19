import json
import os
import shutil
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import pytest
import rtoml
import yaml
from ddeutil.workflow import Workflow
from ddeutil.workflow.conf import (
    Config,
    YamlParser,
    config,
    dynamic,
    pass_env,
)

from .utils import exclude_created_and_updated


def test_config():
    conf = Config()
    os.environ["WORKFLOW_LOG_TIMEZONE"] = "Asia/Bangkok"
    assert conf.log_tz == ZoneInfo("Asia/Bangkok")


@pytest.fixture(scope="module")
def target_path(test_path):
    target_p = test_path / "test_load_file"
    target_p.mkdir(exist_ok=True)

    with (target_p / "test_simple_file.json").open(mode="w") as f:
        json.dump({"foo": "bar"}, f)

    with (target_p / "test_simple_file.toml").open(mode="w") as f:
        rtoml.dump({"foo": "bar", "env": "${ WORKFLOW_LOG_TIMEZONE }"}, f)

    yield target_p

    shutil.rmtree(target_p)


@pytest.fixture(scope="module")
def mock_conf(test_path: Path):
    target_p = test_path / "test_read_file"
    target_p.mkdir(exist_ok=True)

    with (target_p / "wf_1.yaml").open(mode="w") as f:
        yaml.dump(
            {
                "wf_1": {
                    "type": "Workflow",
                    "value": 1,
                    "tags": [
                        1,
                    ],
                }
            },
            f,
        )

    with (target_p / "wf_2.yaml").open(mode="w") as f:
        yaml.dump(
            {
                "wf_2": {
                    "type": "Workflow",
                    "value": 2,
                    "tags": [
                        2,
                    ],
                }
            },
            f,
        )

    with (target_p / "wf_3.yaml").open(mode="w") as f:
        yaml.dump(
            {
                "wf_3": {
                    "value": 3,
                    "tags": [
                        3,
                    ],
                }
            },
            f,
        )

    with (target_p / "wf_4.yaml").open(mode="w") as f:
        yaml.dump({"wf_4": {"type": "Custom", "value": 4}}, f)

    yield target_p

    shutil.rmtree(target_p)


def test_yaml_parser(target_path: Path):
    with pytest.raises(ValueError):
        YamlParser("test_load_file_raise", path=target_path)

    with pytest.raises(ValueError):
        YamlParser("wf-ignore-inside", path=target_path)

    with pytest.raises(ValueError):
        YamlParser("wf-ignore", path=target_path)

    with (target_path / "test_simple_file_raise.yaml").open(mode="w") as f:
        yaml.dump(
            {
                "test_load_file": {
                    "type": "Workflow",
                    "desc": "Test multi config path",
                    "env": "${WORKFLOW_LOG_TIMEZONE}",
                },
                "test_load_not_set_type": {
                    "desc": "Test load not set type.",
                },
            },
            f,
        )

    load = YamlParser("test_load_file", extras={"conf_paths": [target_path]})
    assert exclude_created_and_updated(load.data) == {
        "name": "test_load_file",
        "type": "Workflow",
        "desc": "Test multi config path",
        "env": "${WORKFLOW_LOG_TIMEZONE}",
    }
    assert pass_env(load.data["env"]) == "Asia/Bangkok"
    assert exclude_created_and_updated(pass_env(load.data)) == {
        "name": "test_load_file",
        "type": "Workflow",
        "desc": "Test multi config path",
        "env": "Asia/Bangkok",
    }

    load = YamlParser(
        "test_load_file", extras={"conf_paths": [target_path]}, obj="Workflow"
    )
    assert exclude_created_and_updated(load.data) == {
        "name": "test_load_file",
        "type": "Workflow",
        "desc": "Test multi config path",
        "env": "${WORKFLOW_LOG_TIMEZONE}",
    }

    # NOTE: Raise because passing `conf_paths` invalid type.
    with pytest.raises(TypeError):
        YamlParser("test_load_file", extras={"conf_paths": target_path})

    load = YamlParser(
        "test_load_not_set_type", extras={"conf_paths": [target_path]}
    )
    with pytest.raises(ValueError):
        _ = load.type


@pytest.fixture(scope="function")
def mock_workflow_with_name_key(test_path):
    target_p = test_path / "test_read_file_with_name_key"
    target_p.mkdir(exist_ok=True)

    with (target_p / "wf_1.yaml").open(mode="w") as f:
        yaml.dump(
            {
                "name": "wf_1",
                "type": "Workflow",
                "value": 1,
                "tags": [
                    1,
                ],
            },
            f,
        )

    with (target_p / "wf_2.yaml").open(mode="w") as f:
        yaml.dump(
            {
                "name": "wf_2",
                "type": "Workflow",
                "value": 1,
                "tags": [
                    1,
                ],
            },
            f,
        )

    yield target_p

    shutil.rmtree(target_p)


def test_yaml_parser_with_name_key(mock_workflow_with_name_key):
    assert exclude_created_and_updated(
        YamlParser(
            "wf_1", extras={"conf_paths": [mock_workflow_with_name_key]}
        ).data
    ) == {"name": "wf_1", "tags": [1], "type": "Workflow", "value": 1}

    with pytest.raises(ValueError):
        YamlParser(
            "wf_not_exists",
            extras={"conf_paths": [mock_workflow_with_name_key]},
        )


def test_yaml_parser_find_with_filter(mock_conf: Path):
    assert (
        "wf_1",
        {"tags": [1], "type": "Workflow", "value": 1},
    ) in exclude_created_and_updated(
        list(YamlParser.finds("Workflow", path=mock_conf))
    )
    assert (
        "wf_2",
        {"tags": [2], "type": "Workflow", "value": 2},
    ) in exclude_created_and_updated(
        list(YamlParser.finds("Workflow", path=mock_conf))
    )

    assert exclude_created_and_updated(
        list(YamlParser.finds("Workflow", path=mock_conf, tags=[1]))
    ) == [("wf_1", {"tags": [1], "type": "Workflow", "value": 1})]

    assert exclude_created_and_updated(
        list(YamlParser.finds("Custom", path=mock_conf, tags=[]))
    ) == [("wf_4", {"type": "Custom", "value": 4})]

    assert (
        exclude_created_and_updated(
            list(YamlParser.finds("Custom", path=mock_conf, tags=[1]))
        )
        == []
    )

    assert (
        exclude_created_and_updated(
            list(YamlParser.finds("Custom", path=mock_conf, tags=[1]))
        )
        == []
    )
    assert (
        exclude_created_and_updated(
            list(YamlParser.finds("Custom", paths=[mock_conf], tags=[1]))
        )
        == []
    )

    assert exclude_created_and_updated(
        YamlParser.find("wf_1", path=mock_conf)
    ) == {"name": "wf_1", "tags": [1], "type": "Workflow", "value": 1}
    assert exclude_created_and_updated(
        YamlParser.find("wf_2", path=mock_conf)
    ) == {"name": "wf_2", "tags": [2], "type": "Workflow", "value": 2}
    assert (
        exclude_created_and_updated(
            YamlParser.find("wf_3", path=mock_conf, obj="Workflow")
        )
        == {}
    )
    assert exclude_created_and_updated(
        YamlParser.find("wf_4", path=mock_conf, obj="Custom")
    ) == {"name": "wf_4", "type": "Custom", "value": 4}

    with pytest.raises(TypeError):
        list(YamlParser.finds("Custom", paths={"path": mock_conf}, tags=[1]))


def test_yaml_parser_finds(target_path: Path):
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
        ] == exclude_created_and_updated(
            list(YamlParser.finds(Config, path=config.conf_path))
        )

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
    ] == exclude_created_and_updated(
        list(YamlParser.finds("Workflow", path=target_path))
    )

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
    ] == exclude_created_and_updated(
        list(YamlParser.finds("Workflow", path=target_path))
    )

    load = YamlParser.find("test_load_file", path=target_path, obj="Workflow")
    assert exclude_created_and_updated(load) == {
        "name": "test_load_file",
        "type": "Workflow",
        "data": "foo",
    }

    # NOTE: Load with the same name, but it set different type.
    load = YamlParser.find("test_load_file", path=target_path, obj="Config")
    assert exclude_created_and_updated(load) == {
        "name": "test_load_file",
        "type": "Config",
        "data": "bar",
    }

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


def test_test_yaml_parser_finds_example(test_path: Path):
    for data in YamlParser.finds(
        Workflow, path=test_path.parent / "docs/examples/conf"
    ):
        print(data[0])
        Workflow.model_validate(data[1])

    assert (
        len(
            list(
                YamlParser.finds(
                    Workflow,
                    paths=[test_path.parent / "docs/examples/conf"],
                    include_conf_path=False,
                )
            )
        )
        == 11
    )


def test_load_ignore_file(test_path: Path):
    assert YamlParser.find("wf-ignore", path=test_path / "conf") == {}

    assert YamlParser.find("wf-not-exists", path=test_path / "conf") == {}


def test_dynamic():
    conf = dynamic("log_datetime_format", f="%Y%m%d", extras={})
    assert conf == "%Y%m%d"

    conf = dynamic("log_datetime_format", f=None, extras={})
    assert conf == "%Y-%m-%d %H:%M:%S"

    conf = dynamic(
        "log_datetime_format", f="%Y%m%d", extras={"log_datetime_format": "%Y"}
    )
    assert conf == "%Y"

    conf = dynamic("max_job_exec_timeout", f=500, extras={})
    assert conf == 500

    with pytest.raises(TypeError):
        dynamic(
            "max_job_exec_timeout", f=50, extras={"max_job_exec_timeout": False}
        )

    conf = dynamic("max_job_exec_timeout", f=0, extras={})
    assert conf == 0

    conf = dynamic("trace_handlers", extras={})
    assert conf == [{"type": "console"}]
