# Utils

## Params

## Result

!!! note

    The result context from the workflow execution.

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
