# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import asyncio
import contextlib
import os
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from queue import Empty, Queue
from typing import TypedDict
from zoneinfo import ZoneInfo

from ddeutil.core import str2bool
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import UJSONResponse
from pydantic import BaseModel

from .__about__ import __version__
from .log import get_logger
from .repeat import repeat_every

load_dotenv()
logger = get_logger("ddeutil.workflow")


class State(TypedDict):
    upper_queue: Queue
    upper_result: dict[str, str]
    scheduler: dict
    scheduler_threads: dict


@contextlib.asynccontextmanager
async def lifespan(a: FastAPI) -> AsyncIterator[State]:
    a.state.upper_queue = Queue()
    a.state.upper_result = {}
    a.state.scheduler = {}
    a.state.scheduler_threads = {}

    await asyncio.create_task(broker_upper_messages())

    yield {
        "upper_queue": a.state.upper_queue,
        "upper_result": a.state.upper_result,
        # NOTE: Scheduler value should be contain a key of pipeline workflow and
        #   list of datetime of queue and running.
        #
        #   ... {
        #   ...     '<pipeline-name>': (
        #   ...         [<running-datetime>, ...], [<queue-datetime>, ...]
        #   ...     )
        #   ... }
        #
        "scheduler": a.state.scheduler,
        "scheduler_threads": a.state.scheduler_threads,
    }


app = FastAPI(
    titile="Workflow API",
    description=(
        "This is workflow FastAPI web application that use to manage manual "
        "execute or schedule workflow via RestAPI."
    ),
    version=__version__,
    lifespan=lifespan,
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


@app.get("/", response_class=UJSONResponse)
async def health():
    return {"message": "Workflow API already start up"}


@app.post("/", response_class=UJSONResponse)
async def message_upper(payload: Payload):
    """Convert message from any case to the upper case."""
    request_id: str = str(uuid.uuid4())
    app.state.upper_queue.put(
        {"text": payload.text, "request_id": request_id},
    )
    return await get_result(request_id)


if str2bool(os.getenv("WORKFLOW_API_ENABLE_ROUTE_WORKFLOW", "true")):
    from .route import workflow

    app.include_router(workflow)

if str2bool(os.getenv("WORKFLOW_API_ENABLE_ROUTE_SCHEDULE", "true")):
    from .route import schedule
    from .scheduler import PipelineTask, Schedule, workflow_task

    app.include_router(schedule)

    @schedule.on_event("startup")
    @repeat_every(seconds=60)
    def schedule_broker_up():
        logger.info(
            f"[SCHEDULER]: Start listening schedule from queue "
            f"{app.state.scheduler}"
        )
        tz: ZoneInfo = ZoneInfo(os.getenv("WORKFLOW_CORE_TIMEZONE", "UTC"))
        start_date: datetime = datetime.now(tz=tz)
        start_date_waiting: datetime = (
            start_date + timedelta(minutes=1)
        ).replace(second=0, microsecond=0)

        # NOTE: Create pair of pipeline and on from schedule model.
        pipeline_tasks: list[PipelineTask] = []
        for name in app.state.scheduler:

            sch = Schedule.from_loader(name)
            pipeline_tasks.extend(
                sch.tasks(start_date_waiting, **app.state.scheduler[name])
            )

        if pipeline_tasks:
            workflow_task(
                pipeline_tasks,
                start_date_waiting + timedelta(minutes=1),
                app.state.scheduler_threads,
            )
