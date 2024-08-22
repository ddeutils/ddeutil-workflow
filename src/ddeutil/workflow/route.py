from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi import status as st

logger = logging.getLogger(__name__)
workflow = APIRouter(prefix="/wf", tags=["workflow"])


@workflow.get("/")
async def get_workflows():
    return {"message": "getting all pipelines: []"}


@workflow.get("/{name}")
async def get_workflow(name: str):
    return {"message": f"getting pipeline {name}"}


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


class JobNotFoundError(Exception):
    pass


schedule = APIRouter(prefix="/schedule", tags=["schedule"])


@schedule.post("/", name="scheduler:add_job", status_code=st.HTTP_201_CREATED)
async def add_job(request: Request):
    return {"job": f"{request}"}


@schedule.get("/", name="scheduler:get_jobs", response_model=list)
async def get_jobs(request: Request):
    jobs = request.app.scheduler.get_jobs()
    jobs = [
        {k: v for k, v in job.__getstate__().items() if k != "trigger"}
        for job in jobs
    ]
    return jobs


@schedule.delete("/{job_id}", name="scheduler:remove_job")
async def remove_job(request: Request, job_id: str):
    try:
        deleted = request.app.scheduler.remove_job(job_id=job_id)
        logger.debug(f"Job {job_id} deleted: {deleted}")
        return {"job": f"{job_id}"}
    except AttributeError as err:
        raise JobNotFoundError(
            f"No job by the id of {job_id} was found"
        ) from err
