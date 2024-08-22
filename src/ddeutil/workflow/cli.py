# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

from typing import Optional

from typer import Typer

cli: Typer = Typer()
state = {"verbose": False}


@cli.command()
def run(pipeline: str):
    """Run workflow manually"""
    if state["verbose"]:
        print("About to create a user")

    print(f"Creating user: {pipeline}")

    if state["verbose"]:
        print("Just created a user")


@cli.command()
def schedule(exclude: Optional[str]):
    """Start workflow scheduler"""
    if state["verbose"]:
        print("About to delete a user")

    print(f"Deleting user: {exclude}")

    if state["verbose"]:
        print("Just deleted a user")


@cli.callback()
def main(verbose: bool = False):
    """
    Manage workflow with CLI.
    """
    if verbose:
        print("Will write verbose output")
        state["verbose"] = True


if __name__ == "__main__":
    cli()
