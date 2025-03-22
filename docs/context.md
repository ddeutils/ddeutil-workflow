# Context

This content will explain a context data that passing in and out to execution
process for each workflow model objects such as **Workflow**, **Job**, and **Stage**.

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

A stage execution context that return from `execute` and `handler_execute`
methods.

```json
{
  "out": "result"
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
        "outputs": {
          "out": "result"
        },
        "errors": {
          "class": "",
          "name": "",
          "message": ""
        }
      }
    }
}
```

!!! note

    The main key from stage setting output method are
    `outputs` and `errors`.
