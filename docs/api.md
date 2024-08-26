# API Documents

## Cron

## On

The **On** is schedule object that receive crontab value and able to generate
datetime value with next or previous with any start point of an input datetime.

```yaml
# This file should keep under this path: `./root-path/conf-path/*`
on_every_5_min:
  type: on.On
  cron: "*/5 * * * *"
```

```python
from ddeutil.workflow.on import On

# NOTE: Start load the on data from `.yaml` template file with this key.
schedule = On.from_loader(name='on_every_5_min', externals={})

assert '*/5 * * * *' == str(schedule.cronjob)

cron_iter = schedule.generate('2022-01-01 00:00:00')

assert "2022-01-01 00:05:00" f"{cron_iter.next:%Y-%m-%d %H:%M:%S}"
assert "2022-01-01 00:10:00" f"{cron_iter.next:%Y-%m-%d %H:%M:%S}"
assert "2022-01-01 00:15:00" f"{cron_iter.next:%Y-%m-%d %H:%M:%S}"
```

## Stage

## Strategy

## Job

## Pipeline

The **Pipeline** object that is the core feature of this project.

```yaml
# This file should keep under this path: `./root-path/conf-path/*`
pipeline-name:
  type: ddeutil.workflow.pipeline.Pipeline
  on: 'on_every_5_min'
  params:
    author-run:
      type: str
    run-date:
      type: datetime
  jobs:
    first-job:
      stages:
        - name: "Empty stage do logging to console only!!"
```

```python
from ddeutil.workflow.pipeline import Pipeline

pipe = Pipeline.from_loader(name='pipeline-name', externals={})
pipe.execute(params={'author-run': 'Local Workflow', 'run-date': '2024-01-01'})
```

> [!NOTE]
> The above parameter can use short declarative statement. You can pass a parameter
> type to the key of a parameter name but it does not handler default value if you
> run this pipeline workflow with schedule.
>
> ```yaml
> ...
> params:
>   author-run: str
>   run-date: datetime
> ...
> ```
>
> And for the type, you can remove `ddeutil.workflow` prefix because we can find
> it by looping search from `WORKFLOW_CORE_REGISTRY` value.

## Schedule
