import pathlib
import unittest

import ddeutil.node.base.loader as ld
import pytest
from ddeutil.io.models import Params


@pytest.mark.usefixtures("test_path_to_cls")
class BaseLoaderTestCase(unittest.TestCase):
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

    def test_base_loader_init(self):
        load: ld.BaseLoader = ld.BaseLoader.from_catalog(
            name="demo:conn_local_data_landing",
            config=self.params,
            params={"audit_date": "2023-12-01 00:00:00"},
        )
        self.assertDictEqual(
            {
                "alias": "conn_local_data_landing",
                "endpoint": (
                    "file:///D:/korawica/Work/dev02_miniproj/ddeutil-node/"
                    "tests/examples/dummy"
                ),
                "type": "connection.LocalFileStorage",
            },
            load.data,
        )
