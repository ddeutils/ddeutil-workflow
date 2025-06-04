import json
from pathlib import Path
from platform import python_version
from typing import Annotated, Any, Optional

import typer
import uvicorn

from .__about__ import __version__
from .__types import DictData
from .api import app as fastapp
from .errors import JobError
from .job import Job
from .result import Result

app = typer.Typer(
    pretty_exceptions_enable=True,
)


@app.callback()
def callback():
    """Manage Workflow CLI app.

    Use it with the interface workflow engine.
    """


@app.command()
def version():
    """Get the ddeutil-workflow package version."""
    typer.echo(f"ddeutil-workflow=={__version__}")
    typer.echo(f"python-version=={python_version()}")


@app.command()
def job(
    params: Annotated[str, typer.Option(help="A job execute parameters")],
    job: Annotated[str, typer.Option(help="A job model")],
    parent_run_id: Annotated[str, typer.Option(help="A parent running ID")],
    run_id: Annotated[Optional[str], typer.Option(help="A running ID")] = None,
) -> None:
    """Job execution on the local.

    Example:
        ... workflow-cli job --params "{\"test\": 1}"
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


if __name__ == "__main__":
    app()
