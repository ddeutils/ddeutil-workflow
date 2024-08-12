# Manual Execution

## Prerequisite

```shell
pip install ddeutil-workflow
```

Create the first pipeline template:

```yaml
pipe-run-manual:
  type: workflow.pipeline.Pipeline
  jobs:
    ...
```

## Getting Started

### Via CLI

```shell
workflow pipeline exec -p "{\"asat-dt\": \"2024-08-01\"}"
```

### Via Python

```python
from ddeutil.workflow.pipeline import Pipeline

pipe = Pipeline.from_loader('pipe-run-manual').execute(params={
    "asat-dt": "2024-08-01",
})
```

### Via Application

```shell
workflow start -h 127.0.0.1 -p 7070
curl POST http://127.0.0.1:7070/workflow/pipeline/pipe-run-manual/exec/?asat-dt=2024-08-01
```
