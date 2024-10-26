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
from threading import Thread
from typing import TypedDict

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import UJSONResponse
from pydantic import BaseModel

from .__about__ import __version__
from .conf import config, get_logger
from .repeat import repeat_at, repeat_every
from .scheduler import WorkflowTaskData

load_dotenv()
logger = get_logger("ddeutil.workflow")


class State(TypedDict):
    upper_queue: Queue
    upper_result: dict[str, str]
    scheduler: list[str]
    workflow_threads: dict[str, Thread]
    workflow_tasks: list[WorkflowTaskData]
    workflow_queue: dict[str, list[datetime]]
    workflow_running: dict[str, list[datetime]]


@contextlib.asynccontextmanager
async def lifespan(a: FastAPI) -> AsyncIterator[State]:
    a.state.upper_queue = Queue()
    a.state.upper_result = {}
    a.state.scheduler = []
    a.state.workflow_threads = {}
    a.state.workflow_tasks = []
    a.state.workflow_queue = {}
    a.state.workflow_running = {}

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
        "workflow_running": a.state.workflow_running,
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
@app.get("/api")
async def health():
    return {"message": "Workflow API already start up"}


@app.post("/api")
async def message_upper(payload: Payload):
    """Convert message from any case to the upper case."""
    request_id: str = str(uuid.uuid4())
    app.state.upper_queue.put(
        {"text": payload.text, "request_id": request_id},
    )
    return await get_result(request_id)


if config.enable_route_workflow:
    from .route import workflow

    app.include_router(workflow)

if config.enable_route_schedule:
    from .route import schedule
    from .scheduler import workflow_task

    app.include_router(schedule)

    @schedule.on_event("startup")
    @repeat_at(cron="* * * * *", delay=2)
    def schedule_broker_up():
        logger.debug(
            f"[SCHEDULER]: Start listening schedule from queue "
            f"{app.state.scheduler}"
        )
        if app.state.workflow_tasks:
            workflow_task(
                app.state.workflow_tasks,
                stop=datetime.now() + timedelta(minutes=1),
                threads=app.state.workflow_threads,
            )
