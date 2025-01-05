# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from queue import Empty, Queue
from typing import TypedDict

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import UJSONResponse
from pydantic import BaseModel

from ..__about__ import __version__
from ..conf import config, get_logger
from ..scheduler import ReleaseThread, ReleaseThreads
from ..workflow import WorkflowQueue, WorkflowTask
from .repeat import repeat_at, repeat_every

load_dotenv()
logger = get_logger("ddeutil.workflow")


class State(TypedDict):
    """TypeDict for State of FastAPI application."""

    # NOTE: For upper queue route.
    upper_queue: Queue
    upper_result: dict[str, str]

    # NOTE: For schedule listener.
    scheduler: list[str]
    workflow_threads: ReleaseThreads
    workflow_tasks: list[WorkflowTask]
    workflow_queue: dict[str, WorkflowQueue]


@contextlib.asynccontextmanager
async def lifespan(a: FastAPI) -> AsyncIterator[State]:
    """Lifespan function for the FastAPI application."""
    a.state.upper_queue = Queue()
    a.state.upper_result = {}
    a.state.scheduler = []
    a.state.workflow_threads = {}
    a.state.workflow_tasks = []
    a.state.workflow_queue = {}

    await asyncio.create_task(broker_upper_messages())

    yield {
        "upper_queue": a.state.upper_queue,
        "upper_result": a.state.upper_result,
        # NOTE: Scheduler value should be contain a key of workflow workflow and
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


@repeat_every(seconds=10)
async def broker_upper_messages():
    """Broker for receive message from the `/upper` path and change it to upper
    case. This broker use interval running in background every 10 seconds.
    """
    for _ in range(10):
        try:
            obj = app.state.upper_queue.get_nowait()
            app.state.upper_result[obj["request_id"]] = obj["text"].upper()
            logger.info(f"Upper message: {app.state.upper_result}")
        except Empty:
            pass
    await asyncio.sleep(0.0001)


class Payload(BaseModel):
    text: str


async def get_result(request_id: str) -> dict[str, str]:
    """Get data from output dict that global."""
    while True:
        if request_id in app.state.upper_result:
            result: str = app.state.upper_result[request_id]
            del app.state.upper_result[request_id]
            return {"message": result}
        await asyncio.sleep(0.0025)


@app.get("/")
async def health():
    return {"message": "Workflow API already start up"}


@app.post(f"{config.prefix_path}/upper")
async def message_upper(payload: Payload):
    """Convert message from any case to the upper case."""
    request_id: str = str(uuid.uuid4())
    app.state.upper_queue.put(
        {"text": payload.text, "request_id": request_id},
    )
    return await get_result(request_id)


# NOTE: Enable the workflow route.
if config.enable_route_workflow:
    from .route import workflow_route

    app.include_router(workflow_route, prefix=config.prefix_path)


# NOTE: Enable the schedule route.
if config.enable_route_schedule:
    from ..conf import FileLog
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
                log=FileLog,
            )

    @schedule_route.on_event("startup")
    @repeat_at(cron="*/5 * * * *")
    def monitoring():
        logger.debug("[MONITOR]: Start monitoring threading.")
        snapshot_threads: list[str] = list(app.state.workflow_threads.keys())
        for t_name in snapshot_threads:

            thread_release: ReleaseThread = app.state.workflow_threads[t_name]

            # NOTE: remove the thread that running success.
            if not thread_release["thread"].is_alive():
                app.state.workflow_threads.pop(t_name)
