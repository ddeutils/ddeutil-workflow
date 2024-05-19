from collections.abc import Generator
from pathlib import Path

import ddeutil.workflow.conn as conn
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


def test_connection_file(params: Params):
    connection = conn.FlConn.from_loader(
        name="conn_local_file",
        params=params,
        externals={},
    )
    print(connection)
    # assert connection.ping()


def test_connection_file_url_relative(params: Params):
    connection = conn.FlConn.from_loader(
        name="conn_local_file_url_relative",
        params=params,
        externals={},
    )
    print(connection)


def test_connection_sftp(params: Params):
    connection = conn.Conn.from_loader(
        name="conn_sftp",
        params=params,
        externals={},
    )
    print(connection.extras)
