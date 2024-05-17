import shutil
from collections.abc import Generator
from pathlib import Path

import ddeutil.pipe.loader as ld
import pytest
from ddeutil.io.param import Params
from ddeutil.pipe.workflow import Workflow


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
    if (test_path / ".cache").exists():
        shutil.rmtree(test_path / ".cache")


def test_loader(params: Params):
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


def test_simple_loader(params: Params):
    load = ld.SimLoad(
        name="conn_local_file",
        params=params,
        externals={},
    )
    assert {
        'type': 'connection.LocalFileStorage',
        'endpoint': 'file:///null/tests/examples/dummy'
    } == load.data


def test_simple_loader_workflow_run_py(params: Params):
    load = ld.SimLoad(
        name='run_python_local',
        params=params,
        externals={},
    )
    assert load.type == Workflow
    param: str = 'Parameter'
    g = {'x': param}
    exec(
        load.data.get('jobs')[0].get('demo_run').get('stages')[0].get('run'),
        g,
    )

    exec(
        load.data.get('jobs')[0].get('demo_run').get('stages')[1].get('run'),
        g,
    )

    assert 1 == g['x']
