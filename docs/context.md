# Context

This content will explain a context data that passing in and out to execution
process for each workflow model objects such as **Workflow**, **Job**, and **Stage**.

```text
Input       --> {params: {}}
|
Workflow    --> {params: {}, jobs: {<job-id>: {}}}
|
Job         --> {
|                   status: SUCCESS,
|                   params: {},
|                   jobs: {
|                       <job-id>: {
|                           status: SUCCESS,
|                           strategies: {
|                               <strategy-id>: {metrix: {}, stages: {}}
|                           },
|                           errors: {
|                               <strategy-id>: {}
|                           }
|                       }
|                   },
|                   metrix: {},
|                   stages: {}
|           --> {
|                   status: SUCCESS,
|                   params: {},
|                   jobs: {
|                       <job-id>: {stages: {}, errors: {}, status: SUCCESS}
|                   },
|                   metrix: {},
|                   stages: {}
|               }
|
Stage       --> {
                    params: {},
                    jobs: {},
                    metrix: {},
                    stages: {<stage-id>: {outputs: {}, errors: {}, status: SUCCESS}}
                }
```

## Stage

A stage context is the minimum standard context for this package. I will explain
context execution that return from `execute` and `handler_execute`
methods can be any custom output with its stage.

### Input Template Params

The template parameter that want to use on stage will can be

- `${{ stages.<stage-id>.outputs.<result> }}`
- `${{ stages.<stage-id>.errors?.name }}`

Job reference if it has any job running finish before.

- `${{ jobs.<job-id>.stages.<stage-id>.outputs.<result> }}`
- `${{ jobs.<job-id>.strategies.<strategy-id>.stages.<stage-id>.errors?.name }}`

### Execution Output

The result from execution method should be.

=== "SUCCESS"

    ```python
    {
      "result": 100
    }
    ```

=== "FAILED/CANCEL"

    ```python
    {
      "errors": {
        "name": "error-class-name",
        "message": "error-message"
      }
    }
    ```

For nested stage, it can return skipped output with `SUCCESS` status,
but it will keep in nested-stage ID instead parent output.

```python
{
    "stages": {
        "<stage-ID>": {
            "status": SKIP,
        }
    }
}
```

!!! note

    This step can raise any error by custom excution. It does not raise only
    `StageExcepton`.

### Set Output

A context that return from `set_outputs` method.

if a `to` argument that pass to this method be;

```json
{
  "params": {"key":  "value"}
}
```

it will return result be;

```json
{
  "params": {"key": "value"},
  "stages": {
    "<stage-id>": {
      "status": "0",
      "outputs": {"result": "100"},
      "errors": {
        "name": "class-name",
        "message": "error-message"
      }
    }
  }
}
```

!!! note

    The main key from stage setting output method are `outputs` and `errors`.

## Workflow

A workflow execution context that return from the `execute` method.

### Execution

For the fist context values that passing to the workflow execution method:

```json
{
  "params": {"key": "value"},
  "jobs": {
    "<job-name>": {},
    "<job-name-02>": {}
  },
  "errors": {
    "name": "",
    "message": ""
  }
}
```

The `params` is the values from the parameterize method that already validated
typing.

## Job

A job execution context that return from the `execute` method.

### Execution

```json
{
  "params": {},
  "jobs": {
    "<job-name>": {
      "strategies": {
        "<strategy-id>": {
          "matrix": {},
          "stages": {
            "<stage-id>": {}
          }
        }
      }
    }
  }
}
```

If the job does not set strategy matrix;

```json
{
  "params": {},
  "jobs": {
    "<job-name>": {
      "stages": {
        "<stage-id>": {}
      }
    }
  }
}
```
