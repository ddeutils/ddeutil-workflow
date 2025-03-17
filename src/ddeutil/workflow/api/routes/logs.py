# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""This route include audit and trace log paths."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi import status as st
from fastapi.responses import UJSONResponse

from ...audit import get_audit
from ...logs import get_trace_obj

log_route = APIRouter(
    prefix="/logs",
    tags=["logs", "trace", "audit"],
    default_response_class=UJSONResponse,
)


@log_route.get(
    path="/trace/",
    response_class=UJSONResponse,
    status_code=st.HTTP_200_OK,
    summary="Read all trace logs.",
)
async def get_traces():
    """Return all trace logs from the current trace log path that config with
    `WORKFLOW_LOG_PATH` environment variable name.
    """
    return {
        "message": "Getting trace logs",
        "traces": [
            trace.model_dump(
                by_alias=True,
                exclude_none=True,
                exclude_unset=True,
                exclude_defaults=True,
            )
            for trace in get_trace_obj().find_logs()
        ],
    }


@log_route.get(
    path="/trace/{run_id}",
    response_class=UJSONResponse,
    status_code=st.HTTP_200_OK,
    summary="Read trace log with specific running ID.",
)
async def get_trace_with_id(run_id: str):
    """Return trace log with specific running ID from the current trace log path
    that config with `WORKFLOW_LOG_PATH` environment variable name.

    - **run_id**: A running ID that want to search a trace log from the log
        path.
    """
    return {
        "message": f"Getting trace log with specific running ID: {run_id}",
        "trace": (
            get_trace_obj()
            .find_log_with_id(run_id)
            .model_dump(
                by_alias=True,
                exclude_none=True,
                exclude_unset=True,
                exclude_defaults=True,
            )
        ),
    }


@log_route.get(path="/audit/")
async def get_audits():
    """Get all audit logs."""
    return {
        "message": "Getting audit logs",
        "audits": list(get_audit().find_audits(name="demo")),
    }


@log_route.get(path="/audit/{workflow}/")
async def get_audit_with_workflow(workflow: str):
    """Get all audit logs."""
    return {
        "message": f"Getting audit logs with workflow name {workflow}",
        "audits": list(get_audit().find_audits(name="demo")),
    }


@log_route.get(path="/audit/{workflow}/{release}")
async def get_audit_with_workflow_release(workflow: str, release: str):
    """Get audit logs with specific workflow and release values."""
    return {
        "message": (
            f"Getting audit logs with workflow name {workflow} and release "
            f"{release}"
        ),
        "audits": list(get_audit().find_audits(name="demo")),
    }


@log_route.get(path="/audit/{workflow}/{release}/{run_id}")
async def get_audit_with_workflow_release_run_id(workflow: str, release: str):
    """Get all audit logs."""
    return {
        "message": (
            f"Getting audit logs with workflow name {workflow} and release "
            f"{release}"
        ),
        "audits": list(get_audit().find_audits(name="demo")),
    }
