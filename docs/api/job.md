# Job

This job module include Strategy and Job objects.

## Strategy

A strategy is a for-parallel/for-loop generated object that use to control the
job execution.

### Fields

| field        | data type      | default  | description                                                                             |
|--------------|----------------|:--------:|-----------------------------------------------------------------------------------------|
| fail_fast    | bool           | `False`  |                                                                                         |
| max_parallel | int            |   `1`    | If this value more than 1, it will use the multithreading feature on the job execution. |
| matrix       | Matrix         | `dict()` |                                                                                         |
| include      | MatrixFilter   | `list()` |                                                                                         |
| exclude      | MatrixFilter   | `list()` |                                                                                         |

## Job

!!! example "YAML"

    === "Job"

        ```yaml
        ```

    === "Job Matrix"

        ```yaml
        ...
        jobs:
          multiple-system:
            strategy:
              max-parallel: 4
              fail-fast: true
              matrix:
                table: [ 'customer', 'sales' ]
                system: [ 'csv' ]
                partition: [ 1, 2, 3 ]
              exclude:
                - table: customer
                  system: csv
                  partition: 1
                - table: sales
                  partition: 3
              include:
                - table: customer
                  system: csv
                  partition: 4
            stages:
              - name: Extract & Load Multi-System
                run: |
                  if ${{ matrix.partition }} == 1:
                    raise ValueError('Value of partition matrix was equaled 1.')
        ...
        ```

### Fields

| field        | data type    |          default           | alias | description |
|--------------|--------------|:--------------------------:|-------|-------------|
| id           | str \| None  |           `None`           |       |             |
| desc         | str \| None  |           `None`           |       |             |
| runs_on      | str \| None  |           `None`           |       |             |
| condition    |              |           `None`           | if    |             |
| stages       | list[Stage]  |          `list()`          |       |             |
| trigger_rule | TriggerRules | `TriggerRules.all_success` |       |             |
| needs        | list[str]    |          `list()`          |       |             |
| strategy     | Strategy     |        `Strategy()`        |       |             |


## TriggerRule

## TriggerState
