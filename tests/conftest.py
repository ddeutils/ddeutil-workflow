from pathlib import Path

import pytest

from .utils import dotenv_setting, initial_sqlite

collect_ignore: list[str] = [
    "vendors",
]

dotenv_setting()
initial_sqlite()


@pytest.fixture(scope="session")
def root_path() -> Path:
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def test_path(root_path) -> Path:
    return root_path / "tests"


@pytest.fixture(scope="session")
def data_path(test_path: Path) -> Path:
    return test_path / "data"


@pytest.fixture(scope="session")
def conf_path(data_path: Path) -> Path:
    return data_path / "conf"
