# Job

This job module include Strategy and Job objects.

## Strategy

### Fields

| field        | data type      | default | description |
|--------------|----------------|---------|-------------|
| fail_fast    | bool           | False   |             |
| max_parallel | int            | 1       |             |
| matrix       | Matrix         | dict()  |             |
| include      | MatrixFilter   | list()  |             |
| exclude      | MatrixFilter   | list()  |             |

## Job

### Fields

| field        | data type    | default                  | description |
|--------------|--------------|--------------------------|-------------|
| id           | str \| None  | None                     |             |
| desc         | str \| None  | None                     |             |
| runs_on      | str \| None  | None                     |             |
| stages       | list[Stage]  | list()                   |             |
| trigger_rule | TriggerRules | TriggerRules.all_success |             |
| needs        | list[str]    | list()                   |             |
| strategy     | Strategy     | Strategy()               |             |
