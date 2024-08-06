# Data Utility: _Workflow_

[![test](https://github.com/ddeutils/ddeutil-workflow/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/ddeutils/ddeutil-workflow/actions/workflows/tests.yml)
[![python support version](https://img.shields.io/pypi/pyversions/ddeutil-workflow)](https://pypi.org/project/ddeutil-workflow/)
[![size](https://img.shields.io/github/languages/code-size/ddeutils/ddeutil-workflow)](https://github.com/ddeutils/ddeutil-workflow)
[![gh license](https://img.shields.io/github/license/ddeutils/ddeutil-workflow)](https://github.com/ddeutils/ddeutil-workflow/blob/main/LICENSE)

**Table of Contents**:

- [Installation](#installation)
- [Getting Started](#getting-started)
  - [Schedule](#schedule)
  - [Pipeline](#pipeline)
- [Examples](#examples)
  - [Python & Shell](#python--shell)
  - [Tasks (EL)](#tasks-extract--load)
  - [Hooks (T)](#tasks-transform)
- [Configuration](#configuration)

This **Utility Workflow** objects was created for easy to make a simple metadata
driven pipeline that able to **ETL, T, EL, or ELT** by `.yaml` file.

I think we should not create the multiple pipeline per use-case if we able to
write some dynamic pipeline that just change the input parameters per use-case
instead. This way we can handle a lot of pipelines in our orgs with metadata only.
It called **Metadata Driven**.

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

This project need `ddeutil-io` extension namespace packages.

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

---

### Schedule

```yaml
schd_for_node:
  type: schedule.Schedule
  cron: "*/5 * * * *"
```

```python
from ddeutil.workflow.on import Schedule

scdl = Schedule.from_loader(name='schd_for_node', externals={})
assert '*/5 * * * *' == str(scdl.cronjob)

cron_iterate = scdl.generate('2022-01-01 00:00:00')
assert '2022-01-01 00:05:00' f"{cron_iterate.next:%Y-%m-%d %H:%M:%S}"
assert '2022-01-01 00:10:00' f"{cron_iterate.next:%Y-%m-%d %H:%M:%S}"
assert '2022-01-01 00:15:00' f"{cron_iterate.next:%Y-%m-%d %H:%M:%S}"
assert '2022-01-01 00:20:00' f"{cron_iterate.next:%Y-%m-%d %H:%M:%S}"
assert '2022-01-01 00:25:00' f"{cron_iterate.next:%Y-%m-%d %H:%M:%S}"
```

---

### Pipeline

```yaml
run_py_local:
  type: ddeutil.workflow.pipeline.Pipeline
  ...
```

```python
from ddeutil.workflow.pipeline import Pipeline

pipe = Pipeline.from_loader(name='run_py_local', externals={})
pipe.execute(params={'author-run': 'Local Workflow', 'run-date': '2024-01-01'})
```

## Examples

This is examples that use workflow file for running common Data Engineering
use-case.

### Python & Shell

The state of doing lists that worker should to do. It be collection of the stage.

```yaml
run_py_local:
  type: ddeutil.workflow.pipeline.Pipeline
  params:
    author-run:
      type: str
    run-date:
      type: datetime
  jobs:
    first-job:
      stages:
        - name: Printing Information
          id: define-func
          run: |
            x = '${{ params.author-run }}'
            print(f'Hello {x}')

            def echo(name: str):
              print(f'Hello {name}')

        - name: Run Sequence and use var from Above
          vars:
            x: ${{ params.author-run }}
          run: |
            print(f'Receive x from above with {x}')
            # Change x value
            x: int = 1

        - name: Call Function
          vars:
            echo: ${{ stages.define-func.outputs.echo }}
          run: |
            echo('Caller')
    second-job:
      stages:
        - name: Echo Shell Script
          id: shell-echo
          shell: |
            echo "Hello World from Shell"
```

```python
from ddeutil.workflow.pipeline import Pipeline

pipe = Pipeline.from_loader(name='run_py_local', externals={})
pipe.execute(params={'author-run': 'Local Workflow', 'run-date': '2024-01-01'})
```

```shell
> Hello Local Workflow
> Receive x from above with Local Workflow
> Hello Caller
> Hello World from Shell
```

---

### Tasks (Extract & Load)

```yaml
pipe_el_pg_to_lake:
  type: ddeutil.workflow.pipeline.Pipeline
  params:
    run-date:
      type: datetime
    author-email:
      type: str
  jobs:
    extract-load:
      stages:
        - name: "Extract Load from Postgres to Lake"
          id: extract-load
          task: tasks/postgres-to-delta@polars
          with:
            source:
              conn: conn_postgres_url
              query: |
                select * from ${{ params.name }}
                where update_date = '${{ params.datetime }}'
            sink:
              conn: conn_az_lake
              endpoint: "/${{ params.name }}"
```

---

### Tasks (Transform)

> I recommend you to use task for all actions that you want to do.

```yaml
pipe_hook_mssql_proc:
  type: ddeutil.workflow.pipeline.Pipeline
  params:
    run_date: datetime
    sp_name: str
    source_name: str
    target_name: str
  jobs:
    transform:
      stages:
        - name: "Transform Data in MS SQL Server"
          id: transform
          task: tasks/mssql-proc@odbc
          with:
            exec: ${{ params.sp_name }}
            params:
              run_mode: "T"
              run_date: ${{ params.run_date }}
              source: ${{ params.source_name }}
              target: ${{ params.target_name }}
```

> [!NOTE]
> The above parameter use short declarative statement. You can pass a parameter
> type to the key of a parameter name.

## Configuration

the `workflows-conf.yaml` file:

```yaml
engine:
  registry:
    - "ddeutil.workflow"
    - "tests.utils"
  paths:
    conf: "${ROOT_PATH:.}/tests/data/conf"
    root: "${ROOT_PATH:.}"
```

**Environment variables**:

```text
DDE_WORKFLOW_ENGIN_REGISTRY=ddeutil.workflow,tests.utils
DDE_WORKFLOW_ENGIN_PATH_CONF=
DDE_WORKFLOW_ENGIN_PATH_ROOT=
```
