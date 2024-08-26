# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import asyncio
import os
import uuid
from queue import Empty, Queue

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


app = FastAPI(
    titile="Workflow API",
    description=(
        "This is workflow FastAPI web application that use to manage manual "
        "execute or schedule workflow via RestAPI."
    ),
    version=__version__,
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.queue = Queue()
app.upper_result = {}
app.scheduler = {}


@app.on_event("startup")
@repeat_every(seconds=10)
def broker_upper_messages():
    """Broker for receive message from the `/upper` path and change it to upper
    case. This broker use interval running in background every 10 seconds.
    """
    for _ in range(10):
        try:
            obj = app.queue.get_nowait()
            app.upper_result[obj["request_id"]] = obj["text"].upper()
            logger.info(f"Upper message: {app.upper_result}")
        except Empty:
            pass


class Payload(BaseModel):
    text: str


async def get_result(request_id: str) -> dict[str, str]:
    """Get data from output dict that global."""
    while True:
        if request_id in app.upper_result:
            result: str = app.upper_result[request_id]
            del app.upper_result[request_id]
            return {"message": result}
        await asyncio.sleep(0.0025)


@app.get("/", response_class=UJSONResponse)
async def health():
    return {"message": "Workflow API already start up"}


@app.post("/", response_class=UJSONResponse)
async def message_upper(payload: Payload):
    """Convert message from any case to the upper case."""
    request_id: str = str(uuid.uuid4())
    app.queue.put(
        {"text": payload.text, "request_id": request_id},
    )
    return await get_result(request_id)


if str2bool(os.getenv("WORKFLOW_API_ENABLE_ROUTE_WORKFLOW", "true")):
    from .route import workflow

    app.include_router(workflow)

if str2bool(os.getenv("WORKFLOW_API_ENABLE_ROUTE_SCHEDULE", "true")):
    from .route import schedule

    app.include_router(schedule)

    @schedule.on_event("startup")
    @repeat_every(seconds=60)
    def schedule_broker_up():
        logger.info(f"Start listening schedule from queue {app.scheduler}")
