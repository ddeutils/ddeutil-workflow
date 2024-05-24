import shutil
from collections.abc import Generator
from pathlib import Path

import ddeutil.workflow.loader as ld
import pytest
from ddeutil.io.param import Params


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


def test_base_loader(params: Params):
    load: ld.BaseLoad = ld.BaseLoad.from_register(
        name="demo:conn_local_file",
        params=params,
        externals={
            "audit_date": "2024-01-01 00:12:45",
        },
    )
    assert {
        "alias": "conn_local_file",
        "endpoint": "data/examples/",
        "type": "conn.FlSys",
    } == load.data


def test_loader(conf_path):
    loader = ld.Loader.config()
    assert conf_path == loader.engine.paths.conf
