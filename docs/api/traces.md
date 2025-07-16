# Traces

The Traces module provides logging and trace management for workflow execution,
including stdout, stderr capture, and persistent logging capabilities.

## Overview

The traces system provides:

- **Console output Handler**: Real-time stdout/stderr logging
- **File-based Handler**: Persistent logging to local filesystem
- **SQLite Handler**: Database-backed logging for scalable deployments

## Base Classes

### `BaseTrace`

Abstract base class for all trace implementations.

!!! info "Key Features"
    - Structured logging with levels (DEBUG, INFO, WARNING, ERROR)
    - Context-aware messages with run ID tracking
    - Parent-child relationship support for nested workflows

### `ConsoleTrace`

Basic console logging implementation that outputs to stdout/stderr.

!!! example "Console Trace"

    ```python
    from ddeutil.workflow.traces import ConsoleTrace

    trace = ConsoleTrace(run_id="workflow-123")
    trace.info("Starting workflow execution")
    trace.debug("Processing job dependencies")
    trace.error("Job failed: connection timeout")
    ```

## File-based Handler

### `FileTrace`

File-based trace implementation that persists logs to the local filesystem.

!!! example "File Trace Usage"

    ```python
    from ddeutil.workflow.traces import FileTrace

    # Create file trace
    trace = FileTrace(
        run_id="workflow-123",
        parent_run_id="parent-456"
    )

    # Log messages
    trace.info("Workflow started")
    trace.warning("Retrying failed operation")

    # Messages are automatically saved to:
    # {trace_url}/run_id=workflow-123/
    ```

#### Finding Traces

The `FileTrace` class provides utilities to search and retrieve trace logs.

!!! example "Trace Discovery"

    ```python
    from ddeutil.workflow.traces import FileTrace
    from pathlib import Path

    # Find all traces in default path
    for trace_data in FileTrace.find_traces():
        print(f"Run ID: {trace_data.run_id}")
        print(f"Stdout: {trace_data.stdout}")
        print(f"Stderr: {trace_data.stderr}")

    # Find specific trace by run ID
    trace_data = FileTrace.find_trace_with_id("workflow-123")
    print(trace_data.meta.update)  # Last update timestamp
    ```

#### Trace File Structure

```
traces/
├── run_id=workflow-123/
│   ├── stdout.log
│   ├── stderr.log
│   └── meta.json
└── run_id=workflow-456/
    ├── stdout.log
    ├── stderr.log
    └── meta.json
```

## Database Traces

### `SQLiteTrace`

SQLite-based trace implementation for scalable logging.

!!! example "SQLite Trace"

    ```python
    from ddeutil.workflow.traces import SQLiteTrace

    # Uses SQLite database for trace storage
    trace = SQLiteTrace(run_id="workflow-789")
    trace.info("Database trace initialized")

    # Traces are stored in SQLite with schema:
    # - run_id (int, primary key)
    # - stdout (str)
    # - stderr (str)
    # - update (datetime)
    ```

## Trace Data Models

### `TraceMeta`

Metadata information for trace logs.

| Field           | Type        | Description             |
|-----------------|-------------|-------------------------|
| `run_id`        | str         | Unique run identifier   |
| `parent_run_id` | str \| None | Parent workflow run ID  |
| `update`        | datetime    | Last update timestamp   |

### `TraceData`

Complete trace data including stdout, stderr, and metadata.

| Field    | Type        | Description             |
|----------|-------------|-------------------------|
| `run_id` | str         | Unique run identifier   |
| `stdout` | str         | Standard output content |
| `stderr` | str         | Standard error content  |
| `meta`   | TraceMeta   | Trace metadata          |

!!! example "Trace Data"

    ```python
    from ddeutil.workflow.traces import TraceData
    from pathlib import Path

    # Load trace from file path
    trace_data = TraceData.from_path(Path("traces/run_id=123"))

    print(f"Run ID: {trace_data.run_id}")
    print(f"Output: {trace_data.stdout}")
    print(f"Errors: {trace_data.stderr}")
    print(f"Updated: {trace_data.meta.update}")
    ```

## Trace Factory

### `get_trace`

Factory function that returns the appropriate trace implementation based on configuration.

!!! example "Dynamic Trace Creation"

    ```python
    from ddeutil.workflow.traces import get_trace

    # Automatically selects FileTrace or SQLiteTrace based on config
    trace = get_trace(
        run_id="workflow-123",
        parent_run_id="parent-456"
    )

    # Configuration determines trace type:
    # - If trace_url points to file: SQLiteTrace
    # - If trace_url points to directory: FileTrace
    ```

## Logging Integration

### Message Formatting

All trace implementations support structured message formatting:

!!! example "Message Formats"

    ```python
    trace = FileTrace(run_id="test-123")

    # Standard messages
    trace.info("Processing started")
    # Output: [INFO] (test-123) Processing started

    # With context
    trace.warning("Job timeout", extra={"job_id": "job-456"})
    # Output: [WARNING] (test-123) Job timeout (job_id=job-456)

    # Error with exception
    try:
        raise ValueError("Invalid input")
    except Exception as e:
        trace.error("Operation failed", exc_info=True)
    ```

### Async Support

Trace implementations support asynchronous logging for non-blocking operations:

!!! example "Async Logging"

    ```python
    import asyncio

    async def async_workflow():
        trace = get_trace("async-workflow-123")

        await trace.ainfo("Async workflow started")
        # Non-blocking log writing

        await trace.aerror("Async operation failed")

    asyncio.run(async_workflow())
    ```

## Configuration

Trace behavior is controlled by environment variables:

| Variable                     | Default           | Description                  |
|------------------------------|-------------------|------------------------------|
| `WORKFLOW_CORE_TRACE_PATH`   | `./logs/traces`   | Path for trace file storage  |
| `WORKFLOW_CORE_TRACE_LEVEL`  | `INFO`            | Minimum logging level        |
| `WORKFLOW_CORE_TRACE_FORMAT` | Custom            | Log message format template  |

!!! tip "Performance Considerations"

    - **FileTrace**: Best for development and small-scale deployments
    - **SQLiteTrace**: Recommended for production with concurrent access
    - **ConsoleTrace**: Ideal for debugging and testing

    Choose the appropriate trace implementation based on your deployment scale and persistence requirements.
