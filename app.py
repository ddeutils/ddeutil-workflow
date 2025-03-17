# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""This file use for provisioning the uvicorn server vis Python API."""
from __future__ import annotations

import uvicorn

from src.ddeutil.workflow.api import app
from src.ddeutil.workflow.api.log import LOGGING_CONFIG

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        "Provision the Uvicorn server via Python API"
    )
    parser.add_argument(
        "--host",
        help="A host IP address of this server.",
        default="0.0.0.0",
        type=str,
        dest="host",
    )
    parser.add_argument(
        "--port",
        help="A port of this server.",
        default=80,
        type=int,
        dest="port",
    )
    args = parser.parse_args()
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_config=uvicorn.config.LOGGING_CONFIG | LOGGING_CONFIG,
    )
