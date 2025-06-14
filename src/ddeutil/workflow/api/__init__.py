"""FastAPI Web Application for Workflow Management.

This module provides a RESTful API interface for workflow orchestration using
FastAPI. It enables remote workflow management, execution monitoring, and
provides endpoints for workflow operations.

The API supports:
    - Workflow execution and management
    - Job status monitoring
    - Log streaming and access
    - Result retrieval and analysis

Example:
    ```python
    from ddeutil.workflow.api import app

    # Run the API server
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    ```

Routes:
    - /workflows: Workflow management endpoints
    - /jobs: Job execution and monitoring
    - /logs: Log access and streaming
"""

# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import contextlib
import logging
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
from .routes import job, log, workflow

load_dotenv()
logger = logging.getLogger("uvicorn.error")


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[dict[str, list]]:
    """FastAPI application lifespan management.

    Manages the startup and shutdown lifecycle of the FastAPI application.
    Currently yields an empty dictionary for future extension.

    Args:
        _: FastAPI application instance (unused)

    Yields:
        dict: Empty dictionary for future lifespan data
    """
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
    """Health check endpoint for API status monitoring.

    Provides a simple health check endpoint to verify the API is running
    and responding correctly. Returns a JSON response with health status.

    Returns:
        UJSONResponse: JSON response confirming healthy API status

    Example:
        ```bash
        curl http://localhost:8000/
        # Returns: {"message": "Workflow already start up with healthy status."}
        ```
    """
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
    """Handle request validation errors from Pydantic models.

    Provides standardized error responses for request validation failures,
    including detailed error information for debugging and client feedback.

    Args:
        request: The FastAPI request object (unused)
        exc: The validation exception containing error details

    Returns:
        UJSONResponse: Standardized error response with validation details

    Example:
        When a request fails validation:
        ```json
        {
            "message": "Body does not parsing with model.",
            "detail": [...],
            "body": {...}
        }
        ```
    """
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
