# Data Utility: _Workflow_

[![test](https://github.com/korawica/ddeutil-pipe/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/korawica/ddeutil-pipe/actions/workflows/tests.yml)
[![python support version](https://img.shields.io/pypi/pyversions/ddeutil-workflow)](https://pypi.org/project/ddeutil-workflow/)
[![size](https://img.shields.io/github/languages/code-size/korawica/ddeutil-pipe)](https://github.com/korawica/ddeutil-pipe)

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

I think we should not create the multiple pipeline per use-case if we able to write
some engines that just change input parameters per use-case instead.

> [!NOTE]
> I inspire the dynamic statement from GitHub action `.yml` files and all of config
> file from several data orchestration framework.

## Installation

```shell
pip install ddeutil-workflow
```

## Getting Started

The first step, you should start create the connections for in and out of you data
that want to transfer.

### Connection

The connection for worker able to do any thing.

### Dataset

The thing that worker should to focus on that connection.


### Schedule

```yaml
schd_for_node:
    type: 'scdl.Scdl'
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

### Workflow

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
from ddeutil.workflow.pipe import Pipeline

pipe = Pipeline.from_loader(name='run_python_local', ...)
pipe.execute(params={"run_date": "2023-01-01", "name": "foo"})
```

## License

This project was licensed under the terms of the [MIT license](LICENSE).
