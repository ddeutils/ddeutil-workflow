from collections.abc import Generator
from pathlib import Path

import pytest
from ddeutil.io.param import Params
from ddeutil.workflow.schedule import ScdlBkk


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


def test_schedule(params: Params):
    load = ScdlBkk.from_loader(
        name="scdl_bkk_every_5_minute",
        params=params,
        externals={},
    )
    print(load)
