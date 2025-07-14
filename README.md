# Workflow Orchestration

[![test](https://github.com/ddeutils/ddeutil-workflow/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/ddeutils/ddeutil-workflow/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/ddeutils/ddeutil-workflow/graph/badge.svg?token=3NDPN2I0H9)](https://codecov.io/gh/ddeutils/ddeutil-workflow)
[![pypi version](https://img.shields.io/pypi/v/ddeutil-workflow)](https://pypi.org/project/ddeutil-workflow/)
[![python support version](https://img.shields.io/pypi/pyversions/ddeutil-workflow)](https://pypi.org/project/ddeutil-workflow/)
[![size](https://img.shields.io/github/languages/code-size/ddeutils/ddeutil-workflow)](https://github.com/ddeutils/ddeutil-workflow)
[![gh license](https://img.shields.io/github/license/ddeutils/ddeutil-workflow)](https://github.com/ddeutils/ddeutil-workflow/blob/main/LICENSE)
[![code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

The **Lightweight Workflow Orchestration** with fewer dependencies the was created
for easy to make a simple metadata driven data workflow. It can use for data operator
by a `.yaml` template.

> [!WARNING]
> This package provide only orchestration workload. That mean you should not
> use the workflow stage to process any large volume data which use a lot of compute
> resource :cold_sweat:.

---

**:pushpin: <u>Rules of This Workflow</u>**:

1. The Minimum frequency unit of built-in scheduling is **1 Minute** 🕘
2. **Can not** re-run only failed stage and its pending downstream ↩️
3. All parallel tasks inside workflow core engine use **Multi-Threading** pool
   (Python 3.13 unlock GIL 🐍🔓)
4. Recommend to pass a **Secret Value** with environment variable in YAML template 🔐
5. Any datatime value convert to **UTC Timezone** 🌐

---

**:memo: <u>Workflow Diagrams</u>**:

This diagram show where is this application run on the production infrastructure.
You will see that this application do only running code with stress-less which mean
you should to set the data layer separate this core program before run this application.

```mermaid
flowchart LR
    A((fa:fa-user User))

    subgraph Docker Container
        direction TB
        G@{ shape: rounded, label: "📡Observe<br>Application" }
    end

    subgraph Docker Container
        direction TB
        B@{ shape: rounded, label: "🏃Workflow<br>Application" }
    end

    A <-->|action &<br>response| B
    B -...-> |response| G
    G -...-> |request| B

    subgraph Data Context
        D@{ shape: processes, label: "Logs" }
        E@{ shape: lin-cyl, label: "Audit<br>Logs" }
    end

    subgraph Config Context
        F@{ shape: tag-rect, label: "YAML<br>files" }
    end

    A ---> |push| H(Repo)
    H -.-> |pull| F

    B <-->|disable &<br>read| F

    B <-->|read &<br>write| E

    B -->|write| D

    D -.->|read| G
    E -.->|read| G
```

> [!WARNING]
> _**Disclaimer**_: I inspire the dynamic YAML statement from the [**GitHub Action**](https://github.com/features/actions),
> and my experience of data framework configs pattern. :grimacing:
>
> Other workflow orchestration services that I interest and pick them to be
> this project inspiration:
>
> - [Google **Workflows**](https://cloud.google.com/workflows)
> - [AWS **Step Functions**](https://aws.amazon.com/step-functions/)

## 📦 Installation

This project need `ddeutil` and `ddeutil-io` extension namespace packages to be
the base deps.
If you want to install this package with application add-ons, you should add
`app` in installation;

| Use-case       | Install Optional        | Support |
|----------------|-------------------------|:-------:|
| Python         | `ddeutil-workflow`      |    ✅    |
| FastAPI Server | `ddeutil-workflow[all]` |    ✅    |

Check the version of the current workflow package:

```shell
$ pip install ddeutil-workflow
$ workflow-cli version
```

Initial workflow project:

```shell
$ workflow-cli init
```

## 📖 Documentation

For comprehensive API documentation, examples, and best practices:

- **[Full Documentation](https://ddeutils.github.io/ddeutil-workflow/)** - Complete user guide and API reference
- **[Getting Started](https://ddeutils.github.io/ddeutil-workflow/getting-started/)** - Quick start guide
- **[API Reference](https://ddeutils.github.io/ddeutil-workflow/api/workflow/)** - Detailed API documentation
- **[Optimized Tracing](docs/optimized-tracing.md)** - High-performance logging system (2-5x faster)

## ⚡ Performance Improvements

The workflow system now includes an optimized tracing system that provides significant performance improvements:

- **🚀 2-5x faster logging** with buffered I/O operations
- **💾 60-80% reduction** in disk I/O operations
- **🛡️ Built-in thread safety** with minimal overhead
- **🔄 Backward compatible** - existing code automatically benefits
- **📊 Lower memory footprint** for high-volume logging

See [Optimized Tracing Documentation](docs/optimized-tracing.md) for details and performance benchmarks.

## 🎯 Usage

This is examples that use workflow file for running common Data Engineering
use-case.

> [!IMPORTANT]
> I recommend you to use the `call` stage for all actions that you want to do
> with workflow activity that you want to orchestrate. Because it is able to
> dynamic an input argument with the same call function that make you use less
> time to maintenance your data workflows.

```yaml
run-py-local:

   # Validate model that use to parsing exists for template file
   type: Workflow
   on:
      # If workflow deploy to schedule, it will run every 5 minutes
      # with Asia/Bangkok timezone.
      - cronjob: '*/5 * * * *'
        timezone: "Asia/Bangkok"
   params:
      # Incoming execution parameters will validate with this type. It allows
      # to set default value or templating.
      source-extract: str
      run-date: datetime
   jobs:
      getting-api-data:
         runs-on:
            type: local
         stages:
            - name: "Retrieve API Data"
              id: retrieve-api
              uses: tasks/get-api-with-oauth-to-s3@requests
              with:
                 # Arguments of source data that want to retrieve.
                 method: post
                 url: https://finances/open-data/currency-pairs/
                 body:
                    resource: ${{ params.source-extract }}

                    # You can use filtering like Jinja template but this
                    # package does not use it.
                    filter: ${{ params.run-date | fmt(fmt='%Y%m%d') }}
                 auth:
                    type: bearer
                    keys: ${API_ACCESS_REFRESH_TOKEN}

                 # Arguments of target data that want to land.
                 writing_mode: flatten
                 aws:
                    path: my-data/open-data/${{ params.source-extract }}

                    # This Authentication code should implement with your custom call
                    # function. The template allow you to use environment variable.
                    access_client_id: ${AWS_ACCESS_CLIENT_ID}
                    access_client_secret: ${AWS_ACCESS_CLIENT_SECRET}
```

Before execute this workflow, you should implement caller function first.

```text
registry-caller/
  ╰─ tasks.py
```

This function will store as module that will import from `WORKFLOW_CORE_REGISTRY_CALLER`
value (This config can override by extra parameters with `registry_caller` key).

> [!NOTE]
> You can use Pydantic Model as argument of your caller function. The core workflow
> engine will auto use the `model_validate` method before run your caller function.

```python
from ddeutil.workflow import Result, CallerSecret, tag
from ddeutil.workflow.errors import StageError
from pydantic import BaseModel


class AwsCredential(BaseModel):
    path: str
    access_client_id: str
    access_client_secret: CallerSecret


class RestAuth(BaseModel):
    type: str
    keys: CallerSecret


@tag("requests", alias="get-api-with-oauth-to-s3")
def get_api_with_oauth_to_s3(
     method: str,
     url: str,
     body: dict[str, str],
     auth: RestAuth,
     writing_node: str,
     aws: AwsCredential,
     result: Result,
) -> dict[str, int]:
    """Get the data from RestAPI via Authenticate with OAuth and then store to
    AWS S3 service.
    """
    result.trace.info("[CALLER]: Start get data via RestAPI to S3.")
    result.trace.info(f"... {method}: {url}")
    if method != "post":
        raise StageError(f"RestAPI does not support for {method} action.")
    # NOTE: If you want to use secret, you can use `auth.keys.get_secret_value()`.
    return {"records": 1000}
```

The above workflow template is main executor pipeline that you want to do. If you
want to schedule this workflow, you want to dynamic its parameters change base on
execution time such as `run-date` should change base on that workflow running date.

```python
from ddeutil.workflow import Workflow, Result

workflow: Workflow = Workflow.from_conf('run-py-local')
result: Result = workflow.execute(
   params={"source-extract": "USD-THB", "run-date": "2024-01-01"}
)
```

## :cookie: Configuration

The main configuration that use to dynamic changing this workflow engine for your
objective use environment variable only. If any configuration values do not set yet,
it will use default value and do not raise any error to you.

> [!IMPORTANT]
> The config value that you will set on the environment should combine with
> prefix, component, and name which is `WORKFLOW_{component}_{name}` (Upper case).

| Name                         | Component | Default                                                                                                                         | Description                                                                                      |
|:-----------------------------|:---------:|:--------------------------------------------------------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------------------|
| **REGISTRY_CALLER**          |   CORE    | `.`                                                                                                                             | List of importable string for the call stage.                                                    |
| **REGISTRY_FILTER**          |   CORE    | `ddeutil.workflow.templates`                                                                                                    | List of importable string for the filter template.                                               |
| **CONF_PATH**                |   CORE    | `./conf`                                                                                                                        | The config path that keep all template `.yaml` files.                                            |
| **STAGE_DEFAULT_ID**         |   CORE    | `false`                                                                                                                         | A flag that enable default stage ID that use for catch an execution output.                      |
| **GENERATE_ID_SIMPLE_MODE**  |   CORE    | `true`                                                                                                                          | A flog that enable generating ID with `md5` algorithm.                                           |
| **DEBUG_MODE**               |    LOG    | `true`                                                                                                                          | A flag that enable logging with debug level mode.                                                |
| **TIMEZONE**                 |    LOG    | `Asia/Bangkok`                                                                                                                  | A Timezone string value that will pass to `ZoneInfo` object.                                     |
| **FORMAT**                   |    LOG    | `%(asctime)s.%(msecs)03d (%(name)-10s, %(process)-5d,%(thread)-5d) [%(levelname)-7s] %(message)-120s (%(filename)s:%(lineno)s)` | A trace message console format.                                                                  |
| **FORMAT_FILE**              |    LOG    | `{datetime} ({process:5d}, {thread:5d}) {message:120s} ({filename}:{lineno})`                                                   | A trace message format that use to write to target pointer.                                      |
| **DATETIME_FORMAT**          |    LOG    | `%Y-%m-%d %H:%M:%S`                                                                                                             | A datetime format of the trace log.                                                              |
| **TRACE_HANDLERS**           |    LOG    | `[{"type": "console"}]`                                                                                                         | A pointer URL of trace log that use to emit log message. Now uses optimized handler by default.  |
| **AUDIT_URL**                |    LOG    | `file:./audits`                                                                                                                 | A pointer URL of audit log that use to write audit metrix.                                       |
| **AUDIT_ENABLE_WRITE**       |    LOG    | `true`                                                                                                                          | A flag that enable writing audit log after end execution in the workflow release step.           |

## :rocket: Deployment

This package able to run as an application service for receive manual trigger
from any node via RestAPI with the FastAPI package.

### API Server

This server use FastAPI package to be the base application.

```shell
(.venv) $ workflow-cli api --host 127.0.0.1 --port 80
```

> [!NOTE]
> If this package already deploy, it is able to use multiprocess;
> `$ workflow-cli api --host 127.0.0.1 --port 80 --workers 4`

### Docker Container

Build a Docker container from this package.

```shell
$ docker pull ghcr.io/ddeutils/ddeutil-workflow:latest
$ docker run --rm ghcr.io/ddeutils/ddeutil-workflow:latest ddeutil-worker
```

## :speech_balloon: Contribute

I do not think this project will go around the world because it has specific propose,
and you can create by your coding without this project dependency for long term
solution. So, on this time, you can open [the GitHub issue on this project :raised_hands:](https://github.com/ddeutils/ddeutil-workflow/issues)
for fix bug or request new feature if you want it.
