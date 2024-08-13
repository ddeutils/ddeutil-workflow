import logging
import time

from fastapi import BackgroundTasks, FastAPI

app = FastAPI()


def write_pipeline(task_id: str, message=""):
    logging.info(task_id, ":", message)
    time.sleep(5)
    logging.info(task_id, ": run task successfully!!!")


@app.post("/schedule/{pipeline}")
async def send_schedule(pipeline: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(
        write_pipeline,
        pipeline,
        message=f"some message for {pipeline}",
    )
    return {"message": f"Schedule sent {pipeline!r} in the background"}


@app.get("/pipeline/{pipeline}")
async def get_pipeline(
    pipeline: str,
):
    return {"message": f"getting pipeline {pipeline}"}


@app.get("/pipeline/{pipeline}/logging")
async def get_pipeline_log(
    pipeline: str,
):
    return {"message": f"getting pipeline {pipeline} logging"}
