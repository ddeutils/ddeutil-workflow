# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

OUTSIDE_PATH: Path = Path(__file__).parent.parent


def dotenv_setting() -> None:
    """Create .env file if this file in the current path do not exists."""
    env_path: Path = OUTSIDE_PATH / ".env"
    if not env_path.exists():
        logging.warning("Dot env file does not exists")
        # NOTE: For ``ROOT_PATH`` value on the different OS:
        #   * Windows: D:\user\path\...\ddeutil-workflow
        #   * Ubuntu: /home/runner/work/ddeutil-workflow/ddeutil-workflow
        #
        env_str: str = dedent(
            f"""
            WORKFLOW_ROOT_PATH={OUTSIDE_PATH.resolve()}
            WORKFLOW_CORE_REGISTRY=src.ddeutil.workflow,tests
            WORKFLOW_CORE_REGISTRY_FILTER=ddeutil.workflow.utils
            WORKFLOW_CORE_PATH_CONF=tests/conf
            WORKFLOW_CORE_PATH_CONF=tests/conf
            WORKFLOW_CORE_TIMEZONE=Asia/Bangkok
            WORKFLOW_CORE_STAGE_DEFAULT_ID=true
            WORKFLOW_CORE_STAGE_RAISE_ERROR=true
            WORKFLOW_CORE_JOB_DEFAULT_ID=false
            WORKFLOW_CORE_JOB_RAISE_ERROR=true
            WORKFLOW_CORE_GENERATE_ID_SIMPLE_MODE=true
            WORKFLOW_CORE_MAX_NUM_POKING=4
            WORKFLOW_CORE_MAX_JOB_PARALLEL=1
            WORKFLOW_CORE_MAX_JOB_EXEC_TIMEOUT=600
            WORKFLOW_LOG_ENABLE_WRITE=true
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
    """Convert string value to datetime object with ``fromisoformat`` method."""
    return datetime.fromisoformat(value).astimezone(ZoneInfo("Asia/Bangkok"))
