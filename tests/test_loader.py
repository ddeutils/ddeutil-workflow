from pathlib import Path

import ddeutil.pipe.loader as ld
import pytest
from ddeutil.io.models import Params


@pytest.fixture(scope='module')
def params(conf_path: Path, test_path: Path, root_path: Path) -> Params:
    return Params.model_validate(
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


def test_base_loader_init(params):
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
            "endpoint": "file:///null/tests/examples/dummy",
            "type": "connection.LocalFileStorage",
        }
        == load.data
    )
