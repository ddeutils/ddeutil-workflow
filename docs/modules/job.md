# Job

!!! note

    This feature already made 100% coverage.

This job module include Strategy and Job objects.

## Strategy

A strategy is a for-parallel/for-loop generated object that use to control the
job execution.

### Fields

| field        | data type      | default | description                                                                             |
|--------------|----------------|:-------:|-----------------------------------------------------------------------------------------|
| fail_fast    | bool           |  False  |                                                                                         |
| max_parallel | int            |    1    | If this value more than 1, it will use the multithreading feature on the job execution. |
| matrix       | Matrix         | dict()  |                                                                                         |
| include      | MatrixFilter   | list()  |                                                                                         |
| exclude      | MatrixFilter   | list()  |                                                                                         |

## Job

### Fields

| field        | data type    |         default          | description |
|--------------|--------------|:------------------------:|-------------|
| id           | str \| None  |           None           |             |
| desc         | str \| None  |           None           |             |
| runs_on      | str \| None  |           None           |             |
| stages       | list[Stage]  |          list()          |             |
| trigger_rule | TriggerRules | TriggerRules.all_success |             |
| needs        | list[str]    |          list()          |             |
| strategy     | Strategy     |        Strategy()        |             |
