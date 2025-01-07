# Getting Started

This execution usecase is getting data from external API and prepare that data
and aggregate it into daily layer to silver data zone.

## Prerequisite

I will use only the core package of the workflow and run with manual action.

```shell
pip install uv
uv pip install -U ddeutil-workflow
```

Project structure:

```text
root/
 ├─ conf/
 │   ╰─ manual-workflow.yml
 ├─ logs/
 ├─ src/
 │   ╰─ hooks/
 │       ├─ __init__.py
 │       ╰─ https_hook.py
 ├─ main.py
 ╰─ .env
```

## Getting Started

Create initial config path at `.env`:

```dotenv
WORKFLOW_LOG_ENABLE_WRITE=true
WORKFLOW_CORE_REGISTRY=src
WORKFLOW_CORE_TIMEZONE=Asia/Bangkok
```

Create the first pipeline template at `./conf/manual-workflow.yml`:

```yaml
wf-run-manual:
  type: Workflow
  params:
    run_date: datetime
  jobs:
    stage-to-curated:
      stages:
        - name: "Extract data from external API"
          uses: tasks/https-external@httpx
          with:
            url: "https://some-endpoint/api/v1/extract"
            auth: "http_conn_id"
            incremental: {{ params.run_date }}
```

Create the hook function that use on your stage.

At `./src/__init__.py`:

```python
from .https_hook import *
```

At `./src/https_hook.py`:

```python
from ddeutil.workflow.hook import tag


@tag("httpx", alias="https-external")
def dummy_task_polars_dir(url: str, auth: str) -> dict[str, int]:
    print(f"Start POST: {url} with auth: {auth}")
    return {"counts": 0}
```

## Run Workflow

### Execute

At the `main.py` file:

```python
from ddeutil.workflow import Workflow
from ddeutil.workflow.result import Result


def call_execute():
    result: Result = (
        Workflow
        .from_loader('wf-run-manual')
        .execute(params={"run_date": "2024-08-01"})
    )
    print(result)


if __name__ == '__main__':
    call_execute()
```

### Release

```python
from datetime import datetime
from ddeutil.workflow import Workflow, config
from ddeutil.workflow.result import Result


def call_release():
    result: Result = (
        Workflow
        .from_loader('wf-run-manual')
        .release(
            datetime.now(tz=config.tz),
            params={"run_date": "2024-08-01"},
        )
    )
    print(result)


if __name__ == '__main__':
    call_release()
```

The log file that keep from this release:

```text
root/
 ╰─ logs/
     ╰─ workflow=wf-run-manual
         ╰─ release=20240101001011
             ╰─ 820626787820250106163236493894.log
```
