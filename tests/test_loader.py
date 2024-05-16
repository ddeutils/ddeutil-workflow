from pathlib import Path

import ddeutil.pipe.loader as ld
import pytest
from ddeutil.io.models import Params


@pytest.fixture(scope='module')
def param(test_path: Path, root_path: Path) -> Params:
    return Params.model_validate(
        {
            "engine": {
                "paths": {
                    "conf": test_path / "examples/conf",
                    "data": root_path / "data",
                    "archive": root_path / "/data/.archive",
                    "root": root_path,
                },
            },
            "stages": {
                "raw": {"format": "{naming:%s}.{timestamp:%Y%m%d_%H%M%S}"},
            },
        }
    )


def test_base_loader_init(params):
    load: ld.BaseLoader = ld.BaseLoader.from_register(
        name="demo:conn_local_data_landing",
        params=params,
        # params={"audit_date": "2023-12-01 00:00:00"},
    )
    assert (
        {
            "alias": "conn_local_data_landing",
            "endpoint": (
                "file:///D:/korawica/Work/dev02_miniproj/ddeutil-node/"
                "tests/examples/dummy"
            ),
            "type": "connection.LocalFileStorage",
        }
        == load.data
    )
