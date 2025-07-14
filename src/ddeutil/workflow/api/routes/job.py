# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Body
from fastapi import status as st
from fastapi.responses import UJSONResponse

from ...__types import DictData
from ...errors import JobError
from ...job import Job
from ...traces import TraceManager, get_trace
from ...utils import gen_id

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/job", tags=["job"])


@router.post(
    path="/execute/",
    response_class=UJSONResponse,
    status_code=st.HTTP_200_OK,
)
async def job_execute(
    job: Job,
    params: dict[str, Any],
    run_id: str = Body(...),
    extras: Optional[dict[str, Any]] = Body(default=None),
) -> UJSONResponse:
    """Execute job via RestAPI with execute route path."""
    logger.info("[API]: Start execute job ...")
    parent_run_id: str = run_id
    run_id = gen_id(job.id, unique=True)

    if extras:
        job.extras = extras

    trace: TraceManager = get_trace(
        run_id, parent_run_id=parent_run_id, extras=job.extras
    )

    context: DictData = {}
    try:
        job.set_outputs(
            job.execute(
                params=params,
                run_id=parent_run_id,
            ).context,
            to=context,
        )
    except JobError as err:
        trace.error(f"[JOB]: {err.__class__.__name__}: {err}")
        return UJSONResponse(
            content={
                "message": str(err),
                "run_id": parent_run_id,
                "job": job.model_dump(
                    by_alias=True,
                    exclude_none=False,
                    exclude_unset=True,
                ),
                "params": params,
                "context": context,
            },
            status_code=st.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return UJSONResponse(
        content={
            "message": "Execute job via RestAPI successful.",
            "run_id": parent_run_id,
            "job": job.model_dump(
                by_alias=True,
                exclude_none=False,
                exclude_unset=True,
            ),
            "params": params,
            "context": context,
        },
        status_code=st.HTTP_200_OK,
    )
