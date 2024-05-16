from pathlib import Path

import pytest

collect_ignore = [
    "vendors",
    "test_loader.py",
    "test_connection.py",
]


@pytest.fixture(scope="session")
def test_path() -> Path:
    return Path(__file__).parent


def root_path(test_path: Path) -> Path:
    return test_path.parent


@pytest.fixture(scope="session")
def example_path(test_path: Path) -> Path:
    return test_path / "examples" / "conf"


@pytest.fixture(scope="session")
def conf_path(example_path: Path) -> Path:
    return example_path / "conf"
