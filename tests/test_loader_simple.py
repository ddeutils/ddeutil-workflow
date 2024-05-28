from collections.abc import Generator
from pathlib import Path

import ddeutil.workflow.loader as ld
import pytest
from ddeutil.io.param import Params
from ddeutil.workflow.pipeline import Pipeline
from ddeutil.workflow.schedule import ScdlBkk

from .utils import str2dt


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
        name="run_python",
        params=params,
        externals={},
    )
    assert load.type == Pipeline

    x: str = "Init"
    param: str = "Parameter"
    g: dict[str, str] = {"x": param}
    for stage in load.data.get("jobs").get("demo-run").get("stages"):
        exec(stage.get("run"), g)

    # NOTE: the `x` variable will change because the stage.
    assert 1 == g["x"]

    # NOTE: Make sore that `x` on this local does not change.
    assert "Init" == x


def test_simple_loader_schedule(params: Params):
    load = ld.SimLoad(
        name="scdl_bkk_every_5_minute",
        params=params,
        externals={},
    )
    assert ScdlBkk == load.type

    scdl: ScdlBkk = load.type.model_validate(
        obj={"cronjob": load.data["cronjob"]}
    )
    cronjob_iter = scdl.generate("2024-01-01 00:00:00")
    t = cronjob_iter.next
    assert str2dt("2024-01-01 00:00:00").tzinfo == t.tzinfo
    assert f"{t:%Y%m%d%H%M%S}" == "20240101000000"
    assert str2dt("2024-01-01 00:00:00") == t
    assert str2dt("2024-01-01 00:05:00") == cronjob_iter.next
