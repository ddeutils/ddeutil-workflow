import shutil
from collections.abc import Generator
from pathlib import Path

import ddeutil.pipe.loader as ld
import pytest
from ddeutil.io.models import Params


@pytest.fixture(scope='module')
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
                    "archive": test_path / ".archive",
                    "root": root_path,
                },
            },
            "stages": {
                "raw": {"format": "{naming:%s}.{timestamp:%Y%m%d_%H%M%S}"},
            },
        }
    )
    shutil.rmtree(test_path / ".cache")


def test_base_loader(params):
    load: ld.BaseLoad = ld.BaseLoad.from_register(
        name="demo:conn_local_file",
        params=params,
        externals={
            "audit_date": "2024-01-01 00:12:45",
        }
    )
    assert (
        {
            "alias": "conn_local_file",
            "host": "/C:/user/data",
            "type": "conn.LocalFlSys",
            "?endpoint": "dwh",
        }
        == load.data
    )
