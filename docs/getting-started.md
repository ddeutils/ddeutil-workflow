# Getting Started

This quick start use-case is getting data from external API and then prepare these
data and finally, aggregate them into the silver data zone by daily basis.

## Prerequisite

I will use only the core package of the workflow and run with manual action.

```shell
$ pip install uv
$ uv pip install -U ddeutil-workflow
```

**Project structure:**

```text
project/
 ├─ conf/
 │   ╰─ manual-workflow.yml
 ├─ logs/
 ├─ src/
 │   ╰─ tasks/
 │       ├─ __init__.py
 │       ╰─ https_call.py
 ├─ main.py
 ╰─ .env
```

## Getting Started

Create initial config path at `.env`:

```dotenv
WORKFLOW_CORE_REGISTRY_CALLER=src
WORKFLOW_LOG_TIMEZONE=Asia/Bangkok
WORKFLOW_LOG_AUDIT_ENABLE_WRITE=true
WORKFLOW_LOG_TRACE_ENABLE_WRITE=true
```

Create the first pipeline template at `./conf/manual-workflow.yml`:

```yaml title="./conf/manual-workflow.yml"
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

Create the called function that use on your stage.

1. Create `__init__.py` file inside `./src/tasks` folder for import your called
   function from your module.

   ```python title="./src/__init__.py"
   from .https_call import *
   ```

2. Create `https_call.py` file inside `./src/tasks` folder to be task module.

   ```python title="./src/https_call.py"
   from ddeutil.workflow import Result, tag


   @tag("httpx", alias="https-external")
   def demo_http_to_external_task(url: str, auth: str, result: Result) -> dict[str, int]:
       result.trace.info(f"Start POST: {url} with auth: {auth}")
       return {"counts": 0}
   ```

   The name of called function can be free text with snake case. The stage will
   use `alias` name to search this function instead its function name.

## Run Workflow

The workflow allow you to run with 2 modes, `execute` and `release` modes.

### Execute

At the `main.py` file:

```python title="./main.py"
from ddeutil.workflow import Workflow, Result


def call_execute():
    result: Result = (
        Workflow
        .from_conf('wf-run-manual')
        .execute(params={"run_date": "2024-08-01"})
    )
    print(result)


if __name__ == '__main__':
    call_execute()
```

```text

```

### Release

At the `main.py` file:

```python title="./main.py"
from datetime import datetime
from ddeutil.workflow import Workflow, Result, config


def call_release():
    result: Result = (
        Workflow
        .from_conf('wf-run-manual')
        .release(
            datetime.now(tz=config.tz),
            params={"run_date": "2024-08-01"},
        )
    )
    print(result)


if __name__ == '__main__':
    call_release()
```

```text

```

The audit file that keep from this release execution:

```text
project/
 ╰─ audits/
     ╰─ workflow=wf-run-manual/
         ╰─ release=20240101001011/
             ╰─ 820626787820250106163236493894.log
```

## Conclusion

You can run any workflow that you want by config a YAML file. If it raises any
error from your caller stage, you can observe the error log in log path with
the release running ID from `run_id` attribute of the return Result object.

```text
project/
 ╰─ logs/
     ╰─ run_id=820626787820250106163236493894/
         ├─ metadata.json
         ├─ stderr.txt
         ╰─ stdout.txt
```
