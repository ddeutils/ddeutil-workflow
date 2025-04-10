# Context

This content will explain a context data that passing in and out to execution
process for each workflow model objects such as **Workflow**, **Job**, and **Stage**.

```text
Input       --> {params: {}}
|
Workflow    --> {params: {}, jobs: {<job-id>: {}}}
|
Job         --> {
|                   params: {},
|                   jobs: {
|                       <job-id>: {
|                           strategies: {
|                               <strategy-id>: {metrix: {}, stages: {}}
|                           }
|                       }
|                   },
|                   metrix: {},
|                   stages: {}
|           --> {
|                   params: {},
|                   jobs: {
|                       <job-id>: {stages: {}}
|                   },
|                   metrix: {},
|                   stages: {}
|               }
|
Stage       --> {
                    params: {},
                    jobs: {},
                    metrix: {},
                    stages: {<stage-id>: {outputs: {}, errors: {}, skipped: False}}
                }
```

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
    "class": "",
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


## Stage

A stage context execution that return from `execute` and `handler_execute`
methods can be any custom output with its stage.

```json
{
  "result": 100
}
```

With error;

```json
{
  "errors": {
    "class": "ExceptionClass",
    "name": "class-name",
    "message": "error-message"
  }
}
```

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
      "outputs": {"result": "100"},
      "errors": {
        "class": "ExceptionClass",
        "name": "class-name",
        "message": "error-message"
      }
    }
  }
}
```

!!! note

    The main key from stage setting output method are `outputs` and `errors`.

The template parameter that want to use on stage will can be

- `${{ stages.<stage-id>.outputs.<result> }}`
- `${{ stages.<stage-id>.errors?.name }}`

Job reference if it has any job running finish before.

- `${{ jobs.<job-id>.stages.<stage-id>.outputs.<result> }}`
- `${{ jobs.<job-id>.strategies.<strategy-id>.stages.<stage-id>.errors?.name }}`
