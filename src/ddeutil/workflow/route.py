from enum import Enum

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, ConfigDict, Field

from .log import get_logger

logger = get_logger(__name__)
workflow_route = APIRouter(prefix="/workflow")


@workflow_route.get("/{name}")
async def get_pipeline(name: str):
    return {"message": f"getting pipeline {name}"}


@workflow_route.get("/{name}/logs")
async def get_pipeline_log(name: str):
    return {"message": f"getting pipeline {name} logs"}


class JobNotFoundError(Exception):
    pass


schedule_route = APIRouter(prefix="/schedule", tags=["schedule"])


class TriggerEnum(str, Enum):
    interval = "interval"
    cron = "cron"


class Job(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "func": "example.main:pytest_job",
                "trigger": "interval",
                "seconds": 3,
                "id": "pytest_job",
            },
        },
    )
    func: str = Field()
    trigger: TriggerEnum = Field(title="Trigger type")
    seconds: int = Field(title="Interval in seconds")
    id: str = Field(title="Job ID")


@schedule_route.post(
    "/", name="scheduler:add_job", status_code=status.HTTP_201_CREATED
)
async def add_job(request: Request, job: Job):
    job = request.app.scheduler.add_job(**job.dict())
    return {"job": f"{job.id}"}


@schedule_route.get("/", name="scheduler:get_jobs", response_model=list)
async def get_jobs(request: Request):
    jobs = request.app.scheduler.get_jobs()
    jobs = [
        {k: v for k, v in job.__getstate__().items() if k != "trigger"}
        for job in jobs
    ]
    return jobs


@schedule_route.delete("/{job_id}", name="scheduler:remove_job")
async def remove_job(request: Request, job_id: str):
    try:
        deleted = request.app.scheduler.remove_job(job_id=job_id)
        logger.debug(f"Job {job_id} deleted: {deleted}")
        return {"job": f"{job_id}"}
    except AttributeError as err:
        raise JobNotFoundError(
            f"No job by the id of {job_id} was found"
        ) from err
