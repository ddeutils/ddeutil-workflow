# Stage

A stage is the minimum object for this package that use to do a task with it
propose such as the empty stage is doing nothing without printing custom statement
to stdout.

Stage Model that use for getting stage data template from the Job Model.
The stage handle the minimize task that run in some thread (same thread at
its job owner) that mean it is the lowest executor of a workflow that can
tracking logs.

The output of stage execution only return 0 status because I do not want to
handle stage error on this stage model. I think stage model should have a lot of
use-case, and it does not worry when I want to create a new one.

```text
Execution   --> Ok      --> Result with 0

            --> Error   --> Result with 1 (if env var was set)
                        --> Raise StageException(...)
```

On the context I/O that pass to a stage object at execute process. The
execute method receives a `params={"params": {...}}` value for mapping to
template searching.

## Empty Stage

Empty stage that do nothing (context equal empty stage) and logging the name of
stage only to stdout.

!!! example "YAML"

    === "Echo"

        ```yaml
        ...
        stages:
          - name: Echo hello world
            echo: "Hello World"
        ...
        ```

    === "Echo with ID"

        ```yaml
        ...
        stages:
          - name: Echo hello world
            id: echo-stage
            echo: "Hello World"
        ...
        ```

    === "Sleep"

        ```yaml
        ...
        stages:
          - name: Echo hello world
            id: echo-sleep-stage
            echo: "Hello World and Sleep 10 seconds"
            sleep: 10
        ...
        ```

### Fields

| field | data type   | default | description                                     |
|-------|-------------|:-------:|-------------------------------------------------|
| echo  | str \| None | `None`  | A string statement that want to logging         |
| sleep | float       |   `0`   | A second value to sleep before finish execution |

## Bash Stage

Bash execution stage that execute bash script on the current OS.
If your current OS is Windows, it will run on the bash in the WSL.

I get some limitation when I run shell statement with the built-in
subprocess package. It does not good enough to use multiline statement.
Thus, I add writing ``.sh`` file before execution process for fix this
issue.

!!! example "YAML"

    === "Bash"

        ```yaml
        ...
        stages:
            - name: Call echo
              bash: |
                echo "Hello Bash Stage";
        ...
        ```

    === "Bash with Env"

        ```yaml
        ...
        stages:
            - name: Call echo with env
              env:
                FOO: BAR
              bash: |
                echo "Hello Bash $FOO";
        ...
        ```

### Fields

| field   | data type      | default  | description                                                                           |
|---------|----------------|:--------:|---------------------------------------------------------------------------------------|
| bash    | str            |          | A bash statement that want to execute.                                                |
| env     | dict[str, Any] | `dict()` | An environment variable mapping that want to set before execute this shell statement. |

## Python Stage

Python executor stage that running the Python statement with receiving
globals and additional variables.

This stage allow you to use any Python object that exists on the globals
such as import your installed package.

!!! example "YAML"

    === "Python"

        ```yaml
        ...
        stages:
            - name: Call Python
              run: |
                import sys
                print(sys.version_info)
        ...
        ```

### Fields

| field | data type      | default  | description                                                 |
|-------|----------------|:--------:|-------------------------------------------------------------|
| run   | str            |          | A Python string statement that want to run with exec.       |
| vars  | dict[str, Any] |  dict()  | A mapping to variable that want to pass to globals in exec. |

## Hook Stage

Hook executor that hook the Python function from registry with tag
decorator function in ``utils`` module and run it with input arguments.

This stage is different with PyStage because the PyStage is just calling
a Python statement with the ``eval`` and pass that locale before eval that
statement. So, you can create your function complexly that you can for your
objective to invoked by this stage object.

!!! example "YAML"

    === "Hook"

        ```yaml
        ...
        stages:
            - name: Call hook task
              uses: tasks/el-csv-to-parquet@polars
              with:
                source-path: "./data"
                target-path: "./warehouse"
        ...
        ```

### Fields

| field  | alias | data type           | default  | description                                                  |
|--------|-------|---------------------|:--------:|--------------------------------------------------------------|
| uses   |       | str                 |          | A pointer that want to load function from the hook registry. |
| args   | with  | dict[str, Any]      |  dict()  | An arguments that want to pass to the hook function.         |

## Trigger Stage

Trigger Workflow execution stage that execute another workflow. This
the core stage that allow you to create the reusable workflow object or
dynamic parameters workflow for common usecase.

!!! example "YAML"

    === "Trigger"

        ```yaml
        ...
        stages:
            - name: Call trigger
        ...
        ```

### Fields

| field     | data type      | default  | description                                                      |
|-----------|----------------|:--------:|------------------------------------------------------------------|
| trigger   | str            |          | A trigger workflow name that should already exist on the config. |
| params    | dict[str, Any] |  dict()  | A parameter that want to pass to workflow execution.             |
