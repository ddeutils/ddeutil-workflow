# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import json
from pathlib import Path
from platform import python_version
from typing import Annotated, Any, Literal, Optional, Union

import typer
from pydantic import Field, TypeAdapter

from .__about__ import __version__
from .__types import DictData
from .errors import JobError
from .event import Crontab
from .job import Job
from .params import Param
from .result import Result
from .workflow import Workflow

app = typer.Typer(
    pretty_exceptions_enable=True,
)


@app.callback()
def callback() -> None:
    """Manage Workflow Orchestration CLI.

    Use it with the interface workflow engine.
    """


@app.command()
def version() -> None:
    """Get the ddeutil-workflow package version."""
    typer.echo(f"ddeutil-workflow=={__version__}")
    typer.echo(f"python-version=={python_version()}")


@app.command(name="job")
def execute_job(
    params: Annotated[str, typer.Option(help="A job execute parameters")],
    job: Annotated[str, typer.Option(help="A job model")],
    parent_run_id: Annotated[str, typer.Option(help="A parent running ID")],
    run_id: Annotated[Optional[str], typer.Option(help="A running ID")] = None,
) -> None:
    """Job execution on the local.

    Example:
        ... workflow-cli job --params \"{\\\"test\\\": 1}\"
    """
    try:
        params_dict: dict[str, Any] = json.loads(params)
    except json.JSONDecodeError as e:
        raise ValueError(f"Params does not support format: {params!r}.") from e

    try:
        job_dict: dict[str, Any] = json.loads(job)
        _job: Job = Job.model_validate(obj=job_dict)
    except json.JSONDecodeError as e:
        raise ValueError(f"Params does not support format: {params!r}.") from e

    typer.echo(f"Job params: {params_dict}")
    rs: Result = Result(
        run_id=run_id,
        parent_run_id=parent_run_id,
    )

    context: DictData = {}
    try:
        _job.set_outputs(
            _job.execute(
                params=params_dict,
                run_id=rs.run_id,
                parent_run_id=rs.parent_run_id,
            ).context,
            to=context,
        )
    except JobError as err:
        rs.trace.error(f"[JOB]: {err.__class__.__name__}: {err}")


@app.command()
def api(
    host: Annotated[str, typer.Option(help="A host url.")] = "0.0.0.0",
    port: Annotated[int, typer.Option(help="A port url.")] = 80,
    debug: Annotated[bool, typer.Option(help="A debug mode flag")] = True,
    workers: Annotated[int, typer.Option(help="A worker number")] = None,
    reload: Annotated[bool, typer.Option(help="A reload flag")] = False,
):
    """
    Provision API application from the FastAPI.
    """
    import uvicorn

    from .api import app as fastapp
    from .api.log_conf import LOGGING_CONFIG

    # LOGGING_CONFIG = {}

    uvicorn.run(
        fastapp,
        host=host,
        port=port,
        log_config=uvicorn.config.LOGGING_CONFIG | LOGGING_CONFIG,
        # NOTE: Logging level of uvicorn should be lowered case.
        log_level=("debug" if debug else "info"),
        workers=workers,
        reload=reload,
    )


@app.command()
def make(
    name: Annotated[Path, typer.Argument()],
) -> None:
    """
    Create Workflow YAML template.

    :param name:
    """
    typer.echo(f"Start create YAML template filename: {name.resolve()}")


workflow_app = typer.Typer()
app.add_typer(workflow_app, name="workflows", help="An Only Workflow CLI.")


@workflow_app.callback()
def workflow_callback():
    """Manage Only Workflow CLI."""


@workflow_app.command(name="execute")
def workflow_execute():
    """"""


WORKFLOW_TYPE = Literal["Workflow"]


class WorkflowSchema(Workflow):
    """Override workflow model fields for generate JSON schema file."""

    type: WORKFLOW_TYPE = Field(description="A type of workflow template.")
    name: Optional[str] = Field(default=None, description="A workflow name.")
    params: dict[str, Union[Param, str]] = Field(
        default_factory=dict,
        description="A parameters that need to use on this workflow.",
    )
    on: Union[list[Union[Crontab, str]], str] = Field(
        default_factory=list,
        description="A list of Crontab instance for this workflow schedule.",
    )


CRONTAB_TYPE = Literal["Crontab"]


class CrontabSchema(Crontab):
    """Override crontab model fields for generate JSON schema file."""

    type: CRONTAB_TYPE = Field(description="A type of crontab template.")


@workflow_app.command(name="json-schema")
def workflow_json_schema(
    output: Annotated[
        Path,
        typer.Option(help="An output file to export the JSON schema."),
    ] = Path("./json-schema.json"),
) -> None:
    """Generate JSON schema file from the Workflow model."""
    template = dict[str, Union[WorkflowSchema, CrontabSchema]]
    json_schema = TypeAdapter(template).json_schema(by_alias=True)
    template_schema: dict[str, str] = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Workflow Configuration Schema",
        "version": "1.0.0",
    }
    with open(output, mode="w", encoding="utf-8") as f:
        json.dump(template_schema | json_schema, f, indent=2)


log_app = typer.Typer()
app.add_typer(log_app, name="logs", help="An Only Log CLI.")


@log_app.callback()
def log_callback():
    """Manage Only Log CLI."""


if __name__ == "__main__":
    app()
