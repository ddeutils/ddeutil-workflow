# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import copy
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi import status as st
from fastapi.responses import UJSONResponse
from pydantic import BaseModel

from ..__types import DictData
from ..conf import Loader, config, get_logger
from ..logs import Log, get_log
from ..result import Result
from ..scheduler import Schedule
from ..workflow import Workflow

logger = get_logger("ddeutil.workflow")

workflow_route = APIRouter(
    prefix="/workflows",
    tags=["workflows"],
    default_response_class=UJSONResponse,
)

schedule_route = APIRouter(
    prefix="/schedules",
    tags=["schedules"],
    default_response_class=UJSONResponse,
)


@workflow_route.get(path="/")
async def get_workflows() -> DictData:
    """Return all workflow workflows that exists in config path."""
    workflows: DictData = dict(Loader.finds(Workflow))
    return {
        "message": f"Getting all workflows: {len(workflows)}",
        "count": len(workflows),
        "workflows": workflows,
    }


@workflow_route.get(path="/{name}")
async def get_workflow_by_name(name: str) -> DictData:
    """Return model of workflow that passing an input workflow name."""
    try:
        workflow: Workflow = Workflow.from_loader(name=name, externals={})
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
        exclude_none=True,
        exclude_unset=True,
        exclude_defaults=True,
    )


class ExecutePayload(BaseModel):
    params: dict[str, Any]


@workflow_route.post(path="/{name}/execute", status_code=st.HTTP_202_ACCEPTED)
async def execute_workflow(name: str, payload: ExecutePayload) -> DictData:
    """Return model of workflow that passing an input workflow name."""
    try:
        workflow: Workflow = Workflow.from_loader(name=name, externals={})
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


@workflow_route.get(path="/{name}/logs")
async def get_workflow_logs(name: str):
    try:
        return {
            "message": f"Getting workflow {name!r} logs",
            "logs": [
                log.model_dump(
                    by_alias=True,
                    exclude_none=True,
                    exclude_unset=True,
                    exclude_defaults=True,
                )
                for log in get_log().find_logs(name=name)
            ],
        }
    except FileNotFoundError:
        raise HTTPException(
            status_code=st.HTTP_404_NOT_FOUND,
            detail=f"Does not found log for workflow {name!r}",
        ) from None


@workflow_route.get(path="/{name}/logs/{release}")
async def get_workflow_release_log(name: str, release: str):
    try:
        log: Log = get_log().find_log_with_release(
            name=name, release=datetime.strptime(release, "%Y%m%d%H%M%S")
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=st.HTTP_404_NOT_FOUND,
            detail=(
                f"Does not found log for workflow {name!r} "
                f"with release {release!r}"
            ),
        ) from None
    return {
        "message": f"Getting workflow {name!r} log in release {release}",
        "log": log.model_dump(
            by_alias=True,
            exclude_none=True,
            exclude_unset=True,
            exclude_defaults=True,
        ),
    }


@workflow_route.delete(
    path="/{name}/logs/{release}",
    status_code=st.HTTP_204_NO_CONTENT,
)
async def del_workflow_release_log(name: str, release: str):
    return {"message": f"Deleted workflow {name!r} log in release {release}"}


@schedule_route.get(path="/{name}")
async def get_schedules(name: str):
    try:
        schedule: Schedule = Schedule.from_loader(name=name, externals={})
    except ValueError:
        raise HTTPException(
            status_code=st.HTTP_404_NOT_FOUND,
            detail=f"Schedule name: {name!r} does not found in /conf path",
        ) from None
    return schedule.model_dump(
        by_alias=True,
        exclude_none=True,
        exclude_unset=True,
        exclude_defaults=True,
    )


@schedule_route.get(path="/deploy/")
async def get_deploy_schedulers(request: Request):
    snapshot = copy.deepcopy(request.state.scheduler)
    return {"schedule": snapshot}


@schedule_route.get(path="/deploy/{name}")
async def get_deploy_scheduler(request: Request, name: str):
    if name in request.state.scheduler:
        schedule = Schedule.from_loader(name)
        getter: list[dict[str, dict[str, list[datetime]]]] = []
        for workflow in schedule.workflows:
            getter.append(
                {
                    workflow.name: {
                        "queue": copy.deepcopy(
                            request.state.workflow_queue[workflow.name]
                        ),
                        "running": copy.deepcopy(
                            request.state.workflow_running[workflow.name]
                        ),
                    }
                }
            )
        return {
            "message": f"Getting {name!r} to schedule listener.",
            "scheduler": getter,
        }
    raise HTTPException(
        status_code=st.HTTP_404_NOT_FOUND,
        detail=f"Does not found {name!r} in schedule listener",
    )


@schedule_route.post(path="/deploy/{name}")
async def add_deploy_scheduler(request: Request, name: str):
    """Adding schedule name to application state store."""
    if name in request.state.scheduler:
        raise HTTPException(
            status_code=st.HTTP_302_FOUND,
            detail=f"This schedule {name!r} already exists in scheduler list.",
        )

    request.state.scheduler.append(name)

    start_date: datetime = datetime.now(tz=config.tz)
    start_date_waiting: datetime = (start_date + timedelta(minutes=1)).replace(
        second=0, microsecond=0
    )

    # NOTE: Create a pair of workflow and on from schedule model.
    try:
        schedule: Schedule = Schedule.from_loader(name)
    except ValueError as err:
        request.state.scheduler.remove(name)
        logger.exception(err)
        raise HTTPException(
            status_code=st.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from None

    request.state.workflow_tasks.extend(
        schedule.tasks(
            start_date_waiting,
            queue=request.state.workflow_queue,
            externals={},
        ),
    )
    return {
        "message": f"Adding {name!r} to schedule listener.",
        "start_date": start_date_waiting,
    }


@schedule_route.delete(path="/deploy/{name}")
async def del_deploy_scheduler(request: Request, name: str):
    """Delete workflow task on the schedule listener."""
    if name in request.state.scheduler:

        # NOTE: Remove current schedule name from the state.
        request.state.scheduler.remove(name)

        schedule: Schedule = Schedule.from_loader(name)

        for task in schedule.tasks(datetime.now(tz=config.tz), queue={}):
            if task in request.state.workflow_tasks:
                request.state.workflow_tasks.remove(task)

        for workflow in schedule.workflows:
            if workflow.alias in request.state.workflow_queue:
                request.state.workflow_queue.pop(workflow.alias)

        return {"message": f"Deleted schedule {name!r} in listener."}

    raise HTTPException(
        status_code=st.HTTP_404_NOT_FOUND,
        detail=f"Does not found schedule {name!r} in listener",
    )
