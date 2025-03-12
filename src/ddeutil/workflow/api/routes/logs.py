# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import UJSONResponse

from ...audit import get_audit
from ...logs import get_trace_obj

log_route = APIRouter(
    prefix="/logs",
    tags=["logs", "trace", "audit"],
    default_response_class=UJSONResponse,
)


@log_route.get(path="/trace/")
async def get_traces():
    """Get all trace logs."""
    return {
        "message": "Getting trace logs",
        "traces": list(get_trace_obj().find_logs()),
    }


@log_route.get(path="/trace/{run_id}")
async def get_trace_with_id(run_id: str):
    """Get trace log with specific running ID."""
    return get_trace_obj().find_log_with_id(run_id)


@log_route.get(path="/audit/")
async def get_audits():
    """Get all audit logs."""
    return {
        "message": "Getting audit logs",
        "audits": list(get_audit().find_audits(name="demo")),
    }
