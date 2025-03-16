# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter
from fastapi.responses import UJSONResponse
from pydantic import BaseModel, Field

from ...__types import DictData
from ...conf import get_logger
from ...exceptions import JobException
from ...job import Job
from ...result import Result, Status

logger = get_logger("ddeutil.workflow")


job_route = APIRouter(
    prefix="/job",
    tags=["job"],
    default_response_class=UJSONResponse,
)


class ResultPost(BaseModel):
    status: Status
    context: DictData
    run_id: Optional[str]
    parent_run_id: Optional[str]
    ts: datetime = Field(exclude=True)


@job_route.post(path="/execute/")
async def job_execute(
    result_schema: ResultPost,
    job: Job,
    params: dict[str, Any],
):
    """Execute job via API."""
    result: Result = Result(
        status=result_schema.status,
        context=result_schema.context,
        run_id=result_schema.run_id,
        parent_run_id=result_schema.parent_run_id,
        ts=result_schema.ts,
    )
    try:
        job.set_outputs(
            job.execute(
                params=params,
                run_id=result.run_id,
                parent_run_id=result.parent_run_id,
            ).context,
            to=params,
        )
    except JobException as err:
        result.trace.error(f"[WORKFLOW]: {err.__class__.__name__}: {err}")

    return {
        "message": "Start execute job via API.",
        "result": result,
        "job": job,
        "params": params,
    }
