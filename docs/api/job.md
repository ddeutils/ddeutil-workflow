# Job

Job Model that use for keeping stages and node that running its stages.
The job handle the lineage of stages and location of execution of stages that
mean the job model able to define `runs-on` key that allow you to run this
job.

This module include Strategy Model that use on the job strategy field.

## Strategy

A strategy is a for-parallel/for-loop generated object that use to control the
job execution.

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

| field        | data type   |       default       | alias | description |
|--------------|-------------|:-------------------:|-------|-------------|
| id           | str \| None |       `None`        |       |             |
| desc         | str \| None |       `None`        |       |             |
| runs_on      | str \| None |       `None`        |       |             |
| condition    |             |       `None`        | if    |             |
| stages       | list[Stage] |      `list()`       |       |             |
| trigger_rule | Rule        | `Rule.all_success`  |       |             |
| needs        | list[str]   |      `list()`       |       |             |
| strategy     | Strategy    |    `Strategy()`     |       |             |


## Rule

Trigger rules enum object.

## RunsOn

Runs-On enum object.
