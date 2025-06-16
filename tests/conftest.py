# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

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
