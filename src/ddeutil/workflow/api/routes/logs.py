# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import UJSONResponse

from ...logs import get_trace_obj

log_route = APIRouter(
    prefix="/logs",
    tags=["logs"],
    default_response_class=UJSONResponse,
)


@log_route.get(path="/")
async def get_logs():
    """Get all logs."""
    return {
        "message": "Getting logs",
        "audits": list(get_trace_obj().find_logs()),
    }


@log_route.get(path="/{run_id}")
async def get_log_with_run_id(run_id: str):
    """Get log with specific running ID."""
    return get_trace_obj().find_log_with_id(run_id)
