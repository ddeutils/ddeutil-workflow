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

In my opinion, I think it should not create duplicate workflow codes if I can
write with dynamic input parameters on the one template workflow that just change
the input parameters per use-case instead.
This way I can handle a lot of logical workflows in our orgs with only metadata
configuration. It called **Metadata Driven Data Workflow**.

**:pushpin: <u>Rules of This Workflow engine</u>**:

1. The Minimum frequency unit of scheduling is **1 minute** :warning:
2. Can not re-run only failed stage and its pending downstream :rotating_light:
3. All parallel tasks inside workflow engine use Multi-Threading
   (Python 3.13 unlock GIL :unlock:)

**:memo: <u>Workflow Diagrams</u>**:

```mermaid
flowchart LR
    subgraph Interface
    A((User))
        subgraph Docker Container
        G@{ shape: rounded, label: "Observe<br>Application" }
        end
    end

    A --->|action| B(Workflow<br>Application)
    B ---> |response| A
    B -..-> |response| G
    G -..-> |request| B

    subgraph Docker Container
    B
    end

    subgraph Data Context
    D@{ shape: processes, label: "Logs" }
    E@{ shape: lin-cyl, label: "Metadata" }
    end

    subgraph Git Context
    F@{ shape: tag-rect, label: "YAML<br>files" }
    end

    B --->|disable| F
    F --->|read| B

    B --->|write| E
    E --->|read| B
    B --->|write| D

    D -.->|read| G
    E -.->|read| G
```

