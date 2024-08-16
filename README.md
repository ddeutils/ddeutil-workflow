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

This **Workflow** objects was created for easy to make a simple metadata
driven for data pipeline orchestration that able to use for **ETL, T, EL, or
ELT** by a `.yaml` file template.

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

## Installation

```shell
pip install ddeutil-workflow
```

This project need `ddeutil-io` extension namespace packages. If you want to install
this package with application add-ons, you should add `app` in installation;

| Usecase            | Install Optional          |
|--------------------|---------------------------|
| Scheduler Service  | `ddeutil-workflow[app]`   |
| FastAPI Server     | `ddeutil-workflow[api]`   |

## Getting Started

The first step, you should start create the connections and datasets for In and
Out of you data that want to use in pipeline of workflow. Some of this component
is similar component of the **Airflow** because I like it orchestration concepts.

The main feature of this project is the `Pipeline` object that can call any
registries function. The pipeline can handle everything that you want to do, it
will passing parameters and catching the output for re-use it to next step.

> [!IMPORTANT]
> In the future of this project, I will drop the connection and dataset to
> dynamic registries instead of main features because it have a lot of maintain
> vendor codes and deps. (I do not have time to handle this features)

### On

The **On** is schedule object.

```yaml
on_every_5_min:
  type: on.On
  cron: "*/5 * * * *"
```

```python
from ddeutil.workflow.on import On

schedule = On.from_loader(name='on_every_5_min', externals={})
assert '*/5 * * * *' == str(schedule.cronjob)

cron_iter = schedule.generate('2022-01-01 00:00:00')
assert '2022-01-01 00:05:00' f"{cron_iter.next:%Y-%m-%d %H:%M:%S}"
assert '2022-01-01 00:10:00' f"{cron_iter.next:%Y-%m-%d %H:%M:%S}"
assert '2022-01-01 00:15:00' f"{cron_iter.next:%Y-%m-%d %H:%M:%S}"
assert '2022-01-01 00:20:00' f"{cron_iter.next:%Y-%m-%d %H:%M:%S}"
```

### Pipeline

The **Pipeline** object that is the core feature of this project.

```yaml
run_py_local:
  type: ddeutil.workflow.pipeline.Pipeline
  on: 'on_every_5_min'
  params:
    author-run:
      type: str
    run-date:
      type: datetime
```

```python
from ddeutil.workflow.pipeline import Pipeline

pipe = Pipeline.from_loader(name='run_py_local', externals={})
pipe.execute(params={'author-run': 'Local Workflow', 'run-date': '2024-01-01'})
```

> [!NOTE]
> The above parameter use short declarative statement. You can pass a parameter
> type to the key of a parameter name.
> ```yaml
> params:
>   author-run: str
>   run-date: datetime
> ```
>
> And for the type, you can remove `ddeutil.workflow` prefix because we can find
> it by looping search from `WORKFLOW_CORE_REGISTRY` value.

## Usage

This is examples that use workflow file for running common Data Engineering
use-case.

> [!IMPORTANT]
> I recommend you to use `task` stage for all actions that you want to do with
> pipeline object.

```yaml
run_py_local:
  type: pipeline.Pipeline
  on:
    - cronjob: '* * * * *'
      timezone: "Asia/Bangkok"
  params:
    author-run: str
    run-date: datetime
  jobs:
    first-job:
      stages:
        - name: "Printing Information"
          id: define-func
          run: |
            x = '${{ params.run-date | fmt("%Y%m%d") }}'
            print(f'Hello at {x}')

            def echo(name: str):
              print(f'Hello {name}')
        - name: "Run Sequence and use var from Above"
          vars:
            x: ${{ params.author-run }}
          run: |
            print(f'Receive x from above with {x}')
            # Change x value
            x: int = 1
        - name: "Call Function"
          vars:
            echo: ${{ stages.define-func.outputs.echo }}
          run: |
            echo('Caller')
    second-job:
      stages:
        - name: "Echo Bash Script"
          id: shell-echo
          bash: |
            echo "Hello World from Shell"
```

```python
from datetime import datetime
from ddeutil.workflow.pipeline import Pipeline

pipe: Pipeline = Pipeline.from_loader(name='run_py_local', externals={})
pipe.execute(params={
    'author-run': 'Local Workflow',
    'run-date': datetime(2024, 1, 1),
})
```

```shell
> Hello at 20240101
> Receive x from above with Local Workflow
> Hello Caller
> Hello World from Shell
```

## Configuration

```bash
export WORKFLOW_ROOT_PATH=.
export WORKFLOW_CORE_REGISTRY=ddeutil.workflow,tests.utils
export WORKFLOW_CORE_REGISTRY_FILTER=ddeutil.workflow.utils
export WORKFLOW_CORE_PATH_CONF=conf
export WORKFLOW_CORE_TIMEZONE=Asia/Bangkok
export WORKFLOW_CORE_DEFAULT_STAGE_ID=true
export WORKFLOW_CORE_MAX_PIPELINE_POKING=4
export WORKFLOW_CORE_MAX_JOB_PARALLEL=2
```

Application config:

```bash
export WORKFLOW_APP_DB_URL=postgresql+asyncpg://user:pass@localhost:5432/schedule
export WORKFLOW_APP_INTERVAL=10
```

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
