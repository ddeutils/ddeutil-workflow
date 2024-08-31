# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import copy
import os
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from fastapi import status as st
from fastapi.responses import UJSONResponse
from pydantic import BaseModel

from .__types import DictData
from .log import get_logger
from .pipeline import Pipeline
from .scheduler import Schedule
from .utils import Loader, Result

logger = get_logger("ddeutil.workflow")
workflow = APIRouter(
    prefix="/workflow",
    tags=["workflow"],
    default_response_class=UJSONResponse,
)
schedule = APIRouter(
    prefix="/schedule",
    tags=["schedule"],
    default_response_class=UJSONResponse,
)

ListDate = list[datetime]


@workflow.get("/")
async def get_workflows():
    """Return all pipeline workflows that exists in config path."""
    pipelines: DictData = Loader.finds(Pipeline)
    return {
        "message": f"getting all pipelines: {pipelines}",
    }


@workflow.get("/{name}")
async def get_workflow(name: str) -> DictData:
    """Return model of pipeline that passing an input pipeline name."""
    try:
        pipeline: Pipeline = Pipeline.from_loader(name=name, externals={})
    except ValueError as err:
        logger.exception(err)
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


class ExecutePayload(BaseModel):
    params: dict[str, Any]


@workflow.post("/{name}/execute", status_code=st.HTTP_202_ACCEPTED)
async def execute_workflow(name: str, payload: ExecutePayload) -> DictData:
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

    # NOTE: Start execute manually
    rs: Result = pipeline.execute(params=payload.params)

    return rs.model_dump(
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


@workflow.delete("/{name}/logs/{release}", status_code=st.HTTP_204_NO_CONTENT)
async def del_workflow_release_log(name: str, release: str):
    return {"message": f"deleted pipeline {name!r} log in release {release}"}


@schedule.get("/{name}")
async def get_schedule(name: str):
    try:
        sch: Schedule = Schedule.from_loader(name=name, externals={})
    except ValueError:
        raise HTTPException(
            status_code=st.HTTP_404_NOT_FOUND,
            detail=(f"Schedule name: {name!r} does not found in /conf path"),
        ) from None
    return sch.model_dump(
        by_alias=True,
        exclude_none=True,
        exclude_unset=True,
        exclude_defaults=True,
    )


@schedule.get("/deploy")
async def get_deploy_schedulers(request: Request):
    snapshot = copy.deepcopy(request.state.scheduler)
    return {"schedule": snapshot}


@schedule.get("/deploy/{name}")
async def get_deploy_scheduler(request: Request, name: str):
    if name in request.state.scheduler:
        sch = Schedule.from_loader(name)
        getter: list[dict[str, dict[str, list[datetime]]]] = []
        for pipe in sch.pipelines:
            getter.append(
                {
                    pipe.name: {
                        "queue": copy.deepcopy(
                            request.state.pipeline_queue[pipe.name]
                        ),
                        "running": copy.deepcopy(
                            request.state.pipeline_running[pipe.name]
                        ),
                    }
                }
            )
        return {
            "message": f"getting {name!r} to schedule listener.",
            "scheduler": getter,
        }
    raise HTTPException(
        status_code=st.HTTP_404_NOT_FOUND,
        detail=f"Does not found {name!r} in schedule listener",
    )


@schedule.post("/deploy/{name}")
async def add_deploy_scheduler(request: Request, name: str):
    """Adding schedule name to application state store."""
    if name in request.state.scheduler:
        raise HTTPException(
            status_code=st.HTTP_302_FOUND,
            detail="This schedule already exists in scheduler list.",
        )

    request.state.scheduler.append(name)

    tz: ZoneInfo = ZoneInfo(os.getenv("WORKFLOW_CORE_TIMEZONE", "UTC"))
    start_date: datetime = datetime.now(tz=tz)
    start_date_waiting: datetime = (start_date + timedelta(minutes=1)).replace(
        second=0, microsecond=0
    )

    # NOTE: Create pair of pipeline and on from schedule model.
    try:
        sch = Schedule.from_loader(name)
    except ValueError as e:
        request.state.scheduler.remove(name)
        logger.exception(e)
        raise HTTPException(
            status_code=st.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from None
    request.state.pipeline_tasks.extend(
        sch.tasks(
            start_date_waiting,
            queue=request.state.pipeline_queue,
            running=request.state.pipeline_running,
        ),
    )
    return {"message": f"adding {name!r} to schedule listener."}


@schedule.delete("/deploy/{name}")
async def del_deploy_scheduler(request: Request, name: str):
    if name in request.state.scheduler:
        request.state.scheduler.remove(name)
        sche = Schedule.from_loader(name)
        for pipeline_task in sche.tasks(datetime.now(), {}, {}):
            request.state.pipeline_tasks.remove(pipeline_task)

        for pipe in sche.pipelines:
            if pipe in request.state.pipeline_queue:
                request.state.pipeline_queue.pop(pipe, {})

            if pipe in request.state.pipeline_running:
                request.state.pipeline_running.pop(pipe, {})

        return {"message": f"deleted {name!r} to schedule listener."}

    raise HTTPException(
        status_code=st.HTTP_404_NOT_FOUND,
        detail=f"Does not found {name!r} in schedule listener",
    )
