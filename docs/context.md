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
          "stages": {}
        }
      }
    }
  }
}
```

## Stage

A stage execution context that return from the `handler_execute` method.

```json
{
    "params": {"key": "value"},
    "stages": {
      "<stage-id>": {
        "outputs": {},
        "errors": {
          "class": "",
          "name": "",
          "message": ""
        }
      }
    }
}
```
