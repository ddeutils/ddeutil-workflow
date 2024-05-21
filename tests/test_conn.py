import os

import ddeutil.workflow.conn as conn
import pytest
from ddeutil.io.param import Params


def test_connection_file(params_simple: Params):
    connection = conn.FlSys.from_loader(
        name="conn_local_file",
        params=params_simple,
        externals={},
    )
    assert connection.host is None
    assert connection.port is None
    assert connection.user is None
    assert connection.pwd is None
    assert "data/examples/" == connection.endpoint


def test_connection_file_url(params_simple: Params):
    connection = conn.FlSys.from_loader(
        name="conn_local_file_url",
        params=params_simple,
        externals={},
    )
    assert (
        f"{os.getenv('ROOT_PATH')}/tests/data/examples" == connection.endpoint
    )
    assert connection.host is None
    assert connection.port is None
    assert connection.user is None
    assert connection.pwd is None
    assert connection.ping()
    for p in connection.glob("*.db"):
        assert p.name == "demo_sqlite.db"


def test_connection_file_url_ubuntu(params_simple: Params):
    connection = conn.FlSys.from_loader(
        name="conn_local_file_url_ubuntu",
        params=params_simple,
        externals={},
    )
    assert connection.host is None
    assert connection.port is None
    assert connection.user is None
    assert connection.pwd is None
    assert "/absolute/path/to/foo" == connection.endpoint


def test_connection_file_url_relative(params_simple: Params):
    connection = conn.FlSys.from_loader(
        name="conn_local_file_url_relative",
        params=params_simple,
        externals={},
    )
    assert connection.host is None
    assert connection.port is None
    assert connection.user is None
    assert connection.pwd is None
    assert "data/examples/" == connection.endpoint


@pytest.mark.skipif(True, reason="Because SFTP server does not provisioning")
def test_connection_sftp(params_simple: Params):
    connection = conn.SFTP.from_loader(
        name="conn_sftp",
        params=params_simple,
        externals={},
    )
    assert "data" == connection.endpoint
    assert connection.ping()
    for f in connection.glob("/"):
        print(f)


def test_connection_sqlite(params_simple: Params):
    connection = conn.SqliteConn.from_loader(
        name="conn_sqlite_url", params=params_simple, externals={}
    )
    connection.ping()


def test_connection_sqlite_failed(params_simple: Params):
    connection = conn.SqliteConn.from_loader(
        name="conn_sqlite_url_failed", params=params_simple, externals={}
    )
    assert not connection.ping()
