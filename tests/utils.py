# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from threading import Event, Lock
from typing import Any, Optional, Union
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv

OUTSIDE_PATH: Path = Path(__file__).parent.parent


def dotenv_setting() -> None:
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
            WORKFLOW_CORE_TIMEZONE=Asia/Bangkok
            WORKFLOW_CORE_DEBUG_MODE=true
            WORKFLOW_CORE_STAGE_DEFAULT_ID=true
            WORKFLOW_CORE_STAGE_RAISE_ERROR=true
            WORKFLOW_CORE_GENERATE_ID_SIMPLE_MODE=true
            WORKFLOW_LOG_TRACE_ENABLE_WRITE=false
            WORKFLOW_LOG_AUDIT_ENABLE_WRITE=true
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
        self.n: int = n
        self.counter: int = 0
        self.lock: Lock = Lock()

    def is_set(self) -> bool:
        with self.lock:
            if self.counter == self.n:
                return True
            self.counter += 1
            return False

    def set(self) -> None:
        with self.lock:
            self.counter = self.n

    def clear(self):
        self.counter = 0

    def wait(self, timeout=None):
        raise NotImplementedError(
            "MockEvent object does not override the `wait` method."
        )
