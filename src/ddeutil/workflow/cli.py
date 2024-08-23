# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import logging
from typing import Optional

from typer import Typer

cli: Typer = Typer()


@cli.command()
def run(pipeline: str):
    """Run workflow manually"""
    logging.info(f"Running pipeline name: {pipeline}")


@cli.command()
def schedule(exclude: Optional[str]):
    """Start workflow scheduler"""
    from .scheduler import workflow

    logging.info(f"Start schedule workflow: {exclude}")
    workflow()


@cli.callback()
def main():
    """
    Manage workflow with CLI.
    """


if __name__ == "__main__":
    cli()
