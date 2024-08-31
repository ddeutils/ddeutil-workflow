# Workflow

[![test](https://github.com/ddeutils/ddeutil-workflow/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/ddeutils/ddeutil-workflow/actions/workflows/tests.yml)
[![python support version](https://img.shields.io/pypi/pyversions/ddeutil-workflow)](https://pypi.org/project/ddeutil-workflow/)
[![size](https://img.shields.io/github/languages/code-size/ddeutils/ddeutil-workflow)](https://github.com/ddeutils/ddeutil-workflow)
[![gh license](https://img.shields.io/github/license/ddeutils/ddeutil-workflow)](https://github.com/ddeutils/ddeutil-workflow/blob/main/LICENSE)
[![code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

The **Lightweight workflow orchestration** with less dependencies the was created
for easy to make a simple metadata driven for data pipeline orchestration.
It can to use for data operator by a `.yaml` template.

> [!WARNING]
> This package provide only orchestration workload. That mean you should not use
> workflow stage to process any large data which use lot of compute usecase.

In my opinion, I think it should not create duplicate pipeline codes if I can
write with dynamic input parameters on the one template pipeline that just change
the input parameters per use-case instead.
This way I can handle a lot of logical pipelines in our orgs with only metadata
configuration. It called **Metadata Driven Data Pipeline**.

Next, we should get some monitoring tools for manage logging that return from
pipeline running. Because it not show us what is a use-case that running data
pipeline.

> [!NOTE]
> _Disclaimer_: I inspire the dynamic statement from the GitHub Action `.yml` files
> and all of config file from several data orchestration framework tools from my
> experience on Data Engineer.

**Rules of This Workflow engine**:

1. Minimum unit of scheduling is 1 minute
2. Cannot re-run only failed stage and its pending downstream
3. All parallel tasks inside workflow engine use Threading
   (Because Python 3.13 unlock GIL)

## Installation

This project need `ddeutil-io` extension namespace packages. If you want to install
this package with application add-ons, you should add `app` in installation;

| Usecase           | Install Optional                         | Support            |
|-------------------|------------------------------------------|--------------------|
| Python & CLI      | `pip install ddeutil-workflow`           | :heavy_check_mark: |
| FastAPI Server    | `pip install ddeutil-workflow[api]`      | :heavy_check_mark: |


> I added this feature to the main milestone.
>
> **Docker Images** supported:
>
> | Docker Image                | Python Version | Support |
> |-----------------------------|----------------|---------|
> | ddeutil-workflow:latest     | `3.9`          | :x:     |
> | ddeutil-workflow:python3.10 | `3.10`         | :x:     |
> | ddeutil-workflow:python3.11 | `3.11`         | :x:     |
> | ddeutil-workflow:python3.12 | `3.12`         | :x:     |

## Usage

This is examples that use workflow file for running common Data Engineering
use-case.

> [!IMPORTANT]
> I recommend you to use the `hook` stage for all actions that you want to do
> with pipeline activity that you want to orchestrate. Because it able to dynamic
> an input argument with the same hook function that make you use less time to
> maintenance your data pipelines.

```yaml
run_py_local:
   type: pipeline.Pipeline
   on:
      # If pipeline workflow deploy to schedule, it will running every 5 minutes
      # with Asia/Bangkok timezone.
      - cronjob: '*/5 * * * *'
        timezone: "Asia/Bangkok"
   params:
      # Incoming execution parameters will validate with this type. It allow
      # to set default value or templating.
      author-run: str
      run-date: datetime
   jobs:
      getting-api-data:
         stages:
            - name: "Retrieve API Data"
              id: retrieve-api
              uses: tasks/get-api-with-oauth-to-s3@requests
              with:
                 url: https://open-data/
                 auth: ${API_ACCESS_REFRESH_TOKEN}
                 aws_s3_path: my-data/open-data/

                 # This Authentication code should implement with your custom hook function.
                 # The template allow you to use environment variable.
                 aws_access_client_id: ${AWS_ACCESS_CLIENT_ID}
                 aws_access_client_secret: ${AWS_ACCESS_CLIENT_SECRET}
```

## Configuration

| Environment                         | Component | Default                         | Description                                                                |
|-------------------------------------|-----------|---------------------------------|----------------------------------------------------------------------------|
| `WORKFLOW_ROOT_PATH`                | Core      | .                               | The root path of the workflow application                                  |
| `WORKFLOW_CORE_REGISTRY`            | Core      | ddeutil.workflow,tests.utils    | List of importable string for the hook stage                               |
| `WORKFLOW_CORE_REGISTRY_FILTER`     | Core      | ddeutil.workflow.utils          | List of importable string for the filter template                          |
| `WORKFLOW_CORE_PATH_CONF`           | Core      | conf                            | The config path that keep all template `.yaml` files                       |
| `WORKFLOW_CORE_TIMEZONE`            | Core      | Asia/Bangkok                    | A Timezone string value that will pass to `ZoneInfo` object                |
| `WORKFLOW_CORE_STAGE_DEFAULT_ID`    | Core      | true                            | A flag that enable default stage ID that use for catch an execution output |
| `WORKFLOW_CORE_STAGE_RAISE_ERROR`   | Core      | true                            | A flag that all stage raise StageException from stage execution            |
| `WORKFLOW_CORE_MAX_PIPELINE_POKING` | Core      | 4                               |                                                                            |
| `WORKFLOW_CORE_MAX_JOB_PARALLEL`    | Core      | 2                               | The maximum job number that able to run parallel in pipeline executor      |
| `WORKFLOW_LOG_DEBUG_MODE`           | Log       | true                            | A flag that enable logging with debug level mode                           |
| `WORKFLOW_LOG_ENABLE_WRITE`         | Log       | true                            | A flag that enable logging object saving log to its destination            |
| `WORKFLOW_APP_PROCESS_WORKER`       | Schedule  | 2                               | The maximum process worker number that run in scheduler app module         |
| `WORKFLOW_APP_SCHEDULE_PER_PROCESS` | Schedule  | 100                             | A schedule per process that run parallel                                   |
| `WORKFLOW_APP_STOP_BOUNDARY_DELTA`  | Schedule  | '{"minutes": 5, "seconds": 20}' | A time delta value that use to stop scheduler app in json string format    |

**API Application**:

| Environment                          | Component | Default | Description                                                                       |
|--------------------------------------|-----------|---------|-----------------------------------------------------------------------------------|
| `WORKFLOW_API_ENABLE_ROUTE_WORKFLOW` | API       | true    | A flag that enable workflow route to manage execute manually and workflow logging |
| `WORKFLOW_API_ENABLE_ROUTE_SCHEDULE` | API       | true    | A flag that enable run scheduler                                                  |

## Deployment

This package able to run as a application service for receive manual trigger
from the master node via RestAPI or use to be Scheduler background service
like crontab job but via Python API.

### Schedule App

```shell
(venv) $ ddeutil-workflow schedule
```

### API Server

```shell
(venv) $ uvicorn src.ddeutil.workflow.api:app --host 127.0.0.1 --port 80
```

> [!NOTE]
> If this package already deploy, it able to use
> `uvicorn ddeutil.workflow.api:app --host 127.0.0.1 --port 80 --workers 4`
