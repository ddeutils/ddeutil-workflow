# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import os
from zoneinfo import ZoneInfo

from ddeutil.core import str2bool
from dotenv import load_dotenv

load_dotenv()
env = os.getenv


class Config:
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

    def __init__(self):
        if self.max_job_parallel < 0:
            raise ValueError(
                f"MAX_JOB_PARALLEL should more than 0 but got "
                f"{self.max_job_parallel}."
            )


config = Config()
