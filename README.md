# Workflow

[![test](https://github.com/ddeutils/ddeutil-workflow/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/ddeutils/ddeutil-workflow/actions/workflows/tests.yml)
[![python support version](https://img.shields.io/pypi/pyversions/ddeutil-workflow)](https://pypi.org/project/ddeutil-workflow/)
[![size](https://img.shields.io/github/languages/code-size/ddeutils/ddeutil-workflow)](https://github.com/ddeutils/ddeutil-workflow)
[![gh license](https://img.shields.io/github/license/ddeutils/ddeutil-workflow)](https://github.com/ddeutils/ddeutil-workflow/blob/main/LICENSE)
[![code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**Table of Contents**:

- [Installation](#installation)
- [Getting Started](#getting-started)
  - [On](#on)
  - [Pipeline](#pipeline)
- [Usage](#usage)
- [Configuration](#configuration)
- [Deployment](#deployment)

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
| Scheduler Service | `pip install ddeutil-workflow[schedule]` | :x:                |
| FastAPI Server    | `pip install ddeutil-workflow[api]`      | :x:                |


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

## Getting Started

The main feature of this project is the `Pipeline` object that can call any
registries function. The pipeline can handle everything that you want to do, it
will passing parameters and catching the output for re-use it to next step.

### On

The **On** is schedule object that receive crontab value and able to generate
datetime value with next or previous with any start point of an input datetime.

```yaml
# This file should keep under this path: `./root-path/conf-path/*`
on_every_5_min:
  type: on.On
  cron: "*/5 * * * *"
```

```python
from ddeutil.workflow.on import On

# NOTE: Start load the on data from `.yaml` template file with this key.
schedule = On.from_loader(name='on_every_5_min', externals={})

assert '*/5 * * * *' == str(schedule.cronjob)

cron_iter = schedule.generate('2022-01-01 00:00:00')

assert "2022-01-01 00:05:00" f"{cron_iter.next:%Y-%m-%d %H:%M:%S}"
assert "2022-01-01 00:10:00" f"{cron_iter.next:%Y-%m-%d %H:%M:%S}"
assert "2022-01-01 00:15:00" f"{cron_iter.next:%Y-%m-%d %H:%M:%S}"
```

### Pipeline

The **Pipeline** object that is the core feature of this project.

```yaml
# This file should keep under this path: `./root-path/conf-path/*`
pipeline-name:
  type: ddeutil.workflow.pipeline.Pipeline
  on: 'on_every_5_min'
  params:
    author-run:
      type: str
    run-date:
      type: datetime
  jobs:
    first-job:
      stages:
        - name: "Empty stage do logging to console only!!"
```

```python
from ddeutil.workflow.pipeline import Pipeline

pipe = Pipeline.from_loader(name='pipeline-name', externals={})
pipe.execute(params={'author-run': 'Local Workflow', 'run-date': '2024-01-01'})
```

> [!NOTE]
> The above parameter can use short declarative statement. You can pass a parameter
> type to the key of a parameter name but it does not handler default value if you
> run this pipeline workflow with schedule.
>
> ```yaml
> ...
> params:
>   author-run: str
>   run-date: datetime
> ...
> ```
>
> And for the type, you can remove `ddeutil.workflow` prefix because we can find
> it by looping search from `WORKFLOW_CORE_REGISTRY` value.

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
    - cronjob: '*/5 * * * *'
      timezone: "Asia/Bangkok"
  params:
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
            # This Authentication code should implement with your custom hook function
            aws_access_client_id: ${AWS_ACCESS_CLIENT_ID}
            aws_access_client_secret: ${AWS_ACCESS_CLIENT_SECRET}
```

## Configuration

| Environment                         | Component | Default                      | Description                                                                |
|-------------------------------------|-----------|------------------------------|----------------------------------------------------------------------------|
| `WORKFLOW_ROOT_PATH`                | Core      | .                            | The root path of the workflow application                                  |
| `WORKFLOW_CORE_REGISTRY`            | Core      | ddeutil.workflow,tests.utils | List of importable string for the hook stage                               |
| `WORKFLOW_CORE_REGISTRY_FILTER`     | Core      | ddeutil.workflow.utils       | List of importable string for the filter template                          |
| `WORKFLOW_CORE_PATH_CONF`           | Core      | conf                         | The config path that keep all template `.yaml` files                       |
| `WORKFLOW_CORE_TIMEZONE`            | Core      | Asia/Bangkok                 | A Timezone string value that will pass to `ZoneInfo` object                |
| `WORKFLOW_CORE_STAGE_DEFAULT_ID`    | Core      | true                         | A flag that enable default stage ID that use for catch an execution output |
| `WORKFLOW_CORE_STAGE_RAISE_ERROR`   | Core      | true                         | A flag that all stage raise StageException from stage execution            |
| `WORKFLOW_CORE_MAX_PIPELINE_POKING` | Core      | 4                            |                                                                            |
| `WORKFLOW_CORE_MAX_JOB_PARALLEL`    | Core      | 2                            | The maximum job number that able to run parallel in pipeline executor      |
| `WORKFLOW_LOG_ENABLE_WRITE`         | Log       | true                         | A flag that enable logging object saving log to its destination            |


**Application**:

| Environment                         | Default                          | Description                                                             |
|-------------------------------------|----------------------------------|-------------------------------------------------------------------------|
| `WORKFLOW_APP_PROCESS_WORKER`       | 2                                | The maximum process worker number that run in scheduler app module      |
| `WORKFLOW_APP_SCHEDULE_PER_PROCESS` | 100                              | A schedule per process that run parallel                                |
| `WORKFLOW_APP_STOP_BOUNDARY_DELTA`  | '{"minutes": 5, "seconds": 20}'  | A time delta value that use to stop scheduler app in json string format |

**API server**:

| Environment                          | Default | Description                                                                       |
|--------------------------------------|---------|-----------------------------------------------------------------------------------|
| `WORKFLOW_API_ENABLE_ROUTE_WORKFLOW` | true    | A flag that enable workflow route to manage execute manually and workflow logging |
| `WORKFLOW_API_ENABLE_ROUTE_SCHEDULE` | true    | A flag that enable run scheduler                                                  |

## Deployment

This package able to run as a application service for receive manual trigger
from the master node via RestAPI or use to be Scheduler background service
like crontab job but via Python API.

### Schedule Service

```shell
(venv) $ python src.ddeutil.workflow.app
```

### API Server

```shell
(venv) $ uvicorn src.ddeutil.workflow.api:app --host 0.0.0.0 --port 80 --reload
```

> [!NOTE]
> If this package already deploy, it able to use
> `uvicorn ddeutil.workflow.api:app --host 0.0.0.0 --port 80`
