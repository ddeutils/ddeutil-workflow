# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()
env = os.getenv


class Config:
    tz: ZoneInfo = ZoneInfo(env("WORKFLOW_CORE_TIMEZONE", "UTC"))
    max_job_parallel: int = int(env("WORKFLOW_CORE_MAX_JOB_PARALLEL", "2"))

    def __init__(self):
        if self.max_job_parallel < 0:
            raise ValueError(
                f"MAX_JOB_PARALLEL should more than 0 but got "
                f"{self.max_job_parallel}."
            )


config = Config()
