# Stage

A stage is the minimum object for this package that use to do a task with it
propose such as the empty stage is do nothing without printing custom statement
to stdout.

## Empty Stage

### Fields

| field | data type   | default | description |
|-------|-------------|:-------:|-------------|
| echo  | str \| None | `None`  |             |
| sleep | float       |   `0`   |             |

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

## Bash Stage

### Fields

| field   | data type      | default  | description                          |
|---------|----------------|:--------:|--------------------------------------|
| bash    | str            |          | The bash statement that want to run. |
| env     | dict[str, Any] | `dict()` |                                      |

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

## Python Stage

### Fields

| field | data type      | default  | description |
|-------|----------------|:--------:|-------------|
| run   | str            |          |             |
| vars  | dict[str, Any] |  dict()  |             |

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

## Hook Stage

### Fields

| field  | data type           | default  | description |
|--------|---------------------|:--------:|-------------|
| uses   | str                 |          |             |
| args   | dict[str, Any]      |  dict()  |             |

!!! example "YAML"

    === "Hook"

        ```yaml
        ...
        stages:
            - name: Call hook task
        ...
        ```

## Trigger Stage

### Fields

| field     | data type      | default  | description |
|-----------|----------------|:--------:|-------------|
| trigger   | str            |          |             |
| params    | dict[str, Any] |  dict()  |             |


!!! example "YAML"

    === "Trigger"

        ```yaml
        ...
        stages:
            - name: Call trigger
        ...
        ```
