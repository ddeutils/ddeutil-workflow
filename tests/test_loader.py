import shutil
from collections.abc import Generator
from datetime import datetime
from pathlib import Path

import ddeutil.workflow.loader as ld
import pytest
from ddeutil.io.param import Params
from ddeutil.workflow.pipeline import Pipeline
from ddeutil.workflow.schedule import ScdlBkk


@pytest.fixture(scope="module")
def params(
    conf_path: Path,
    test_path: Path,
    root_path: Path,
) -> Generator[Params, None, None]:
    yield Params.model_validate(
        {
            "engine": {
                "paths": {
                    "conf": conf_path,
                    "data": test_path / ".cache",
                    "root": root_path,
                },
            },
            "stages": {
                "raw": {"format": "{naming:%s}.{timestamp:%Y%m%d_%H%M%S}"},
            },
        }
    )
    if (test_path / ".cache").exists():
        shutil.rmtree(test_path / ".cache")


def test_loader(params: Params):
    load: ld.BaseLoad = ld.BaseLoad.from_register(
        name="demo:conn_local_file",
        params=params,
        externals={
            "audit_date": "2024-01-01 00:12:45",
        },
    )
    assert {
        "alias": "conn_local_file",
        "endpoint": "C:/user/data",
        "type": "conn.LocalFl",
    } == load.data


def test_simple_loader(params: Params):
    load = ld.SimLoad(
        name="conn_local_file",
        params=params,
        externals={},
    )
    assert {
        "type": "conn.LocalFl",
        "endpoint": "C:/user/data",
    } == load.data


def test_simple_loader_workflow_run_py(params: Params):
    load = ld.SimLoad(
        name="run_python_local",
        params=params,
        externals={},
    )
    assert load.type == Pipeline

    x: str = "Init"
    param: str = "Parameter"
    g = {"x": param}
    print(load.data)
    for stage in load.data.get("jobs").get("demo-run").get("stages"):
        exec(stage.get("run"), g)

    # NOTE: the `x` variable will change because the stage.
    assert 1 == g["x"]

    # NOTE: Make sore that `x` on this local does not change.
    assert "Init" == x

    assert {
        "run_date": datetime(2024, 1, 1, 0),
        "name": "Parameter",
    } == load.validate_params(
        param={
            "run_date": "2024-01-01",
            "name": "Parameter",
        }
    )


def test_simple_loader_schedule(params: Params):
    load = ld.SimLoad(
        name="scdl_bkk_every_5_minute",
        params=params,
        externals={},
    )
    assert ScdlBkk == load.type

    scdl: ScdlBkk = load.type(cronjob=load.data["cronjob"])
    cronjob_iter = scdl.generate("2024-01-01 00:00:00")
    assert "2024-01-01 00:00:00" == f"{cronjob_iter.next:%Y-%m-%d %H:%M:%S}"
    assert "2024-01-01 00:05:00" == f"{cronjob_iter.next:%Y-%m-%d %H:%M:%S}"
