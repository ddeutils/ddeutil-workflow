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
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import UJSONResponse

from ..__about__ import __version__
from ..conf import config, get_logger
from ..scheduler import ReleaseThread, ReleaseThreads
from ..workflow import ReleaseQueue, WorkflowTask
from .repeat import repeat_at
from .route import log_route

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
    titile="Workflow API",
    description=(
        "This is workflow FastAPI web application that use to manage manual "
        "execute or schedule workflow via RestAPI."
    ),
    version=__version__,
    lifespan=lifespan,
    default_response_class=UJSONResponse,
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.get("/")
async def health():
    return {"message": "Workflow API already start up"}


# NOTE Add the logs route by default.
app.include_router(log_route, prefix=config.prefix_path)


# NOTE: Enable the workflows route.
if config.enable_route_workflow:
    from .route import workflow_route

    app.include_router(workflow_route, prefix=config.prefix_path)


# NOTE: Enable the schedules route.
if config.enable_route_schedule:
    from ..audit import get_audit
    from ..scheduler import schedule_task
    from .route import schedule_route

    app.include_router(schedule_route, prefix=config.prefix_path)

    @schedule_route.on_event("startup")
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
                log=get_audit(),
            )

    @schedule_route.on_event("startup")
    @repeat_at(cron="*/5 * * * *", delay=10)
    def monitoring():
        logger.debug("[MONITOR]: Start monitoring threading.")
        snapshot_threads: list[str] = list(app.state.workflow_threads.keys())
        for t_name in snapshot_threads:

            thread_release: ReleaseThread = app.state.workflow_threads[t_name]

            # NOTE: remove the thread that running success.
            if not thread_release["thread"].is_alive():
                app.state.workflow_threads.pop(t_name)
