# Stage

!!! note

    This feature already made 100% coverage.

A stage is the minimum object for this package that use to do a task with it
propose such as the empty stage is do nothing without printing custom statement
to stdout.

## Empty Stage

## Fields

| field | data type   | default | description |
|-------|-------------|---------|-------------|
| echo  | str \| None | None    |             |
| sleep | float       | 0       |             |

```python
from ddeutil.workflow.stage import EmptyStage, Stage
from ddeutil.workflow.utils import Result

stage: Stage = EmptyStage(name="Empty Stage", echo="hello world")
rs: Result = stage.execute(params={})
assert {} == rs.context
```

## Bash Stage

## Python Stage

## Hook Stage

## Trigger Stage
