# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from typing import TypedDict

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi import status as st
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import UJSONResponse

from ..__about__ import __version__
from ..conf import config, get_logger
from ..scheduler import ReleaseThread, ReleaseThreads
from ..workflow import ReleaseQueue, WorkflowTask
from .repeat import repeat_at
from .routes import job, log

load_dotenv()
logger = get_logger("ddeutil.workflow")


class State(TypedDict):
    """TypeDict for State of FastAPI application."""

    scheduler: list[str]
    workflow_threads: ReleaseThreads
    workflow_tasks: list[WorkflowTask]
    workflow_queue: dict[str, ReleaseQueue]


@contextlib.asynccontextmanager
async def lifespan(a: FastAPI) -> AsyncIterator[State]:
    """Lifespan function for the FastAPI application."""
    a.state.scheduler = []
    a.state.workflow_threads = {}
    a.state.workflow_tasks = []
    a.state.workflow_queue = {}

    yield {
        # NOTE: Scheduler value should be contained a key of workflow and
        #   list of datetime of queue and running.
        #
        #   ... {
        #   ...     '<workflow-name>': (
        #   ...         [<running-datetime>, ...], [<queue-datetime>, ...]
        #   ...     )
        #   ... }
        #
        "scheduler": a.state.scheduler,
        "workflow_queue": a.state.workflow_queue,
        "workflow_threads": a.state.workflow_threads,
        "workflow_tasks": a.state.workflow_tasks,
    }


app = FastAPI(
    titile="Workflow",
    description=(
        "This is a workflow FastAPI application that use to manage manual "
        "execute, logging, and schedule workflow via RestAPI."
    ),
    version=__version__,
    lifespan=lifespan,
    default_response_class=UJSONResponse,
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
origins: list[str] = [
    "http://localhost",
    "http://localhost:88",
    "http://localhost:80",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def health():
    """Index view that not return any template without json status."""
    return {"message": "Workflow already start up with healthy status."}


# NOTE Add the jobs and logs routes by default.
app.include_router(job, prefix=config.prefix_path)
app.include_router(log, prefix=config.prefix_path)


# NOTE: Enable the workflows route.
if config.enable_route_workflow:
    from .routes import workflow

    app.include_router(workflow, prefix=config.prefix_path)


# NOTE: Enable the schedules route.
if config.enable_route_schedule:
    from ..audit import get_audit
    from ..scheduler import schedule_task
    from .routes import schedule

    app.include_router(schedule, prefix=config.prefix_path)

    @schedule.on_event("startup")
    @repeat_at(cron="* * * * *", delay=2)
    def scheduler_listener():
        """Schedule broker every minute at 02 second."""
        logger.debug(
            f"[SCHEDULER]: Start listening schedule from queue "
            f"{app.state.scheduler}"
        )
        if app.state.workflow_tasks:
            schedule_task(
                app.state.workflow_tasks,
                stop=datetime.now(config.tz) + timedelta(minutes=1),
                queue=app.state.workflow_queue,
                threads=app.state.workflow_threads,
                audit=get_audit(),
            )

    @schedule.on_event("startup")
    @repeat_at(cron="*/5 * * * *", delay=10)
    def monitoring():
        """Monitoring workflow thread that running in the background."""
        logger.debug("[MONITOR]: Start monitoring threading.")
        snapshot_threads: list[str] = list(app.state.workflow_threads.keys())
        for t_name in snapshot_threads:

            thread_release: ReleaseThread = app.state.workflow_threads[t_name]

            # NOTE: remove the thread that running success.
            if not thread_release["thread"].is_alive():
                app.state.workflow_threads.pop(t_name)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    return UJSONResponse(
        status_code=st.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"detail": exc.errors(), "body": exc.body}),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=80,
    )
