# Data Utility: _Workflow_

[![test](https://github.com/korawica/ddeutil-pipe/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/korawica/ddeutil-pipe/actions/workflows/tests.yml)
[![python support version](https://img.shields.io/pypi/pyversions/ddeutil-workflow)](https://pypi.org/project/ddeutil-workflow/)
[![size](https://img.shields.io/github/languages/code-size/korawica/ddeutil-pipe)](https://github.com/korawica/ddeutil-pipe)

**Table of Contents**:

- [Installation](#installation)
- [Getting Started](#getting-started)
  - [Conn](#conn)
  - [Dataset](#dataset)
  - [Scdl](#scdl)
- [Examples](#examples)

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

### Conn

The connection for worker able to do any thing.

### Dataset

The thing that worker should to focus on that connection.


### Scdl

```yaml
schd_for_node:
    type: 'scdl.Scdl'
    cron: "*/5 * * * *"
```

```python
from ddeutil.workflow.scdl import Scdl

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

### Pipe

The state of doing lists that worker should to do. It be collection of the stage.

```yaml

```

## License

This project was licensed under the terms of the [MIT license](LICENSE).
