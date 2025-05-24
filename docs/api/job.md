# Job

Job model that use for store Stage models and node parameter that use for
running these stages. The job model handle the lineage of stages and location of
execution that mean you can define `runs-on` field with the Self-Hosted mode
for execute on target machine instead of the current local machine.

This module include Strategy model that use on the job `strategy` field for
making matrix values before execution parallelism stage execution.

The Job model does not implement `handler_execute` same as Stage model
because the job should raise only `JobError` class from the execution
method.

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

Job Pydantic model object (short description: **a group of stages**).

This job model allow you to use for-loop that call matrix strategy. If
you pass matrix mapping, and it is able to generate, you will see it running
with loop of matrix values.

!!! example "YAML"

    === "Job"

        ```yaml
        jobs:
          first-job:
            stages:
              - name: Start Import
                echo: "Start Import data to raw zone."

              - name: Start Transform
                echo: "Start Transform data from ra to in-memory."

              - name: Start Load
                echo: "Start Load data to bronze zone."
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

ALL_SUCCESS = "all_success"
ALL_FAILED = "all_failed"
ALL_DONE = "all_done"
ONE_FAILED = "one_failed"
ONE_SUCCESS = "one_success"
NONE_FAILED = "none_failed"
NONE_SKIPPED = "none_skipped"

## RunsOn

Runs-On enum object.

LOCAL = "local"
SELF_HOSTED = "self_hosted"
AZ_BATCH = "azure_batch"
DOCKER = "docker"
