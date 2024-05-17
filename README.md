# Data Utility: _Pipeline_

[![test](https://github.com/korawica/ddeutil-pipe/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/korawica/ddeutil-pipe/actions/workflows/tests.yml)
[![python support version](https://img.shields.io/pypi/pyversions/ddeutil-pipe)](https://pypi.org/project/ddeutil-pipe/)
[![size](https://img.shields.io/github/languages/code-size/korawica/ddeutil-pipe)](https://github.com/korawica/ddeutil-pipe)

**Table of Contents**:

- [Installation](#installation)
- [Getting Started](#getting-started)
  - [Conn](#conn)
  - [Ds](#ds)
  - [Pipe](#pipe)
  - [Scdl](#scdl)

This **Utility Pipeline** object was created for easy to make a simple metadata
driven pipeline that able to **ETL, T, EL, or ELT** by `.yaml` file.

I think we should not create the multiple pipeline per use-case if we able to write
some engines that just change input parameters per use-case instead.

> [!NOTE]
> I inspire the dynamic statement from GitHub action file and all of config file
> from several data orchestration framework.

## Installation

```shell
pip install ddeutil-pipe
```

## Getting Started

The first step, you should start create the connections for in and out of you data
that want to transfer.

### Conn

The connection for worker able to do any thing.

### DS

The thing that worker should to focus on that connection.

### Stage

### Scdl

```yaml
schd_for_node:
    type: 'schedule.BaseSchedule'
    cron: "*/5 * * * *"
```

```python
from ddeutil.pipe.scdl import Scdl

scdl = Scdl('schd_for_node')
scdl.cron
```

```text
>>> '*/5 * * * *'
```

```python
cron_iterate = scdl.generate('2022-01-01 00:00:00')
for _ in range(5):
   cron_iterate.next.strftime('%Y-%m-%d %H:%M:%S')
```

```text
>>> 2022-01-01 00:05:00
>>> 2022-01-01 00:10:00
>>> 2022-01-01 00:15:00
>>> 2022-01-01 00:20:00
>>> 2022-01-01 00:25:00
```

## Examples

### Pipe

The state of doing lists that worker should to do. It be collection of the stage.

## License

This project was licensed under the terms of the [MIT license](LICENSE).
