import math
import os
from pathlib import Path

import pytest

from .utils import dotenv_setting

dotenv_setting()


@pytest.fixture(scope="session")
def root_path() -> Path:
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def test_path(root_path) -> Path:
    return root_path / "tests"


@pytest.fixture(scope="session")
def conf_path(test_path: Path) -> Path:
    return test_path / "conf"


def pytest_collection_modifyitems(
    session: pytest.Session, config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Ref: https://guicommits.com/parallelize-pytest-tests-github-actions/"""
    # 👇 Make these vars optional so locally we don't have to set anything
    current_worker = int(os.getenv("GITHUB_WORKER_ID", 0)) - 1
    total_workers = int(os.getenv("GITHUB_TOTAL_WORKERS", 0))

    # 👇 If there's no workers we can affirm we won't split
    if total_workers:
        # 👇 Decide how many tests per worker
        num_tests = len(items)
        matrix_size = math.ceil(num_tests / total_workers)

        # 👇 Select the test range with start and end
        start = current_worker * matrix_size
        end = (current_worker + 1) * matrix_size

        # 👇 Set how many tests are going to be deselected
        deselected_items = items[:start] + items[end:]
        config.hook.pytest_deselected(items=deselected_items)

        # 👇 Set which tests are going to be handled
        items[:] = items[start:end]
        print(f" Executing {start} - {end} tests")
