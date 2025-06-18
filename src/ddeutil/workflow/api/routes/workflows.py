# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi import status as st
from fastapi.responses import UJSONResponse
from pydantic import BaseModel

from ...__types import DictData
from ...audits import Audit, get_audit_model
from ...conf import YamlParser
from ...result import Result
from ...workflow import Workflow

logger = logging.getLogger("uvicorn.error")
router = APIRouter(
    prefix="/workflows",
    tags=["workflows"],
    default_response_class=UJSONResponse,
)


@router.get(path="/", status_code=st.HTTP_200_OK)
async def get_workflows() -> DictData:
    """Return all workflow workflows that exists in config path."""
    workflows: DictData = dict(YamlParser.finds(Workflow))
    return {
        "message": f"Getting all workflows: {len(workflows)}",
        "count": len(workflows),
        "workflows": workflows,
    }


@router.get(path="/{name}", status_code=st.HTTP_200_OK)
async def get_workflow_by_name(name: str) -> DictData:
    """Return model of workflow that passing an input workflow name."""
    try:
        workflow: Workflow = Workflow.from_conf(name=name, extras={})
    except ValueError as err:
        logger.exception(err)
        raise HTTPException(
            status_code=st.HTTP_404_NOT_FOUND,
            detail=(
                f"Workflow workflow name: {name!r} does not found in /conf path"
            ),
        ) from None
    return workflow.model_dump(
        by_alias=True,
        exclude_none=False,
        exclude_unset=True,
    )


class ExecutePayload(BaseModel):
    params: dict[str, Any]


@router.post(path="/{name}/execute", status_code=st.HTTP_202_ACCEPTED)
async def workflow_execute(name: str, payload: ExecutePayload) -> DictData:
    """Return model of workflow that passing an input workflow name."""
    try:
        workflow: Workflow = Workflow.from_conf(name=name, extras={})
    except ValueError:
        raise HTTPException(
            status_code=st.HTTP_404_NOT_FOUND,
            detail=(
                f"Workflow workflow name: {name!r} does not found in /conf path"
            ),
        ) from None

    # NOTE: Start execute manually
    try:
        result: Result = workflow.execute(params=payload.params)
    except Exception as err:
        raise HTTPException(
            status_code=st.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{type(err)}: {err}",
        ) from None

    return asdict(result)


@router.get(path="/{name}/audits", status_code=st.HTTP_200_OK)
async def get_workflow_audits(name: str):
    try:
        return {
            "message": f"Getting workflow {name!r} audits",
            "audits": [
                audit.model_dump(
                    by_alias=True,
                    exclude_none=False,
                    exclude_unset=True,
                )
                for audit in get_audit_model().find_audits(name=name)
            ],
        }
    except FileNotFoundError:
        raise HTTPException(
            status_code=st.HTTP_404_NOT_FOUND,
            detail=f"Does not found audit for workflow {name!r}",
        ) from None


@router.get(path="/{name}/audits/{release}", status_code=st.HTTP_200_OK)
async def get_workflow_release_audit(name: str, release: str):
    """Get Workflow audit log with an input release value."""
    try:
        audit: Audit = get_audit_model().find_audit_with_release(
            name=name,
            release=datetime.strptime(release, "%Y%m%d%H%M%S"),
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=st.HTTP_404_NOT_FOUND,
            detail=(
                f"Does not found audit for workflow {name!r} "
                f"with release {release!r}"
            ),
        ) from None
    return {
        "message": f"Getting workflow {name!r} audit in release {release}",
        "audit": audit.model_dump(
            by_alias=True,
            exclude_none=False,
            exclude_unset=True,
        ),
    }
