import os

import ddeutil.workflow.conn as conn
import pytest


def test_connection_file():
    connection = conn.FlSys.from_loader(
        name="conn_local_file",
        externals={},
    )
    assert connection.host is None
    assert connection.port is None
    assert connection.user is None
    assert connection.pwd is None
    assert "data/examples" == connection.endpoint


def test_connection_file_url():
    connection = conn.FlSys.from_loader(
        name="conn_local_file_url",
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


def test_connection_file_url_ubuntu():
    connection = conn.FlSys.from_loader(
        name="conn_local_file_url_ubuntu",
        externals={},
    )
    assert "/home/runner/work/foo" == connection.endpoint
    assert connection.host is None
    assert connection.port is None
    assert connection.user is None
    assert connection.pwd is None


def test_connection_file_ubuntu():
    connection = conn.FlSys.from_loader(
        name="conn_local_file_ubuntu",
        externals={},
    )
    assert "/home/runner/work/foo" == connection.endpoint
    assert connection.host is None
    assert connection.port is None
    assert connection.user is None
    assert connection.pwd is None


def test_connection_file_url_relative():
    connection = conn.FlSys.from_loader(
        name="conn_local_file_url_relative",
        externals={},
    )
    assert connection.host is None
    assert connection.port is None
    assert connection.user is None
    assert connection.pwd is None
    assert "data/examples/" == connection.endpoint


@pytest.mark.skipif(True, reason="Because SFTP server does not provisioning")
def test_connection_sftp():
    connection = conn.SFTP.from_loader(
        name="conn_sftp",
        externals={},
    )
    assert "data" == connection.endpoint
    assert connection.ping()
    for f in connection.glob("/"):
        print(f)


def test_connection_sqlite():
    connection = conn.SQLite.from_loader(name="conn_sqlite_url", externals={})
    connection.ping()


def test_connection_sqlite_failed():
    connection = conn.SQLite.from_loader(
        name="conn_sqlite_url_failed", externals={}
    )
    assert not connection.ping()
