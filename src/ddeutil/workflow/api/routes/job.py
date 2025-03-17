# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from fastapi.responses import UJSONResponse
from pydantic import BaseModel

from ...__types import DictData
from ...conf import get_logger
from ...exceptions import JobException
from ...job import Job
from ...result import Result

logger = get_logger("uvicorn.error")


job_route = APIRouter(
    prefix="/job",
    tags=["job"],
    default_response_class=UJSONResponse,
)


class ResultPost(BaseModel):
    context: DictData
    run_id: str
    parent_run_id: Optional[str] = None


@job_route.post(path="/execute/")
async def job_execute(
    result: ResultPost,
    job: Job,
    params: dict[str, Any],
):
    """Execute job via API."""
    rs: Result = Result(
        context=result.context,
        run_id=result.run_id,
        parent_run_id=result.parent_run_id,
    )
    try:
        job.set_outputs(
            job.execute(
                params=params,
                run_id=rs.run_id,
                parent_run_id=rs.parent_run_id,
            ).context,
            to=params,
        )
    except JobException as err:
        rs.trace.error(f"[WORKFLOW]: {err.__class__.__name__}: {err}")

    return {
        "message": "Start execute job via API.",
        "result": {
            "run_id": rs.run_id,
            "parent_run_id": rs.parent_run_id,
        },
        "job": job.model_dump(
            by_alias=True,
            exclude_none=True,
            exclude_unset=True,
            exclude_defaults=True,
        ),
        "params": params,
    }
