# Data Utility: _Workflow_

[![test](https://github.com/ddeutils/ddeutil-workflow/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/ddeutils/ddeutil-workflow/actions/workflows/tests.yml)
[![python support version](https://img.shields.io/pypi/pyversions/ddeutil-workflow)](https://pypi.org/project/ddeutil-workflow/)
[![size](https://img.shields.io/github/languages/code-size/ddeutils/ddeutil-workflow)](https://github.com/ddeutils/ddeutil-workflow)

**Table of Contents**:

- [Installation](#installation)
- [Getting Started](#getting-started)
  - [Connection](#connection)
  - [Dataset](#dataset)
  - [Schedule](#schedule)
- [Examples](#examples)
  - [Python](#python)
  - [Extract & Load](#extract--load)
  - [Transform](#transform)
  - [ETL](#extract--transfrom--load)

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

This project need `ddeutil-io`, `ddeutil-model` extension namespace packages.

## Getting Started

The first step, you should start create the connections and datasets for In and
Out of you data that want to use in pipeline of workflow. Some of this component
is similar component of the **Airflow** because I like it concepts.

### Connection

The connection for worker able to do any thing.

```yaml
conn_postgres_data:
  type: conn.Postgres
  url: 'postgres//username:${ENV_PASS}@hostname:port/database?echo=True&time_out=10'
```

```python
from ddeutil.workflow.conn import Conn

conn = Conn.from_loader(name='conn_postgres_data', params=params, externals={})
assert conn.ping()
```

### Dataset

The dataset is define any objects on the connection.

```yaml
ds_postgres_customer_tbl:
  type: dataset.PostgresTbl
  conn: 'conn_postgres_data'
  features:
    id: serial primary key
    name: varchar( 100 ) not null
```

```python
from ddeutil.workflow.dataset import PostgresTbl

dataset = PostgresTbl.from_loader(name='ds_postgres_customer_tbl', params=params, externals={})
assert dataset.exists()
```

### Schedule

```yaml
schd_for_node:
  type: schedule.Scdl
  cron: "*/5 * * * *"
```

```python
from ddeutil.workflow.schedule import Scdl

scdl = Scdl.from_loader(name='schd_for_node', params=params, externals={})
assert '*/5 * * * *' == str(scdl.cronjob)

cron_iterate = scdl.generate('2022-01-01 00:00:00')
assert '2022-01-01 00:05:00' f"{cron_iterate.next:%Y-%m-%d %H:%M:%S}"
assert '2022-01-01 00:10:00' f"{cron_iterate.next:%Y-%m-%d %H:%M:%S}"
assert '2022-01-01 00:15:00' f"{cron_iterate.next:%Y-%m-%d %H:%M:%S}"
assert '2022-01-01 00:20:00' f"{cron_iterate.next:%Y-%m-%d %H:%M:%S}"
assert '2022-01-01 00:25:00' f"{cron_iterate.next:%Y-%m-%d %H:%M:%S}"
```

## Examples

This is examples that use workflow file for running common Data Engineering
use-case.

### Python

The state of doing lists that worker should to do. It be collection of the stage.

```yaml
run_python_local:
  version: 1
  type: ddeutil.workflow.pipe.Pipeline
  params:
    run_date: utils.receive.datetime
    name: utils.receive.string
  jobs:
    - demo_run:
        stages:
          - name: Run Hello World
            run: |
              print(f'Hello {x}')
          - name: Run Sequence and use var from Above
            run: |
              print(f'Receive x from above with {x}')

              # NOTE: Change x value
              x: int = 1
    - next_run:
        stages:
          - name: Set variable and function
            run: |
              var_inside: str = 'Inside'
              def echo() -> None:
                print(f"Echo {var_inside}")
          - name: Call that variable
            run: |
              echo()
```

```python
from ddeutil.workflow.pipeline import Pipeline

pipe = Pipeline.from_loader(name='run_python_local', ...)
pipe.execute(params={"run_date": "2023-01-01", "name": "foo"})
assert {} == pipe.output
```

### Extract & Load

```yaml
pipe_el_pg_to_lake:
  version: 1
  type: ddeutil.workflow.pipe.Pipeline
  params:
    run_date: utils.receive.datetime
    name: utils.receive.string
  jobs:
    extract-load:
      stages:
        - name: Extract Load from Postgres to Lake
          id: extract
          uses: PostgresToDelta
          with:
            source:
              conn: conn_postgres_url
              query: |
                select * from ${{ params.name }}
                where update_date = '${{ params.datetime }}'
            sink:
              conn: conn_az_lake
              endpoint: /${{ params.name }}/
```

### Transform

```yaml
pipe_hook_mssql_proc:
  version: 1
  type: ddeutil.workflow.pipe.Pipeline
  params:
    run_date: utils.receive.datetime
    sp_name: utils.receive.string
    source_name: utils.receive.string
    target_name: utils.receive.string
  jobs:
    transform:
      stages:
        - name: Transform Data in MS SQL Server
          hook: MssqlProcHook
          with:
            exec: ${{ params.sp_name }}
            params:
              run_mode: T
              run_date: ${{ params.run_date }}
              source: ${{ params.source_name }}
              target: ${{ params.target_name }}
```

### Extract & Transform & Load

```yaml
pipe_etl_postgres:
  version: 1
  type: ddeutil.workflow.pipe.Pipeline
  params:
    run_date: utils.receive.datetime
    sp_name: utils.receive.string
    source_name: utils.receive.string
    target_name: utils.receive.string
  jobs:
    etl:
      run-on: IR-Name
      stages:
        - name: Extract to Polars
          uses: PolarsDb
          id: extract
          with:
            conn: conn_postgres_url
            query: |
              select ...
        - name: Transform
          env:
            df: stages.extract.output.df
          run: |
            import polars as pl

            df = (
              df.withColumn('')
                .withC
                .withC
                .drop(...)
            )
        - name: Load
          users: PolarParq
          with:
            conn: ...
```

## License

This project was licensed under the terms of the [MIT license](LICENSE).
