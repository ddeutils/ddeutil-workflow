# Stages

Stages module include all stage model that implemented to be the minimum execution
layer of this workflow core engine. The stage handle the minimize task that run
in a thread (same thread at its job owner) that mean it is the lowest executor that
you can track logs.

The output of stage execution only return SUCCESS or CANCEL status because
I do not want to handle stage error on this stage execution. I think stage model
have a lot of use-case, and it should does not worry about it error output.

So, I will create `handler_execute` for any exception class that raise from
the stage execution method.

```text
Handler     ┬-> Ok      --> Result
            │               |-status: SUCCESS
            │               ╰-context:
            │                   ╰-outputs: ...
            │
            ├-> Ok      --> Result
            │               ╰-status: CANCEL
            │
            ├-> Ok      --> Result
            │               ╰-status: SKIP
            │
            ╰-> Ok      --> Result
                            |-status: FAILED
                            ╰-errors:
                                |-name: ...
                                ╰-message: ...
```

On the context I/O that pass to a stage object at execute process. The
execute method receives a `params={"params": {...}}` value for passing template
searching.

All stages model inherit from `BaseStage` or `AsyncBaseStage` models that has the
base fields:

| field     | alias | data type   | default  | description                                                           |
|-----------|-------|-------------|:--------:|-----------------------------------------------------------------------|
| id        |       | str \| None |  `None`  | A stage ID that use to keep execution output or getting by job owner. |
| name      |       | str         |          | A stage name that want to log when start execution.                   |
| condition | if    | str \| None |  `None`  | A stage condition statement to allow stage executable.                |
| extras    |       | dict        | `dict()` | An extra parameter that override core config values.                  |

It has a special base class is `BaseRetryStage` that inherit from `AsyncBaseStage`
that use to handle retry execution when it got any error with `retry` field.

| field | alias | data type | default | description                                      |
|-------|-------|-----------|:-------:|--------------------------------------------------|
| retry |       | int       |   `0`   | A retry number if stage execution get the error. |

## Methods

- `handler_execution`: This method will be exception handler for the `execute` method.
- `_execution`: Pre-execution method that use to override when that stage want to have pre-execution.
- `execution`: The main execution.
- `set_outputs`
- `get_outputs`
- `is_skipped`
- `gen_id`
- `is_nested`

## Implemented Stage

### Empty Stage

Empty stage executor that do nothing and log the `message` field to
stdout only. It can use for tracking a template parameter on the workflow or
debug step.

You can pass a sleep value in second unit to this stage for waiting
after log message.

!!! example "YAML"

    === "Echo"

        ```yaml
        stages:
          - name: Echo hello world
            echo: "Hello World"
        ```

    === "Echo with ID"

        ```yaml
        stages:
          - name: Echo hello world
            id: echo-stage
            echo: "Hello World"
        ```

    === "Sleep"

        ```yaml
        stages:
          - name: Echo hello world
            id: echo-sleep-stage
            echo: "Hello World and Sleep 10 seconds"
            sleep: 10
        ```

| field | data type   | default | description                                                                                                      |
|-------|-------------|:-------:|------------------------------------------------------------------------------------------------------------------|
| echo  | str \| None | `None`  | A message that want to show on the stdout.                                                                       |
| sleep | float       |   `0`   | A second value to sleep before start execution. This value should gather or equal 0, and less than 1800 seconds. |

### Bash Stage

Bash stage executor that execute bash script on the current OS.
If your current OS is Windows, it will run on the bash from the current WSL.
It will use `bash` for Windows OS and use `sh` for Linux OS.

!!! warning

    This stage has some limitation when it runs shell statement with the
    built-in subprocess package. It does not good enough to use multiline
    statement. Thus, it will write the `.sh` file before start running bash
    command for fix this issue.

!!! example "YAML"

    === "Bash"

        ```yaml
        stages:
            - name: Call echo
              bash: |
                echo "Hello Bash Stage";
        ```

    === "Bash with Env"

        ```yaml
        stages:
            - name: Call echo with env
              env:
                FOO: BAR
              bash: |
                echo "Hello Bash $FOO";
        ```

| field   | data type      | default  | description                                                                                             |
|---------|----------------|:--------:|---------------------------------------------------------------------------------------------------------|
| bash    | str            |          | A bash statement that want to execute via Python subprocess.                                            |
| env     | dict[str, Any] | `dict()` | An environment variables that set before run bash command. It will add on the header of the `.sh` file. |

### Python Stage

Python stage that running the Python statement with the current globals
and passing an input additional variables via `exec` built-in function.

This stage allow you to use any Python object that exists on the globals
such as import your installed package.

!!! warning

    The exec build-in function is very dangerous. So, it should use the `re`
    module to validate exec-string before running or exclude the `os` package
    from the current globals variable.

!!! example "YAML"

    === "Python"

        ```yaml
        stages:
            - name: Call Python Version
              run: |
                import sys
                print(sys.version_info)
        ```

| field | data type      | default  | description                                                                   |
|-------|----------------|:--------:|-------------------------------------------------------------------------------|
| run   | str            |          | A Python string statement that want to run with `exec`.                       |
| vars  | dict[str, Any] | `dict()` | A variable mapping that want to pass to globals parameter in the `exec` func. |

### Call Stage

Call stage executor that call the Python function from registry with tag
decorator function in `reusables` module and run it with input arguments.

This stage is different with PyStage because the PyStage is just run
a Python statement with the `exec` function and pass the current locals and
globals before exec that statement. This stage will import the caller
function can call it with an input arguments. So, you can create your
function complexly that you can for your objective to invoked by this stage
object.

This stage is the most powerful stage of this package for run every
use-case by a custom requirement that you want by creating the Python
function and adding it to the caller registry value by importer syntax like
`module.caller.registry` not path style like `module/caller/registry`.

