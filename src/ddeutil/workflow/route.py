# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi import status as st
from fastapi.responses import UJSONResponse

from .__types import DictData
from .log import get_logger
from .pipeline import Pipeline
from .repeat import repeat_every
from .utils import Loader

logger = get_logger("ddeutil.workflow")
workflow = APIRouter(prefix="/workflow", tags=["workflow"])
schedule = APIRouter(prefix="/schedule", tags=["schedule"])


@workflow.get(
    "/",
    response_class=UJSONResponse,
)
async def get_workflows():
    pipelines: DictData = Loader.find(Pipeline)
    return {
        "message": f"getting all pipelines: {pipelines}",
    }


@workflow.get(
    "/{name}",
    response_class=UJSONResponse,
    status_code=st.HTTP_200_OK,
)
async def get_workflow(name: str):
    """Return model of pipeline that passing an input pipeline name."""
    try:
        pipeline: Pipeline = Pipeline.from_loader(name=name, externals={})
    except ValueError:
        raise HTTPException(
            status_code=st.HTTP_404_NOT_FOUND,
            detail=(
                f"Workflow pipeline name: {name!r} does not found in /conf path"
            ),
        ) from None
    return pipeline.model_dump(exclude=["on"])


@workflow.get("/{name}/logs")
async def get_workflow_logs(name: str):
    return {"message": f"getting pipeline {name} logs"}


@workflow.get("/{name}/logs/{release}")
async def get_workflow_release_log(name: str, release: str):
    return {"message": f"getting pipeline {name} log in release {release}"}


@workflow.delete(
    "/{name}/logs/{release}",
    status_code=st.HTTP_204_NO_CONTENT,
)
async def del_workflow_release_log(name: str, release: str):
    return {"message": f"getting pipeline {name} log in release {release}"}


@schedule.on_event("startup")
@repeat_every(seconds=60)
def schedule_broker_up(): ...


@schedule.get("/", response_class=UJSONResponse)
async def get_jobs(request: Request):
    jobs = request.app.scheduler.get_jobs()
    jobs = [
        {k: v for k, v in job.__getstate__().items() if k != "trigger"}
        for job in jobs
    ]
    return jobs
