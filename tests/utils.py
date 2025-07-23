# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import logging
import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from threading import Event, RLock
from typing import Any, Optional, Union
from zoneinfo import ZoneInfo

import yaml
from ddeutil.core import str2bool
from dotenv import load_dotenv

OUTSIDE_PATH: Path = Path(__file__).parent.parent


def dotenv_setting() -> None:  # pragma: no cov
    """Create .env file if this file in the current path does not exist."""
    env_path: Path = OUTSIDE_PATH / ".env"
    if not env_path.exists():
        logging.warning("Dot env file does not exists")
        # NOTE: For ``CONF_ROOT_PATH`` value on the different OS:
        #   * Windows: D:\user\path\...\ddeutil-workflow
        #   * Ubuntu: /home/runner/work/ddeutil-workflow/ddeutil-workflow
        #
        env_str: str = dedent(
            f"""
            WORKFLOW_CORE_REGISTRY_CALLER=tests
            WORKFLOW_CORE_REGISTRY_FILTER=src.ddeutil.workflow.reusables
            WORKFLOW_CORE_CONF_PATH={(OUTSIDE_PATH / "tests/conf").absolute()}
            WORKFLOW_CORE_DEBUG_MODE=true
            WORKFLOW_CORE_STAGE_DEFAULT_ID=true
            WORKFLOW_CORE_GENERATE_ID_SIMPLE_MODE=true
            WORKFLOW_LOG_TIMEZONE=Asia/Bangkok
            WORKFLOW_LOG_AUDIT_CONF='{{"type": "file", "path": "./audits"}}'
            WORKFLOW_LOG_AUDIT_ENABLE_WRITE=true
            WORKFLOW_LOG_TRACE_HANDLERS='[{{"type": "console"}}]'
            WORKFLOW_TEST_CLEAN_UP=true
            """
        ).strip()
        env_path.write_text(env_str)

    load_dotenv(env_path)


def str2dt(value: str, tz: Optional[str] = None) -> datetime:  # pragma: no cov
    """Convert string value to datetime object with ``fromisoformat`` method.

    :param value: (str): A string value that want to convert to datetime object.
    :param tz: (str)

    :rtype: datetime
    """
    return datetime.fromisoformat(value).astimezone(
        ZoneInfo(tz or "Asia/Bangkok")
    )


def dump_yaml(
    filename: Union[str, Path], data: Union[dict[str, Any], str]
) -> None:  # pragma: no cov
    """Dump the context data to the target yaml file.

    :param filename: (str | Path) A file path or filename of a YAML config.
    :param data: A YAML data context that want to write to the target file path.
    """
    with Path(filename).open(mode="w") as f:
        if isinstance(data, str):
            f.write(dedent(data.strip("\n")))
        else:
            yaml.dump(data, f)


@contextmanager
def dump_yaml_context(
    filename: Union[str, Path], data: Union[dict[str, Any], str]
) -> Iterator[Path]:  # pragma: no cov
    """Dump the context data to the target yaml file.

    :param filename: (str | Path) A file path or filename of a YAML config.
    :param data: A YAML data context that want to write to the target file path.
    """
    test_file: Path = Path(filename) if isinstance(filename, str) else filename
    with test_file.open(mode="w") as f:
        if isinstance(data, str):
            f.write(dedent(data.strip("\n")))
        else:
            yaml.dump(data, f)

    yield test_file

    # NOTE: Remove the testing file.
    test_file.unlink(missing_ok=True)


class MockEvent(Event):  # pragma: no cov
    """Mock Event object that override the core methods of Event for force set
    from parent thread of its function lineage.
    """

    def __init__(self, n: int = 1):
        super().__init__()
        self.n: int = n
        self.counter: int = 0
        self.lock: RLock = RLock()

    def is_set(self) -> bool:
        """Check if the counter value is equal to n."""
        with self.lock:
            if self.counter == self.n:
                return True
            self.counter += 1
            return False

    def set(self) -> None:
        """Set the counter value to n."""
        with self.lock:
            self.counter = self.n

    def clear(self) -> None:
        """Clear the counter value to 0."""
        with self.lock:
            self.counter = 0

    def wait(self, timeout=None):
        raise NotImplementedError(
            "MockEvent object does not override the `wait` method."
        )


def exclude_keys(value: Any, keys: list[str]) -> Any:  # pragma: no cov
    """Exclude keys for assert the specific keys only."""
    if isinstance(value, dict):
        return {
            k: exclude_keys(v, keys=keys)
            for k, v in value.items()
            if k not in keys
        }
    elif isinstance(value, (list, tuple, set)):
        return type(value)(exclude_keys(i, keys=keys) for i in value)
    return value


def exclude_created_and_updated(value: Any) -> Any:  # pragma: no cov
    return exclude_keys(value, keys=["created_at", "updated_at"])


def clean_up(path: Union[str, Path]) -> None:  # pragma: no cov
    if str2bool(os.getenv("WORKFLOW_TEST_CLEAN_UP", "true")):
        shutil.rmtree(path)
