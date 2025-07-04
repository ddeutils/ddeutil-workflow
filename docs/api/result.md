# Results

The Results module provides the core data structures for passing and receiving execution context throughout the workflow system. It defines status enumerations and result containers for stage, job, and workflow execution.

## Overview

The result system provides:

- **Status management**: Comprehensive status enumeration for execution states
- **Context containers**: Structured data containers for execution results
- **Hierarchical results**: Support for nested execution contexts
- **Error handling**: Integrated error information and status mapping

## Status Enumeration

### Status

Enumeration of possible execution statuses.

#### Values

| Status | Value | Description |
|--------|-------|-------------|
| `WAIT` | `0` | Execution is waiting to start |
| `SUCCESS` | `1` | Execution completed successfully |
| `FAILED` | `2` | Execution failed with errors |
| `SKIP` | `3` | Execution was skipped |
| `CANCEL` | `4` | Execution was cancelled |

!!! example "Status Usage"

    ```python
    from ddeutil.workflow.result import Status, SUCCESS, FAILED

    # Using enum values
    if result.status == Status.SUCCESS:
        print("Execution successful")

    # Using constants
    if result.status == SUCCESS:
        print("Execution successful")

    # Status comparison
    if result.status >= SUCCESS:
        print("Execution completed")
    ```

## Result Model

### Result

Pydantic model for passing and receiving data context from any module execution process like stage execution, job execution, or workflow execution.

For comparison property, this result will use `status`, `context`, and `run_id` fields to compare with other result instances.

!!! example "Result Creation"

    ```python
    from ddeutil.workflow.result import Result, SUCCESS

    # Create successful result
    result = Result(
        status=SUCCESS,
        context={"output": "data processed"},
        run_id="workflow-123"
    )

    # Create failed result
    failed_result = Result(
        status=FAILED,
        context={"error": "connection timeout"},
        run_id="workflow-124"
    )
    ```

#### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | Status | `WAIT` | Execution status |
| `context` | DictData | `{}` | Execution context data |
| `run_id` | str \| None | `None` | Unique execution identifier |
| `parent_run_id` | str \| None | `None` | Parent execution identifier |

#### Result Context Structure

The `context` field contains structured data that varies based on the execution level:

!!! example "Context Structures"

    === "Workflow Context"

        ```json
        {
          "params": {
            "input_file": "/data/input.csv",
            "output_dir": "/data/output"
          },
          "jobs": {
            "extract": {
              "matrix": {},
              "stages": {
                "download": {"outputs": {"file_count": 100}},
                "validate": {"outputs": {"valid_count": 95}}
              }
            },
            "transform": {
              "matrix": {},
              "stages": {
                "process": {"outputs": {"processed_count": 95}}
              }
            }
          },
          "error": "WorkflowError",
          "error_message": "Job transform failed"
        }
        ```

    === "Job Context"

        ```json
        {
          "matrix-001": {
            "matrix": {"env": "prod", "region": "us-east"},
            "stages": {
              "setup": {"outputs": {"workspace": "/tmp/work"}},
              "process": {"outputs": {"result": "success"}}
            }
          },
          "matrix-002": {
            "matrix": {"env": "prod", "region": "us-west"},
            "stages": {
              "setup": {"outputs": {"workspace": "/tmp/work"}},
              "process": {"outputs": {"result": "success"}}
            }
          }
        }
        ```

    === "Stage Context"

        ```json
        {
          "stages": {
            "data-processing": {
              "outputs": {
                "processed_rows": 1000,
                "error_count": 5
              }
            }
          }
        }
        ```

## Utility Functions

### `get_status_from_error`

Convert exception to appropriate status value.

!!! example "Error to Status"

    ```python
    from ddeutil.workflow.result import get_status_from_error, FAILED, CANCEL

    try:
        # Some operation that might fail
        process_data()
    except Exception as e:
        status = get_status_from_error(e)
        # Returns FAILED for most exceptions
        # Returns CANCEL for cancellation exceptions
    ```

## Usage Examples

### Creating Results

```python
from ddeutil.workflow.result import Result, SUCCESS, FAILED, SKIP

# Successful execution
success_result = Result(
    status=SUCCESS,
    context={
        "outputs": {
            "processed_files": 10,
            "total_size": "1.5MB"
        }
    },
    run_id="job-123"
)

# Failed execution
failed_result = Result(
    status=FAILED,
    context={
        "error": "Connection timeout",
        "error_type": "NetworkError",
        "retry_count": 3
    },
    run_id="job-124"
)

# Skipped execution
skipped_result = Result(
    status=SKIP,
    context={
        "reason": "Condition not met",
        "condition": "params.enable_processing == true"
    },
    run_id="job-125"
)
```

### Result Comparison

```python
from ddeutil.workflow.result import Result, SUCCESS, FAILED

def compare_results(result1: Result, result2: Result) -> bool:
    """Compare two results for equality."""
    return (
        result1.status == result2.status and
        result1.context == result2.context and
        result1.run_id == result2.run_id
    )

# Usage
result1 = Result(status=SUCCESS, context={"data": "value"})
result2 = Result(status=SUCCESS, context={"data": "value"})

are_equal = compare_results(result1, result2)  # True
```

### Error Handling

```python
from ddeutil.workflow.result import Result, get_status_from_error

def safe_execution(func, *args, **kwargs):
    """Execute function with error handling."""
    try:
        output = func(*args, **kwargs)
        return Result(
            status=SUCCESS,
            context={"output": output}
        )
    except Exception as e:
        return Result(
            status=get_status_from_error(e),
            context={
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
```

### Workflow Integration

```python
from ddeutil.workflow.result import Result, SUCCESS, FAILED

class WorkflowExecutor:
    def execute_stage(self, stage, params):
        """Execute a stage and return result."""
        try:
            output = stage.execute(params)
            return Result(
                status=SUCCESS,
                context={"outputs": output},
                run_id=stage.run_id
            )
        except Exception as e:
            return Result(
                status=FAILED,
                context={
                    "error": str(e),
                    "stage_name": stage.name
                },
                run_id=stage.run_id
            )

    def aggregate_results(self, results):
        """Aggregate multiple stage results."""
        if all(r.status == SUCCESS for r in results):
            return Result(
                status=SUCCESS,
                context={"stages": {r.run_id: r.context for r in results}}
            )
        else:
            failed_results = [r for r in results if r.status == FAILED]
            return Result(
                status=FAILED,
                context={
                    "failed_stages": [r.context for r in failed_results]
                }
            )
```

## Best Practices

### 1. Status Management

- Use appropriate status values for different execution states
- Handle all possible status values in your code
- Use status comparison for conditional logic

### 2. Context Structure

- Maintain consistent context structure within your workflows
- Include relevant metadata in context
- Use descriptive keys for context data

### 3. Error Handling

- Always include error information in failed results
- Use `get_status_from_error()` for consistent error mapping
- Preserve error context for debugging

### 4. Result Comparison

- Use the built-in comparison mechanism for result equality
- Consider run_id when comparing results
- Handle None values appropriately

### 5. Performance

- Keep context data minimal for large-scale executions
- Avoid storing large objects in context
- Use appropriate data structures for context