!!! warning

    The caller registry to get a caller function should importable by the
    current Python execution pointer.

!!! example "YAML"

    === "Call with Args"

        ```yaml
        stages:
            - name: Call call task
              uses: tasks/el-csv-to-parquet@polars
              with:
                source-path: "./data"
                target-path: "./warehouse"
        ```

| field  | alias | data type           | default  | description                                                                                                                                                                 |
|--------|-------|---------------------|:--------:|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| uses   |       | str                 |          | A caller function with registry importer syntax that use to load function before execute step. The caller registry syntax should be `<import.part>/<func-name>@<tag-name>`. |
| args   | with  | dict[str, Any]      | `dict()` | An argument parameter that will pass to this caller function.                                                                                                               |

### Trigger Stage

Trigger workflow executor stage that run an input trigger Workflow
execute method. This is the stage that allow you to create the reusable
Workflow template with dynamic parameters.

!!! example "YAML"

    === "Trigger with Params"

        ```yaml
        stages:
            - name: Call trigger
              trigger: trigger-workflow-name
              params:
                name: some-name
        ```

| field     | data type      | default  | description                                                      |
|-----------|----------------|:--------:|------------------------------------------------------------------|
| trigger   | str            |          | A trigger workflow name that should already exist on the config. |
| params    | dict[str, Any] | `dict()` | A parameter that want to pass to workflow execution.             |


### Parallel Stage

Parallel stage executor that execute branch stages with multithreading.
This stage let you set the fix branches for running child stage inside it on
multithread pool.

!!! note

    This stage is not the low-level stage model because it runs multi-stages
    in this stage execution.

!!! example "YAML"

    === "Parallel"

        ```yaml
        stages:
            - name: Call parallel
              parallel:
                branch-a:
                  - name: Echo in Branch
                    echo: "This is branch: ${{ branch }}"
                branch-b:
                  - name: Echo in Branch
                    echo: "This is branch: ${{ branch }}"
                    sleep: 1
        ```


| field       | alias       | data type              | default | description                                                                                                                      |
|-------------|-------------|------------------------|:-------:|----------------------------------------------------------------------------------------------------------------------------------|
| parallel    |             | dict[str, list[Stage]] |         | A mapping of branch name and its stages.                                                                                         |
| max_workers | max-workers | int                    |   `2`   | The maximum multi-thread pool worker size for execution parallel. This value should be gather or equal than 1, and less than 20. |

### ForEach Stage

For-Each stage executor that execute all stages with each item in the
foreach list.

!!! note

    This stage is not the low-level stage model because it runs
    multi-stages in this stage execution.

| field            | alias | data type                        | default | description |
|------------------|-------|----------------------------------|:-------:|-------------|
| foreach          |       | Union[list[str], list[int], str] |         |             |
| stages           |       | list[Stage]                      | `list`  |             |
| concurrent       |       | int                              |   `1`   |             |
| use_index_as_key |       | bool                             | `False` |             |


### Until Stage

Until stage executor that will run stages in each loop until it valid
with stop loop condition.


!!! note

    This stage is not the low-level stage model because it runs
    multi-stages in this stage execution.

| field    | alias    | data type             | default | description |
|----------|----------|-----------------------|:-------:|-------------|
| item     |          | Union[str, int, bool] |   `0`   |             |
| until    |          | str                   |         |             |
| stages   |          | list[Stage]           | `list`  |             |
| max_loop | max-loop | int                   | `False` |             |

### Case Stage

Case stage executor that execute all stages if the condition was matched.

| field          | alias    | data type   | default | description |
|----------------|----------|-------------|:-------:|-------------|
| case           |          | str         |         |             |
| match          |          | list[Match] |         |             |
| skip_not_match |          | bool        | `False` |             |

!!! note

    When `Match` is the BaseModel for a case.

    | field  | alias    | data type   | default | description |
    |--------|----------|-------------|:-------:|-------------|
    | case   |          | str \| None |         |             |
    | stages |          | list[Stage] |         |             |

### Raise Stage

Raise error stage executor that raise `StageError` that use a message
field for making error message before raise.

| field   | alias | data type   | default | description                                                 |
|---------|-------|-------------|:-------:|-------------------------------------------------------------|
| message | raise | str         |         | An error message that want to raise with `StageError` class |

### Docker Stage

Docker container stage execution that will pull the specific Docker image
with custom authentication and run this image by passing environment
variables and mounting local volume to this Docker container.

The volume path that mount to this Docker container will limit. That is
this stage does not allow you to mount any path to this container.

| field  | alias | data type       | default  | description                                                        |
|--------|-------|-----------------|:--------:|--------------------------------------------------------------------|
| image  |       | str             |          | A Docker image url with tag that want to run.                      |
| tag    |       | str             | `latest` | An Docker image tag.                                               |
| env    |       | dict[str, Any]  |          | An environment variable that want pass to Docker container.        |
| volume |       | dict[str, Any]  |          | A mapping of local and target mounting path.                       |
| auth   |       | dict[str, Any]  |          | An authentication of the Docker registry that use in pulling step. |

### Virtual-Python Stage

Virtual Python stage executor that run Python statement on the dependent
Python virtual environment via the `uv` package.

| field   | data type      | default  | description                                                                   |
|---------|----------------|:--------:|-------------------------------------------------------------------------------|
| run     | str            |          | A Python string statement that want to run with `exec`.                       |
| vars    | dict[str, Any] | `dict()` | A variable mapping that want to pass to globals parameter in the `exec` func. |
| version | str            |  `3.9`   | A Python version that want to run.                                            |
| deps    | list[str]      |          | list of Python dependency that want to install before execution stage.        |
