# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import copy
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from fastapi import status as st
from fastapi.responses import UJSONResponse

from ...conf import config, get_logger
from ...scheduler import Schedule

logger = get_logger("uvicorn.error")

schedule_route = APIRouter(
    prefix="/schedules",
    tags=["schedules"],
    default_response_class=UJSONResponse,
)


@schedule_route.get(path="/{name}", status_code=st.HTTP_200_OK)
async def get_schedules(name: str):
    """Get schedule object."""
    try:
        schedule: Schedule = Schedule.from_conf(name=name, extras={})
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


@schedule_route.get(path="/deploy/", status_code=st.HTTP_200_OK)
async def get_deploy_schedulers(request: Request):
    snapshot = copy.deepcopy(request.state.scheduler)
    return {"schedule": snapshot}


@schedule_route.get(path="/deploy/{name}", status_code=st.HTTP_200_OK)
async def get_deploy_scheduler(request: Request, name: str):
    if name in request.state.scheduler:
        schedule = Schedule.from_conf(name)
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


@schedule_route.post(path="/deploy/{name}", status_code=st.HTTP_202_ACCEPTED)
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
        schedule: Schedule = Schedule.from_conf(name)
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
            extras={},
        ),
    )
    return {
        "message": f"Adding {name!r} to schedule listener.",
        "start_date": start_date_waiting,
    }


@schedule_route.delete(path="/deploy/{name}", status_code=st.HTTP_202_ACCEPTED)
async def del_deploy_scheduler(request: Request, name: str):
    """Delete workflow task on the schedule listener."""
    if name in request.state.scheduler:

        # NOTE: Remove current schedule name from the state.
        request.state.scheduler.remove(name)

        schedule: Schedule = Schedule.from_conf(name)

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
