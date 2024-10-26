# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Annotated, Optional

from ddeutil.core import str2list
from typer import Argument, Option, Typer

from .conf import config, get_logger

logger = get_logger("ddeutil.workflow")
cli: Typer = Typer()
cli_log: Typer = Typer()
cli.add_typer(
    cli_log,
    name="log",
    help="Logging of workflow CLI",
)


@cli.command()
def run(
    workflow: Annotated[
        str,
        Argument(help="A workflow name that want to run manually"),
    ],
    params: Annotated[
        str,
        Argument(
            help="A json string for parameters of this workflow execution."
        ),
    ],
):
    """Run workflow workflow manually with an input custom parameters that able
    to receive with workflow params config.
    """
    logger.info(f"Running workflow name: {workflow}")
    logger.info(f"... with Parameters: {json.dumps(json.loads(params))}")


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
            help="A json string for parameters of this workflow execution."
        ),
    ] = None,
):
    """Start workflow scheduler that will call workflow function from scheduler
    module.
    """
    excluded: list[str] = str2list(excluded) if excluded else []
    externals: str = externals or "{}"
    if stop:
        stop: datetime = stop.astimezone(tz=config.tz)

    from .scheduler import workflow_runner

    # NOTE: Start running workflow scheduler application.
    workflow_rs: list[str] = workflow_runner(
        stop=stop, excluded=excluded, externals=json.loads(externals)
    )
    logger.info(f"Application run success: {workflow_rs}")


@cli_log.command("workflow-get")
def workflow_log_get(
    name: Annotated[
        str,
        Argument(help="A workflow name that want to getting log"),
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
    logger.info(f"{name} : limit {limit} : desc: {desc}")
    return [""]


class LogMode(str, Enum):
    get = "get"
    delete = "delete"


@cli_log.command("workflow-delete")
def workflow_log_delete(
    mode: Annotated[
        LogMode,
        Argument(case_sensitive=True),
    ]
):
    logger.info(mode)


@cli.callback()
def main():
    """
    Manage workflow with CLI.
    """


if __name__ == "__main__":
    cli()
