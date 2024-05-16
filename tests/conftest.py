from pathlib import Path

import pytest

collect_ignore = [
    "vendors",
    "test_conn.py",
]


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
