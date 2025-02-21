# Result

## Result

The result Pydantic model that use to keep all result from any execution layers.

### Fields

| field          | data type   | default  | description |
|----------------|-------------|:--------:|-------------|
| status         | int         |   `2`    |             |
| context        | DictData    | `dict()` |             |
| run_id         | str \| None |  `None`  |             |
| parent_run_id  | str \| None |  `None`  |             |

!!! note "Result Context"

    === "Workflow"

        ```json
        {
          "params": {},
          "jobs": {
            "<job's ID>": {
              "matrix": {},
              "stages": {
                "<stage's ID>": {"outputs": { ... }},
                "<stage's ID>": {"outputs": { ... }},
              },
            },
            "<job's ID>": {
              "matrix": {},
              "stages": {
                "<stage's ID>": {"outputs": { ... }},
                "<stage's ID>": {"outputs": { ... }},
              },
            },
          },
          "error": <Exception Class>,
          "error_message": "",
        }
        ```

    === "Job"

        ```json
        ```

    === "Stage"

        ```json
        ```
