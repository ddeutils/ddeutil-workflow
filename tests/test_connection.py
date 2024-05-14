import os
import pathlib
import unittest

import ddeutil.node.loader as ld
import pytest
from ddeutil.io.models import Params


@pytest.mark.usefixtures("test_path_to_cls")
class ConnectionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.demo_path: pathlib.Path = self.test_path / "examples" / "conf"
        self.params: Params = Params.model_validate(
            {
                "engine": {
                    "paths": {
                        "conf": self.test_path / "examples/conf",
                        "data": self.root_path / "data",
                        "archive": self.root_path / "/data/.archive",
                        "root": self.root_path,
                    },
                },
                "stages": {
                    "raw": {"format": "{naming:%s}.{timestamp:%Y%m%d_%H%M%S}"},
                },
            }
        )
        os.environ["APP_PATH"] = "D:/korawica/Work/dev02_miniproj/ddeutil-node"

    def test_connection_init(self):
        conn: ld.Conn = ld.Conn.from_catalog(
            name="demo:conn_local_file",
            config=self.params,
            params={"audit_date": "2023-12-01 00:00:00"},
            refresh=True,
        )
        self.assertDictEqual(
            {
                "alias": "conn_local_file",
                "endpoint": (
                    "file:///D:/korawica/Work/dev02_miniproj/ddeutil-node"
                    "/tests/examples/dummy"
                ),
                "type": "connection.LocalFileStorage",
            },
            conn.data,
        )
        conn_linked = conn.link()
        p: pathlib.Path
        for p in conn_linked.list_objects("*.csv"):
            print(type(p), p)
        self.assertTrue(conn_linked.exists(path="customer_csv.type01.csv"))

    def test_connection_sftp(self):
        conn: ld.Conn = ld.Conn.from_catalog(
            name="demo:conn_sftp",
            config=self.params,
            params={"audit_date": "2023-12-01 00:00:00"},
            refresh=True,
        )
        from sqlalchemy import make_url

        make_url(conn.data["endpoint"])
        conn_linked = conn.link()
        for p in conn_linked.list_objects():
            print(type(p), p)
