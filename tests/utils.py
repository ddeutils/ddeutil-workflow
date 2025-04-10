# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Any
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
            WORKFLOW_CORE_STAGE_DEFAULT_ID=true
            WORKFLOW_CORE_STAGE_RAISE_ERROR=true
            WORKFLOW_CORE_JOB_DEFAULT_ID=false
            WORKFLOW_CORE_JOB_RAISE_ERROR=true
            WORKFLOW_CORE_GENERATE_ID_SIMPLE_MODE=true
            WORKFLOW_CORE_MAX_NUM_POKING=4
            WORKFLOW_CORE_MAX_JOB_PARALLEL=1
            WORKFLOW_CORE_MAX_JOB_EXEC_TIMEOUT=600
            WORKFLOW_CORE_MAX_CRON_PER_WORKFLOW=5
            WORKFLOW_CORE_MAX_QUEUE_COMPLETE_HIST=16
            WORKFLOW_LOG_TRACE_ENABLE_WRITE=false
            WORKFLOW_LOG_AUDIT_ENABLE_WRITE=true
            WORKFLOW_APP_MAX_PROCESS=2
            WORKFLOW_APP_MAX_SCHEDULE_PER_PROCESS=100
            WORKFLOW_APP_STOP_BOUNDARY_DELTA='{{"minutes": 5, "seconds": 20}}'
            WORKFLOW_API_ENABLE_ROUTE_WORKFLOW=true
            WORKFLOW_API_ENABLE_ROUTE_SCHEDULE=true
            """
        ).strip()
        env_path.write_text(env_str)

    load_dotenv(env_path)


def str2dt(value: str) -> datetime:  # pragma: no cov
    """Convert string value to datetime object with ``fromisoformat`` method.

    :param value: (str): A string value that want to convert to datetime object.

    :rtype: datetime
    """
    return datetime.fromisoformat(value).astimezone(ZoneInfo("Asia/Bangkok"))


def dump_yaml(
    filename: str | Path, data: dict[str, Any] | str
) -> None:  # pragma: no cov
    """Dump the context data to the target yaml file.

    :param filename:
    :param data: A YAML data context that want to write to the target file path.
    """
    with Path(filename).open(mode="w") as f:
        if isinstance(data, str):
            f.write(dedent(data.strip("\n")))
        else:
            yaml.dump(data, f)


@contextmanager
def dump_yaml_context(
    filename: str | Path, data: dict[str, Any] | str
) -> None:  # pragma: no cov
    """Dump the context data to the target yaml file.

    :param filename:
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
