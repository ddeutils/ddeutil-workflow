# Result

## Status

## Result

Result Pydantic Model for passing and receiving data context from any
module execution process like stage execution, job execution, or workflow
execution.

For comparison property, this result will use ``status``, ``context``, and
``_run_id`` fields to comparing with other result instance.

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
          "error_message": "<error-message>",
        }
        ```

    === "Job"

        ```json
        {
          "<strategy's ID>": {
            "matrix": {"<matrix's key>": "<matrix's value>", ...},
            "stages": {"<stage's ID>": {"outputs": {"result": "fast-success"}}},
          },
          "<strategy's ID>": {
            "matrix": {"<matrix's key>": "<matrix's value>", ...},
            "stages": {"<stage's ID>": {"outputs": {"result": "fast-success"}}},
          },
          ...
        }
        ```

    === "Stage"

        ```json
        {
          "stages": {
            "<stage's ID>": {
              "outputs": {
                "error": <Exception Class>,
                "error_message": "<error-message>",
              },
            },
          },
        }
        ```

### Fields

| field          | data type   |    default    | description |
|----------------|-------------|:-------------:|-------------|
| status         | int         | `Status.WAIT` |             |
| context        | DictData    |   `dict()`    |             |
| run_id         | str \| None |    `None`     |             |
| parent_run_id  | str \| None |    `None`     |             |
