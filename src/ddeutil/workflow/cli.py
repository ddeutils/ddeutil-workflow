# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import json
from pathlib import Path
from platform import python_version
from textwrap import dedent
from typing import Annotated, Any, Literal, Optional, Union

import typer
from pydantic import Field, TypeAdapter

from .__about__ import __version__
from .__types import DictData
from .conf import config
from .errors import JobError
from .job import Job
from .params import Param
from .workflow import Workflow

app = typer.Typer(pretty_exceptions_enable=True)


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


@app.command()
def init() -> None:
    """Initialize a Workflow structure on the current context."""
    config.conf_path.mkdir(exist_ok=True)
    (config.conf_path / ".confignore").touch()

    conf_example_path: Path = config.conf_path / "examples"
    conf_example_path.mkdir(exist_ok=True)

    example_template: Path = conf_example_path / "wf_examples.yml"
    example_template.write_text(
        dedent(
            """
        # Example workflow template.
        wf-example:
          type: Workflow
          desc: |
            An example workflow template that provide the demo of workflow.
          params:
            name:
                type: str
                default: "World"
          jobs:
            first-job:
              stages:

                - name: "Hello Stage"
                  echo: "Start say hi to the console"

                - name: "Call tasks"
                  uses: tasks/say-hello-func@example
                  with:
                    name: ${{ params.name }}
            second-job:

                - name: "Hello Env"
                  echo: "Start say hi with ${ WORKFLOW_DEMO_HELLO }"
        """
        ).lstrip("\n")
    )

    if "." in config.registry_caller:
        task_path = Path("./tasks")
        task_path.mkdir(exist_ok=True)

        dummy_tasks_path = task_path / "example.py"
        dummy_tasks_path.write_text(
            dedent(
                """
            from ddeutil.workflow import Result, tag

            @tag(name="example", alias="say-hello-func")
            def hello_world_task(name: str, rs: Result) -> dict[str, str]:
                \"\"\"Logging hello task function\"\"\"
                rs.trace.info(f"Hello, {name}")
                return {"name": name}
            """
            ).lstrip("\n")
        )

        init_path = task_path / "__init__.py"
        init_path.write_text("from .example import hello_world_task\n")

    dotenv_file = Path(".env")
    mode: str = "a" if dotenv_file.exists() else "w"
    with dotenv_file.open(mode=mode) as f:
        f.write("\n# Workflow env vars\n")
        f.write(
            "WORKFLOW_DEMO_HELLO=foo\n"
            "WORKFLOW_CORE_DEBUG_MODE=true\n"
            "WORKFLOW_LOG_TIMEZONE=Asia/Bangkok\n"
            "WORKFLOW_LOG_TRACE_ENABLE_WRITE=false\n"
            "WORKFLOW_LOG_AUDIT_ENABLE_WRITE=true\n"
        )

    typer.echo("Starter command:")
    typer.echo(
        "> `source .env && workflow-cli workflows execute --name=wf-example`"
    )


@app.command(name="job")
def execute_job(
    params: Annotated[str, typer.Option(help="A job execute parameters")],
    job: Annotated[str, typer.Option(help="A job model")],
    run_id: Annotated[str, typer.Option(help="A running ID")],
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
        raise ValueError(f"Jobs does not support format: {job!r}.") from e

    typer.echo(f"Job params: {params_dict}")
    context: DictData = {}
    try:
        _job.set_outputs(
            _job.execute(params=params_dict, run_id=run_id).context,
            to=context,
        )
        typer.echo("[JOB]: Context result:")
        typer.echo(json.dumps(context, default=str, indent=0))
    except JobError as err:
        typer.echo(f"[JOB]: {err.__class__.__name__}: {err}")


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
def workflow_execute(
    name: Annotated[
        str,
        typer.Option(help="A name of workflow template."),
    ],
    params: Annotated[
        str,
        typer.Option(help="A workflow execute parameters"),
    ] = "{}",
):
    """Execute workflow by passing a workflow template name."""
    try:
        params_dict: dict[str, Any] = json.loads(params)
    except json.JSONDecodeError as e:
        raise ValueError(f"Params does not support format: {params!r}.") from e

    typer.echo(f"Start execute workflow template: {name}")
    typer.echo(f"... with params: {params_dict}")


WORKFLOW_TYPE = Literal["Workflow"]


class WorkflowSchema(Workflow):
    """Override workflow model fields for generate JSON schema file."""

    type: WORKFLOW_TYPE = Field(description="A type of workflow template.")
    name: Optional[str] = Field(default=None, description="A workflow name.")
    params: dict[str, Union[Param, str]] = Field(
        default_factory=dict,
        description="A parameters that need to use on this workflow.",
    )


@workflow_app.command(name="json-schema")
def workflow_json_schema(
    output: Annotated[
        Path,
        typer.Option(help="An output file to export the JSON schema."),
    ] = Path("./json-schema.json"),
) -> None:
    """Generate JSON schema file from the Workflow model."""
    template = dict[str, WorkflowSchema]
    json_schema = TypeAdapter(template).json_schema(by_alias=True)
    template_schema: dict[str, str] = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Workflow Configuration JSON Schema",
        "version": __version__,
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
