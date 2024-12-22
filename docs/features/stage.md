# Stage

!!! note

    This feature already made 100% coverage.

## Empty Stage

```python
from ddeutil.workflow.stage import EmptyStage, Stage
from ddeutil.workflow.utils import Result

stage: Stage = EmptyStage(name="Empty Stage", echo="hello world")
rs: Result = stage.execute(params={})
assert {} == rs.context
```
