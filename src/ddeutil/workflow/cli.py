# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import Annotated, Optional

from ddeutil.core import str2list
from typer import Argument, Typer, echo

from .conf import config

cli: Typer = Typer()


@cli.command()
def run(
    workflow: Annotated[
        str,
        Argument(help="A workflow name that want to run manually"),
    ],
    params: Annotated[
        str,
        Argument(
            help="A json string for parameters of this workflow execution.",
        ),
    ],
):
    """Run workflow workflow manually with an input custom parameters that able
    to receive with workflow params config.
    """
    echo(f"Running workflow name: ({type(workflow)}) {workflow!r}")
    echo(f"... with Parameters: ({type(params)}) {params!r}")

    from .result import Result
    from .workflow import Workflow

    try:
        wf: Workflow = Workflow.from_loader(name=workflow)
        rs: Result = wf.execute(params=json.loads(params))
    except Exception as err:
        echo(str(err))
        sys.exit(1)

    echo(f"Result: {rs}")
    sys.exit(0)


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
    echo(f"... with Excluded Parameters: {excluded!r}")
    externals: str = externals or "{}"

    # NOTE: Convert timezone on the stop date.
    if stop:
        stop: datetime = stop.astimezone(tz=config.tz)

    from .scheduler import schedule_runner

    try:
        # NOTE: Start running workflow scheduler application.
        workflow_rs: list[str] = schedule_runner(
            stop=stop, excluded=excluded, externals=json.loads(externals)
        )
        echo(f"Schedule with CLI run success with: {workflow_rs}")
    except Exception as err:
        echo(str(err))
        sys.exit(1)

    sys.exit(0)


@cli.callback()
def main():
    """
    Manage workflow with CLI.
    """


if __name__ == "__main__":
    cli()
