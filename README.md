# Data Utility: _Workflow_

[![test](https://github.com/korawica/ddeutil-workflow/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/korawica/ddeutil-workflow/actions/workflows/tests.yml)
[![python support version](https://img.shields.io/pypi/pyversions/ddeutil-workflow)](https://pypi.org/project/ddeutil-workflow/)
[![size](https://img.shields.io/github/languages/code-size/korawica/ddeutil-workflow)](https://github.com/korawica/ddeutil-workflow)

**Table of Contents**:

- [Installation](#installation)
- [Getting Started](#getting-started)
  - [Connection](#conn)
  - [Dataset](#dataset)
  - [Schedule](#schedule)
- [Examples](#examples)
  - [Workflow](#workflow)

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
> I inspire the dynamic statement from GitHub action `.yml` files and all of config
> file from several data orchestration framework.

## Installation

```shell
pip install ddeutil-workflow
```

## Getting Started

The first step, you should start create the connections and datasets for in and
out of you data that want to use in pipeline of workflow.

### Connection

The connection for worker able to do any thing.

```yaml
conn_postgres_data:
  type: conn.Postgres
  url: 'postgres+pysyncopg//...'
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

### Schedule

```yaml
schd_for_node:
  type: schedule.Scdl
  cron: "*/5 * * * *"
```

```python
from ddeutil.workflow.schedule import Scdl

scdl = Scdl.from_loader(name='schd_for_node', ...)
assert '*/5 * * * *' == str(scdl.cronjob)

cron_iterate = scdl.generate('2022-01-01 00:00:00')
assert '2022-01-01 00:05:00' f"{cron_iterate.next:%Y-%m-%d %H:%M:%S}"
assert '2022-01-01 00:10:00' f"{cron_iterate.next:%Y-%m-%d %H:%M:%S}"
assert '2022-01-01 00:15:00' f"{cron_iterate.next:%Y-%m-%d %H:%M:%S}"
assert '2022-01-01 00:20:00' f"{cron_iterate.next:%Y-%m-%d %H:%M:%S}"
assert '2022-01-01 00:25:00' f"{cron_iterate.next:%Y-%m-%d %H:%M:%S}"
```

## Examples

This is examples that use workflow file for running common use-case.

### Running Python Script

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
```

### EL

```yaml

```

### E

```yaml

```

### ETL

```yaml

```

### ELT

```yaml

```

## License

This project was licensed under the terms of the [MIT license](LICENSE).
