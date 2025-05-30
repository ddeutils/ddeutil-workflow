# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi import status as st
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import UJSONResponse

from ..__about__ import __version__
from ..conf import api_config
from ..logs import get_logger
from .routes import job, log, workflow

load_dotenv()
logger = get_logger("uvicorn.error")


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[dict[str, list]]:
    """Lifespan function for the FastAPI application."""
    yield {}


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


@app.get(path="/", response_class=UJSONResponse)
async def health() -> UJSONResponse:
    """Index view that not return any template without json status."""
    logger.info("[API]: Workflow API Application already running ...")
    return UJSONResponse(
        content={"message": "Workflow already start up with healthy status."},
        status_code=st.HTTP_200_OK,
    )


# NOTE: Add the jobs and logs routes by default.
app.include_router(job, prefix=api_config.prefix_path)
app.include_router(log, prefix=api_config.prefix_path)
app.include_router(workflow, prefix=api_config.prefix_path)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> UJSONResponse:
    """Error Handler for model validate does not valid."""
    _ = request
    return UJSONResponse(
        status_code=st.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder(
            {
                "message": "Body does not parsing with model.",
                "detail": exc.errors(),
                "body": exc.body,
            }
        ),
    )
