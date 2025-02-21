# Scheduler

## ScheduleWorkflow

Schedule Workflow Pydantic model that use to keep workflow model for
the Schedule model. it should not use Workflow model directly because on the
schedule config it can adjust crontab value that different from the Workflow
model.

### Fields

| field  | alias  | data type      | default  | description                                                                       |
|--------|--------|----------------|:--------:|-----------------------------------------------------------------------------------|
| alias  |        | str \| None    |  `None`  | An alias name of workflow that use for schedule model.                            |
| name   |        | str            |          | A workflow name.                                                                  |
| on     |        | list[On]       | `list()` | An override the list of On object values.                                         |
| values | params | dict[str, Any] | `dict()` | A value that want to pass to the workflow parameters when calling release method. |

## Schedule

Schedule Pydantic model that use to run with any scheduler package.

It does not equal the on value in Workflow model, but it uses same logic to
running release date with crontab interval.

### Fields

| field     | data type               |  default  | description                                                    |
|-----------|-------------------------|:---------:|----------------------------------------------------------------|
| desc      | str \| None             |  `None`   | A schedule description that can be string of markdown content. |
| workflows | list[ScheduleWorkflow]  | `list()`  | A list of ScheduleWorkflow models.                             |
