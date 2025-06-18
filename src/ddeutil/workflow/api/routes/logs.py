# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""This route include audit and trace log paths."""
from __future__ import annotations

from fastapi import APIRouter, Path, Query
from fastapi import status as st
from fastapi.responses import UJSONResponse

from ...audits import get_audit_model
from ...result import Result

router = APIRouter(
    prefix="/logs",
    tags=["logs"],
    default_response_class=UJSONResponse,
)


@router.get(
    path="/traces/",
    response_class=UJSONResponse,
    status_code=st.HTTP_200_OK,
    summary="Read all trace logs.",
    tags=["trace"],
)
async def get_traces(
    offset: int = Query(default=0, gt=0),
    limit: int = Query(default=100, gt=0),
):
    """Return all trace logs from the current trace log path that config with
    `WORKFLOW_LOG_PATH` environment variable name.
    """
    result = Result()
    return {
        "message": (
            f"Getting trace logs with offset: {offset} and limit: {limit}"
        ),
        "traces": [
            trace.model_dump(
                by_alias=True,
                exclude_none=True,
                exclude_unset=True,
            )
            for trace in result.trace.find_traces()
        ],
    }


@router.get(
    path="/traces/{run_id}",
    response_class=UJSONResponse,
    status_code=st.HTTP_200_OK,
    summary="Read trace log with specific running ID.",
    tags=["trace"],
)
async def get_trace_with_id(run_id: str):
    """Return trace log with specific running ID from the current trace log path
    that config with `WORKFLOW_LOG_PATH` environment variable name.

    - **run_id**: A running ID that want to search a trace log from the log
        path.
    """
    result = Result()
    return {
        "message": f"Getting trace log with specific running ID: {run_id}",
        "trace": (
            result.trace.find_trace_with_id(run_id).model_dump(
                by_alias=True,
                exclude_none=True,
                exclude_unset=True,
            )
        ),
    }


@router.get(
    path="/audits/",
    response_class=UJSONResponse,
    status_code=st.HTTP_200_OK,
    summary="Read all audit logs.",
    tags=["audit"],
)
async def get_audits():
    """Return all audit logs from the current audit log path that config with
    `WORKFLOW_AUDIT_URL` environment variable name.
    """
    return {
        "message": "Getting audit logs",
        "audits": list(get_audit_model().find_audits(name="demo")),
    }


@router.get(
    path="/audits/{workflow}/",
    response_class=UJSONResponse,
    status_code=st.HTTP_200_OK,
    summary="Read all audit logs with specific workflow name.",
    tags=["audit"],
)
async def get_audit_with_workflow(workflow: str):
    """Return all audit logs with specific workflow name from the current audit
    log path that config with `WORKFLOW_AUDIT_URL` environment variable name.

    - **workflow**: A specific workflow name that want to find audit logs.
    """
    return {
        "message": f"Getting audit logs with workflow name {workflow}",
        "audits": list(get_audit_model().find_audits(name="demo")),
    }


@router.get(
    path="/audits/{workflow}/{release}",
    response_class=UJSONResponse,
    status_code=st.HTTP_200_OK,
    summary="Read all audit logs with specific workflow name and release date.",
    tags=["audit"],
)
async def get_audit_with_workflow_release(
    workflow: str = Path(...),
    release: str = Path(...),
):
    """Return all audit logs with specific workflow name and release date from
    the current audit log path that config with `WORKFLOW_AUDIT_URL`
    environment variable name.

    - **workflow**: A specific workflow name that want to find audit logs.
    - **release**: A release date with a string format `%Y%m%d%H%M%S`.
    """
    return {
        "message": (
            f"Getting audit logs with workflow name {workflow} and release "
            f"{release}"
        ),
        "audits": list(get_audit_model().find_audits(name="demo")),
    }


@router.get(
    path="/audits/{workflow}/{release}/{run_id}",
    response_class=UJSONResponse,
    status_code=st.HTTP_200_OK,
    summary=(
        "Read all audit logs with specific workflow name, release date "
        "and running ID."
    ),
    tags=["audit"],
)
async def get_audit_with_workflow_release_run_id(
    workflow: str, release: str, run_id: str
):
    """Return all audit logs with specific workflow name and release date from
    the current audit log path that config with `WORKFLOW_AUDIT_URL`
    environment variable name.

    - **workflow**: A specific workflow name that want to find audit logs.
    - **release**: A release date with a string format `%Y%m%d%H%M%S`.
    - **run_id**: A running ID that want to search audit log from this release
        date.
    """
    return {
        "message": (
            f"Getting audit logs with workflow name {workflow}, release "
            f"{release}, and running ID {run_id}"
        ),
        "audits": list(get_audit_model().find_audits(name="demo")),
    }
