# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import UJSONResponse

from ...conf import get_logger

logger = get_logger("ddeutil.workflow")


job_route = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
    default_response_class=UJSONResponse,
)


@job_route.post(path="/execute/")
async def job_execute():
    return {
        "message": "Start execute job.",
    }
