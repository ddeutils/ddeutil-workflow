# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import asyncio
import queue
import time
import uuid
from datetime import datetime

from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import UJSONResponse
from pydantic import BaseModel

from .log import get_logger
from .repeat import repeat_every
from .route import schedule_route, workflow_route

logger = get_logger(__name__)


app = FastAPI()
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.include_router(schedule_route)
app.include_router(workflow_route)
app.queue = queue.Queue()
app.output_dict = {}
app.queue_limit = 2


def write_pipeline(task_id: str, message=""):
    logger.info(f"{task_id} : {message}")
    time.sleep(5)
    logger.info(f"{task_id} : run task successfully!!!")


@app.post("/schedule/{name}", response_class=UJSONResponse)
async def send_schedule(name: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(
        write_pipeline,
        name,
        message=f"some message for {name}",
    )
    await fetch_current_time()
    return {"message": f"Schedule sent {name!r} in the background"}


async def fetch_current_time():
    logger.info(f"Fetch: {datetime.now()}")


@app.on_event("startup")
@repeat_every(seconds=10)
def broker_upper_messages():
    for _ in range(app.queue_limit):
        try:
            obj = app.queue.get_nowait()
            app.output_dict[obj["request_id"]] = obj["text"].upper()
            logger.info(f"Upper message: {app.output_dict}")
        except queue.Empty:
            pass


class Payload(BaseModel):
    text: str


async def get_result(request_id):
    while True:
        if request_id in app.output_dict:
            result = app.output_dict[request_id]
            del app.output_dict[request_id]
            return {"message": result}
        await asyncio.sleep(0.001)


@app.post("/upper", response_class=UJSONResponse)
async def message_upper(payload: Payload):
    request_id: str = str(uuid.uuid4())
    app.queue.put(
        {"text": payload.text, "request_id": request_id},
    )
    return await get_result(request_id)