> [!NOTE]
> _Disclaimer_: I inspire the dynamic statement from the [**GitHub Action**](https://github.com/features/actions)
> with `.yml` files and all configs file from several data orchestration framework
> tools from my experience on Data Engineer. :grimacing:
>
> Other workflow tools that I interest on them and pick some interested feature
> implement to this package:
>
> - [Google **Workflows**](https://cloud.google.com/workflows)
> - [AWS **Step Functions**](https://aws.amazon.com/step-functions/)

## :round_pushpin: Installation

This project need `ddeutil` and `ddeutil-io` extension namespace packages.
If you want to install this package with application add-ons, you should add
`app` in installation;

| Use-case       | Install Optional         | Support            |
|----------------|--------------------------|--------------------|
| Python         | `ddeutil-workflow`       | :heavy_check_mark: |
| FastAPI Server | `ddeutil-workflow[api]`  | :heavy_check_mark: |

## :beers: Usage

This is examples that use workflow file for running common Data Engineering
use-case.

> [!IMPORTANT]
> I recommend you to use the `hook` stage for all actions that you want to do
> with workflow activity that you want to orchestrate. Because it is able to
> dynamic an input argument with the same hook function that make you use less
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
                 aws_s3_path: my-data/open-data/${{ params.source-extract }}

                 # This Authentication code should implement with your custom hook
                 # function. The template allow you to use environment variable.
                 aws_access_client_id: ${AWS_ACCESS_CLIENT_ID}
                 aws_access_client_secret: ${AWS_ACCESS_CLIENT_SECRET}
```

The above workflow template is main executor pipeline that you want to do. If you
want to schedule this workflow, you want to dynamic its parameters change base on
execution time such as `run-date` should change base on that workflow running date.

So, this package provide the `Schedule` template for this action.

```yaml
schedule-run-local-wf:

   # Validate model that use to parsing exists for template file
   type: Schedule
   workflows:

      # Map existing workflow that want to deploy with scheduler application.
      # It allows you to pass release parameter that dynamic change depend on the
      # current context of this scheduler application releasing that time.
      - name: run-py-local
        params:
          source-extract: "USD-THB"
          asat-dt: "${{ release.logical_date }}"
```

## :cookie: Configuration

The main configuration that use to dynamic changing with your objective of this
application. If any configuration values do not set yet, it will use default value
and do not raise any error to you.

> [!IMPORTANT]
> The config value that you will set on the environment should combine with
> prefix, component, and name which is `WORKFLOW_{component}_{name}` (Upper case).

| Name                         | Component | Default                           | Description                                                                                                        |
|:-----------------------------|:---------:|:----------------------------------|:-------------------------------------------------------------------------------------------------------------------|
| **ROOT_PATH**                |   Core    | `.`                               | The root path of the workflow application.                                                                         |
| **REGISTRY**                 |   Core    | `src`                             | List of importable string for the hook stage.                                                                      |
| **REGISTRY_FILTER**          |   Core    | `ddeutil.workflow.utils`          | List of importable string for the filter template.                                                                 |
| **CONF_PATH**                |   Core    | `conf`                            | The config path that keep all template `.yaml` files.                                                              |
| **TIMEZONE**                 |   Core    | `Asia/Bangkok`                    | A Timezone string value that will pass to `ZoneInfo` object.                                                       |
| **STAGE_DEFAULT_ID**         |   Core    | `true`                            | A flag that enable default stage ID that use for catch an execution output.                                        |
| **STAGE_RAISE_ERROR**        |   Core    | `false`                           | A flag that all stage raise StageException from stage execution.                                                   |
| **JOB_DEFAULT_ID**           |   Core    | `false`                           | A flag that enable default job ID that use for catch an execution output. The ID that use will be sequence number. |
| **JOB_RAISE_ERROR**          |   Core    | `true`                            | A flag that all job raise JobException from job strategy execution.                                                |
| **MAX_NUM_POKING**           |   Core    | `4`                               | .                                                                                                                  |
| **MAX_JOB_PARALLEL**         |   Core    | `2`                               | The maximum job number that able to run parallel in workflow executor.                                             |
| **MAX_JOB_EXEC_TIMEOUT**     |   Core    | `600`                             |                                                                                                                    |
| **MAX_CRON_PER_WORKFLOW**    |   Core    | `5`                               |                                                                                                                    |
| **MAX_QUEUE_COMPLETE_HIST**  |   Core    | `16`                              |                                                                                                                    |
| **GENERATE_ID_SIMPLE_MODE**  |   Core    | `true`                            | A flog that enable generating ID with `md5` algorithm.                                                             |
| **PATH**                     |    Log    | `./logs`                          | The log path of the workflow saving log.                                                                           |
| **DEBUG_MODE**               |    Log    | `true`                            | A flag that enable logging with debug level mode.                                                                  |
| **ENABLE_WRITE**             |    Log    | `true`                            | A flag that enable logging object saving log to its destination.                                                   |
| **MAX_PROCESS**              |    App    | `2`                               | The maximum process worker number that run in scheduler app module.                                                |
| **MAX_SCHEDULE_PER_PROCESS** |    App    | `100`                             | A schedule per process that run parallel.                                                                          |
| **STOP_BOUNDARY_DELTA**      |    App    | `'{"minutes": 5, "seconds": 20}'` | A time delta value that use to stop scheduler app in json string format.                                           |

**API Application**:

| Environment                |  Component  | Default | Description                                                                        |
|:---------------------------|:-----------:|---------|------------------------------------------------------------------------------------|
| **ENABLE_ROUTE_WORKFLOW**  |     API     | `true`  | A flag that enable workflow route to manage execute manually and workflow logging. |
| **ENABLE_ROUTE_SCHEDULE**  |     API     | `true`  | A flag that enable run scheduler.                                                  |

## :rocket: Deployment

This package able to run as an application service for receive manual trigger
from the master node via RestAPI or use to be Scheduler background service
like crontab job but via Python API.

### API Server

```shell
(venv) $ uvicorn src.ddeutil.workflow.api:app \
  --host 127.0.0.1 \
  --port 80 \
  --no-access-log
```

> [!NOTE]
> If this package already deploy, it is able to use multiprocess;
> `uvicorn ddeutil.workflow.api:app --host 127.0.0.1 --port 80 --workers 4`

### Docker Container

Create Docker image;

```shell
$ docker build -t ddeutil-workflow:latest -f .container/Dockerfile .
```

Run the above Docker image;

```shell
$ docker run -i ddeutil-workflow:latest
```

## :speech_balloon: Contribute

I do not think this project will go around the world because it has specific propose,
and you can create by your coding without this project dependency for long term
solution. So, on this time, you can open [the GitHub issue on this project :raised_hands:](https://github.com/ddeutils/ddeutil-workflow/issues)
for fix bug or request new feature if you want it.
