# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import copy
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi import status as st
from fastapi.responses import UJSONResponse
from pydantic import BaseModel

from . import Workflow
from .__types import DictData
from .conf import Loader, config, get_logger
from .scheduler import Schedule
from .utils import Result

logger = get_logger("ddeutil.workflow")
workflow = APIRouter(
    prefix="/api/workflow",
    tags=["workflow"],
    default_response_class=UJSONResponse,
)
schedule = APIRouter(
    prefix="/api/schedule",
    tags=["schedule"],
    default_response_class=UJSONResponse,
)

ListDate = list[datetime]


@workflow.get("/")
async def get_workflows():
    """Return all workflow workflows that exists in config path."""
    workflows: DictData = Loader.finds(Workflow)
    return {
        "message": f"getting all workflows: {workflows}",
    }


@workflow.get("/{name}")
async def get_workflow(name: str) -> DictData:
    """Return model of workflow that passing an input workflow name."""
    try:
        wf: Workflow = Workflow.from_loader(name=name, externals={})
    except ValueError as err:
        logger.exception(err)
        raise HTTPException(
            status_code=st.HTTP_404_NOT_FOUND,
            detail=(
                f"Workflow workflow name: {name!r} does not found in /conf path"
            ),
        ) from None
    return wf.model_dump(
        by_alias=True,
        exclude_none=True,
        exclude_unset=True,
        exclude_defaults=True,
    )


class ExecutePayload(BaseModel):
    params: dict[str, Any]


@workflow.post("/{name}/execute", status_code=st.HTTP_202_ACCEPTED)
async def execute_workflow(name: str, payload: ExecutePayload) -> DictData:
    """Return model of workflow that passing an input workflow name."""
    try:
        wf: Workflow = Workflow.from_loader(name=name, externals={})
    except ValueError:
        raise HTTPException(
            status_code=st.HTTP_404_NOT_FOUND,
            detail=(
                f"Workflow workflow name: {name!r} does not found in /conf path"
            ),
        ) from None

    # NOTE: Start execute manually
    rs: Result = wf.execute(params=payload.params)

    return dict(rs)


@workflow.get("/{name}/logs")
async def get_workflow_logs(name: str):
    return {"message": f"getting workflow {name!r} logs"}


@workflow.get("/{name}/logs/{release}")
async def get_workflow_release_log(name: str, release: str):
    return {"message": f"getting workflow {name!r} log in release {release}"}


@workflow.delete("/{name}/logs/{release}", status_code=st.HTTP_204_NO_CONTENT)
async def del_workflow_release_log(name: str, release: str):
    return {"message": f"deleted workflow {name!r} log in release {release}"}


@schedule.get("/{name}")
async def get_schedule(name: str):
    try:
        sch: Schedule = Schedule.from_loader(name=name, externals={})
    except ValueError:
        raise HTTPException(
            status_code=st.HTTP_404_NOT_FOUND,
            detail=f"Schedule name: {name!r} does not found in /conf path",
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
        for wf in sch.workflows:
            getter.append(
                {
                    wf.name: {
                        "queue": copy.deepcopy(
                            request.state.workflow_queue[wf.name]
                        ),
                        "running": copy.deepcopy(
                            request.state.workflow_running[wf.name]
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

    start_date: datetime = datetime.now(tz=config.tz)
    start_date_waiting: datetime = (start_date + timedelta(minutes=1)).replace(
        second=0, microsecond=0
    )

    # NOTE: Create pair of workflow and on from schedule model.
    try:
        sch = Schedule.from_loader(name)
    except ValueError as e:
        request.state.scheduler.remove(name)
        logger.exception(e)
        raise HTTPException(
            status_code=st.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from None
    request.state.workflow_tasks.extend(
        sch.tasks(
            start_date_waiting,
            queue=request.state.workflow_queue,
            running=request.state.workflow_running,
        ),
    )
    return {"message": f"adding {name!r} to schedule listener."}


@schedule.delete("/deploy/{name}")
async def del_deploy_scheduler(request: Request, name: str):
    if name in request.state.scheduler:
        request.state.scheduler.remove(name)
        sche = Schedule.from_loader(name)
        for workflow_task in sche.tasks(datetime.now(), {}, {}):
            request.state.workflow_tasks.remove(workflow_task)

        for wf in sche.workflows:
            if wf in request.state.workflow_queue:
                request.state.workflow_queue.pop(wf, {})

            if wf in request.state.workflow_running:
                request.state.workflow_running.pop(wf, {})

        return {"message": f"deleted {name!r} to schedule listener."}

    raise HTTPException(
        status_code=st.HTTP_404_NOT_FOUND,
        detail=f"Does not found {name!r} in schedule listener",
    )
