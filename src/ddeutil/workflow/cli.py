import json
from typing import Annotated, Any

import typer
import uvicorn

from .api import app as fastapp
from .api.logs import LOGGING_CONFIG

app = typer.Typer(
    pretty_exceptions_enable=True,
)


@app.callback()
def callback():
    """
    Awesome Portal Gun
    """
    typer.echo("Start call from callback function")


@app.command()
def job(
    params: Annotated[str, typer.Option(help="A job execute parameters")],
):
    """Job execution on the local.

    Example:
        ... workflow-cli job --params "{\"test\": 1}"
    """
    try:
        params_dict: dict[str, Any] = json.loads(params)
    except json.JSONDecodeError as e:
        raise ValueError(f"params does not support format: {params!r}.") from e
    typer.echo(f"Job params: {params_dict}")


@app.command()
def api(
    host: Annotated[str, typer.Option(help="A host url.")] = "0.0.0.0",
    port: Annotated[int, typer.Option(help="A port url.")] = 80,
    debug: Annotated[bool, typer.Option(help="A debug mode flag")] = True,
):
    """
    Provision API application from the FastAPI.
    """

    uvicorn.run(
        fastapp,
        host=host,
        port=port,
        log_config=uvicorn.config.LOGGING_CONFIG | LOGGING_CONFIG,
        log_level=("DEBUG" if debug else "INFO"),
    )


if __name__ == "__main__":
    app()
