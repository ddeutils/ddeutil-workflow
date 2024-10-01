# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import json
import os
from datetime import timedelta
from zoneinfo import ZoneInfo

from ddeutil.core import str2bool
from dotenv import load_dotenv

load_dotenv()
env = os.getenv


class Config:
    """Config object for keeping application configuration on current session
    without changing when if the application still running.
    """

    # NOTE: Core
    tz: ZoneInfo = ZoneInfo(env("WORKFLOW_CORE_TIMEZONE", "UTC"))

    # NOTE: Stage
    stage_raise_error: bool = str2bool(
        env("WORKFLOW_CORE_STAGE_RAISE_ERROR", "true")
    )
    stage_default_id: bool = str2bool(
        env("WORKFLOW_CORE_STAGE_DEFAULT_ID", "false")
    )

    # NOTE: Workflow
    max_job_parallel: int = int(env("WORKFLOW_CORE_MAX_JOB_PARALLEL", "2"))

    # NOTE: Schedule App
    max_schedule_process: int = int(env("WORKFLOW_APP_MAX_PROCESS", "2"))
    max_schedule_per_process: int = int(
        env("WORKFLOW_APP_MAX_SCHEDULE_PER_PROCESS", "100")
    )
    __stop_boundary_delta: str = env(
        "WORKFLOW_APP_STOP_BOUNDARY_DELTA", '{"minutes": 5, "seconds": 20}'
    )

    def __init__(self):
        if self.max_job_parallel < 0:
            raise ValueError(
                f"``MAX_JOB_PARALLEL`` should more than 0 but got "
                f"{self.max_job_parallel}."
            )
        try:
            self.stop_boundary_delta: timedelta = timedelta(
                **json.loads(self.__stop_boundary_delta)
            )
        except Exception as err:
            raise ValueError(
                "Config ``WORKFLOW_APP_STOP_BOUNDARY_DELTA`` can not parsing to"
                f"timedelta with {self.__stop_boundary_delta}."
            ) from err

    def refresh_dotenv(self):
        self.tz: ZoneInfo = ZoneInfo(env("WORKFLOW_CORE_TIMEZONE", "UTC"))
        self.stage_raise_error: bool = str2bool(
            env("WORKFLOW_CORE_STAGE_RAISE_ERROR", "true")
        )


config = Config()
