# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""This route include audit log path."""
from __future__ import annotations

from fastapi import APIRouter, Path, Query
from fastapi import status as st
from fastapi.responses import UJSONResponse

from ...audits import get_audit

router = APIRouter(
    prefix="/logs",
    tags=["logs"],
    default_response_class=UJSONResponse,
)


@router.get(
    path="/audits/",
    response_class=UJSONResponse,
    status_code=st.HTTP_200_OK,
    summary="Read all audit logs.",
    tags=["audit"],
)
async def get_audits(
    offset: int = Query(default=0, gt=0),
    limit: int = Query(default=100, gt=0),
):
    """Return all audit logs from the current audit log path that config with
    `WORKFLOW_AUDIT_URL` environment variable name.
    """
    return {
        "message": (
            f"Getting audit logs with offset: {offset} and limit: {limit}",
        ),
        "audits": list(get_audit().find_audits(name="demo")),
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
        "audits": list(get_audit().find_audits(name="demo")),
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
        "audits": list(get_audit().find_audits(name="demo")),
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
        "audits": list(get_audit().find_audits(name="demo")),
    }
