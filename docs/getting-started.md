# Getting Started

This execution usecase is getting data from external API and prepare that data
and aggregate it into daily layer to silver data zone.

## Prerequisite

I will use only core package of the workflow because I will run with manual
action.

```shell
pip install ddeutil-workflow
```

Create the first pipeline template:

```yaml
wf-run-manual:
  type: Workflow
  jobs:
    stage-to-curated:
      stages:
        - name: "Extract data from external API"
          uses: tasks/https-external@httpx
          with:
            url: "https://"
            auth: "http_conn_id"
```

## Getting Started

That has ...

### Via Python

```python
from ddeutil.workflow import Workflow
from ddeutil.workflow.result import Result

result: Result = (
    Workflow
    .from_loader('pipe-run-manual')
    .execute(params={"asat-dt": "2024-08-01"})
)
```

### Via Application

```shell
workflow start -h 127.0.0.1 -p 7070
curl POST http://127.0.0.1:7070/workflow/pipeline/pipe-run-manual/exec/?asat-dt=2024-08-01
```
