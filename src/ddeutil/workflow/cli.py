# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from enum import Enum
from typing import Annotated, Optional
from zoneinfo import ZoneInfo

from ddeutil.core import str2list
from typer import Argument, Option, Typer

cli: Typer = Typer()
cli_log: Typer = Typer()
cli.add_typer(
    cli_log,
    name="log",
    help="Logging commands",
)
logging.basicConfig(
    level=logging.DEBUG,
    format=(
        "%(asctime)s.%(msecs)03d (%(name)-10s, %(process)-5d, %(thread)-5d) "
        "[%(levelname)-7s] %(message)-120s (%(filename)s:%(lineno)s)"
    ),
    handlers=[logging.StreamHandler()],
    datefmt="%Y-%m-%d %H:%M:%S",
)


@cli.command()
def run(
    pipeline: Annotated[
        str,
        Argument(help="A pipeline name that want to run manually"),
    ],
    params: Annotated[
        str,
        Argument(
            help="A json string for parameters of this pipeline execution."
        ),
    ],
):
    """Run pipeline workflow manually with an input custom parameters that able
    to receive with pipeline params config.
    """
    logging.info(f"Running pipeline name: {pipeline}")
    logging.info(f"... with Parameters: {json.dumps(json.loads(params))}")


@cli.command()
def schedule(
    stop: Annotated[
        Optional[datetime],
        Argument(
            formats=["%Y-%m-%d", "%Y-%m-%d %H:%M:%S"],
            help="A stopping datetime that want to stop on schedule app.",
        ),
    ] = None,
    excluded: Annotated[
        Optional[str],
        Argument(help="A list of exclude workflow name in str."),
    ] = None,
    externals: Annotated[
        Optional[str],
        Argument(
            help="A json string for parameters of this pipeline execution."
        ),
    ] = None,
):
    """Start workflow scheduler that will call workflow function from scheduler
    module.
    """
    excluded: list[str] = str2list(excluded) if excluded else []
    externals: str = json.loads(externals or "{}")

    logging.info(f"Start schedule workflow with excluded: {excluded}")
    logging.info(f"... with Parameters: {json.dumps(json.loads(externals))}")
    if stop:
        stop: datetime = stop.astimezone(
            tz=ZoneInfo(os.getenv("WORKFLOW_CORE_TIMEZONE", "UTC"))
        )
        logging.info(f"... stop at: {stop}")

    from .scheduler import workflow

    # NOTE: Start running workflow scheduler application.
    workflow_rs: list[str] = workflow(stop=stop, excluded=excluded)
    logging.info(f"Application run success: {workflow_rs}")


@cli_log.command("pipeline-get")
def pipeline_log_get(
    name: Annotated[
        str,
        Argument(help="A pipeline name that want to getting log"),
    ],
    limit: Annotated[
        int,
        Argument(help="A number of the limitation of logging"),
    ] = 100,
    desc: Annotated[
        bool,
        Option(
            "--desc",
            help="A descending flag that order by logging release datetime.",
        ),
    ] = True,
):
    logging.info(f"{name} : limit {limit} : desc: {desc}")
    return [""]


class LogMode(str, Enum):
    get = "get"
    delete = "delete"


@cli_log.command("pipeline-delete")
def pipeline_log_delete(
    mode: Annotated[
        LogMode,
        Argument(case_sensitive=True),
    ]
):
    logging.info(mode)
    return


@cli.callback()
def main():
    """
    Manage workflow with CLI.
    """


if __name__ == "__main__":
    cli()
