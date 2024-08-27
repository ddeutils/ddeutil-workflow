# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import copy
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi import status as st
from fastapi.responses import UJSONResponse

from .__types import DictData
from .log import get_logger
from .pipeline import Pipeline
from .utils import Loader

logger = get_logger("ddeutil.workflow")
workflow = APIRouter(
    prefix="/workflow",
    tags=["workflow"],
)
schedule = APIRouter(
    prefix="/schedule",
    tags=["schedule"],
)

ListDate = list[datetime]
SchedulerValueT = tuple[ListDate, ListDate]


@workflow.get(
    "/",
    response_class=UJSONResponse,
    status_code=st.HTTP_200_OK,
)
async def get_workflows():
    """Return all pipeline workflows that exists in config path."""
    pipelines: DictData = Loader.finds(Pipeline)
    return {
        "message": f"getting all pipelines: {pipelines}",
    }


@workflow.get(
    "/{name}",
    response_class=UJSONResponse,
    status_code=st.HTTP_200_OK,
)
async def get_workflow(name: str) -> DictData:
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
    return pipeline.model_dump(
        by_alias=True,
        exclude_none=True,
        exclude_unset=True,
        exclude_defaults=True,
    )


@workflow.get("/{name}/logs")
async def get_workflow_logs(name: str):
    return {"message": f"getting pipeline {name!r} logs"}


@workflow.get("/{name}/logs/{release}")
async def get_workflow_release_log(name: str, release: str):
    return {"message": f"getting pipeline {name!r} log in release {release}"}


@workflow.delete(
    "/{name}/logs/{release}",
    status_code=st.HTTP_204_NO_CONTENT,
)
async def del_workflow_release_log(name: str, release: str):
    return {"message": f"deleted pipeline {name!r} log in release {release}"}


@schedule.get("/", response_class=UJSONResponse)
async def get_schedulers(request: Request):
    snapshot = copy.deepcopy(request.state.scheduler)
    return snapshot


@schedule.get("/{name}", response_class=UJSONResponse)
async def get_scheduler(request: Request, name: str):
    if name in request.state.scheduler:
        return {
            "message": f"getting {name!r} to schedule listener.",
            "scheduler": request.state.scheduler.get(name),
        }
    raise HTTPException(
        status_code=st.HTTP_404_NOT_FOUND,
        detail=f"Does not found {name!r} in schedule listener",
    )


@schedule.post("/{name}", response_class=UJSONResponse)
async def add_scheduler(request: Request, name: str):
    """Adding schedule name to application state store."""
    wf_queue: ListDate = []
    wf_running: ListDate = []
    request.state.scheduler[name]: SchedulerValueT = (wf_queue, wf_running)
    return {"message": f"adding {name!r} to schedule listener."}


@schedule.delete("/{name}", response_class=UJSONResponse)
async def del_scheduler(request: Request, name: str):
    if name in request.state.scheduler:
        request.state.scheduler.pop(name)
        return {"message": f"deleted {name!r} to schedule listener."}
    raise HTTPException(
        status_code=st.HTTP_404_NOT_FOUND,
        detail=f"Does not found {name!r} in schedule listener",
    )
