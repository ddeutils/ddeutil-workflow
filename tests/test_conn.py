from collections.abc import Generator
from pathlib import Path

import pytest
from ddeutil.io.param import Params
from ddeutil.workflow.conn import Conn


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
                    "archive": test_path / ".archive",
                    "root": root_path,
                },
            },
            "stages": {
                "raw": {"format": "{naming:%s}.{timestamp:%Y%m%d_%H%M%S}"},
            },
        }
    )


def test_connection_file(params: Params):
    load = Conn.from_loader(
        name="conn_local_file",
        params=params,
        externals={},
    )
    print(load.extras)


def test_connection_sftp(params: Params):
    load = Conn.from_loader(
        name="conn_sftp",
        params=params,
        externals={},
    )
    print(load.extras)
