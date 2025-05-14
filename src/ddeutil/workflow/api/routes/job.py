# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from fastapi.responses import UJSONResponse
from pydantic import BaseModel, Field

from ...__types import DictData
from ...exceptions import JobException
from ...job import Job
from ...logs import get_logger
from ...result import Result

logger = get_logger("uvicorn.error")
job_route = APIRouter(prefix="/job", tags=["job"])


class ResultCreate(BaseModel):
    """Create Result model for receive running IDs to create the Result
    dataclass.
    """

    run_id: str = Field(description="A running ID.")
    parent_run_id: Optional[str] = Field(
        default=None, description="A parent running ID."
    )


@job_route.post(path="/execute/", response_class=UJSONResponse)
async def job_execute(
    result: ResultCreate,
    job: Job,
    params: dict[str, Any],
    extras: Optional[dict[str, Any]] = None,
):
    """Execute job via RestAPI with execute route path."""
    rs: Result = Result(
        run_id=result.run_id,
        parent_run_id=result.parent_run_id,
        extras=extras or {},
    )

    if extras:
        job.extras = extras

    context: DictData = {}
    try:
        job.set_outputs(
            job.execute(
                params=params,
                run_id=rs.run_id,
                parent_run_id=rs.parent_run_id,
            ).context,
            to=context,
        )
    except JobException as err:
        rs.trace.error(f"[JOB]: {err.__class__.__name__}: {err}")

    return {
        "message": "Execute job via RestAPI.",
        "result": {"run_id": rs.run_id, "parent_run_id": rs.parent_run_id},
        "job": job.model_dump(
            by_alias=True,
            exclude_none=False,
            exclude_unset=True,
        ),
        "params": params,
        "context": context,
    }
