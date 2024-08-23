# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import json
import logging
from typing import Annotated, Optional

from ddeutil.core import str2list
from typer import Argument, Option, Typer

cli: Typer = Typer()
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
    excluded: Annotated[
        Optional[str],
        Option(help="A list of exclude workflow name in str."),
    ] = None,
):
    """Start workflow scheduler that will call workflow function from scheduler
    module.
    """
    excluded: list[str] = str2list(excluded) if excluded else []
    from .scheduler import workflow

    logging.info(f"Start schedule workflow: {excluded}")
    workflow(excluded=excluded)


@cli.callback()
def main():
    """
    Manage workflow with CLI.
    """


if __name__ == "__main__":
    cli()
