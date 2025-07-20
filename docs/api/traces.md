# Traces

The Traces module provides comprehensive tracing and logging capabilities for workflow execution monitoring. It supports multiple trace backends including console output, file-based logging, SQLite database storage, REST API integration, and Elasticsearch.

## Overview

The traces system provides:

- **Console Handler**: Real-time stdout/stderr logging
- **File Handler**: Persistent logging to local filesystem with structured metadata
- **SQLite Handler**: Database-backed logging for scalable deployments
- **REST API Handler**: Integration with external logging services (Datadog, Grafana, CloudWatch)
- **Elasticsearch Handler**: High-performance distributed logging with search capabilities

## Core Components

### `Trace`

The main trace manager that coordinates multiple handlers and provides a unified logging interface.

!!! example "Basic Usage"

    ```python
    from ddeutil.workflow.traces import get_trace

    # Get trace manager with default handlers
    trace = get_trace(run_id="workflow-123")

    # Log messages
    trace.info("Workflow started")
    trace.debug("Processing stage dependencies")
    trace.warning("Retrying failed operation")
    trace.error("Job failed: connection timeout")
    trace.exception("Critical error occurred")
    ```

### `Metadata`

Comprehensive metadata model capturing execution context, performance metrics, and distributed tracing information.

!!! example "Metadata Fields"

    ```python
    from ddeutil.workflow.traces import Metadata

    # Metadata includes:
    # - Basic info: run_id, parent_run_id, level, message, datetime
    # - System info: process, thread, filename, lineno, cut_id
    # - Observability: workflow_name, stage_name, job_name
    # - Performance: duration_ms, memory_usage_mb, cpu_usage_percent
    # - Distributed tracing: trace_id, span_id, parent_span_id
    # - Error context: exception_type, exception_message, stack_trace
    # - Business context: user_id, tenant_id, environment
    # - System context: hostname, ip_address, python_version
    # - Custom: tags, metadata
    ```

## Handlers

### `ConsoleHandler`

Basic console logging implementation that outputs to stdout/stderr.

!!! example "Console Handler"

    ```python
    from ddeutil.workflow.traces import ConsoleHandler, Trace

    handler = ConsoleHandler(type="console")
    trace = Trace(
        run_id="workflow-123",
        handlers=[handler]
    )
    trace.info("Console logging initialized")
    ```

### `FileHandler`

File-based trace implementation that persists logs to the local filesystem with structured metadata.

!!! example "File Handler Usage"

    ```python
    from ddeutil.workflow.traces import FileHandler, Trace

    # Create file handler
    handler = FileHandler(
        type="file",
        path="./logs/traces",
        format="{datetime} ({process:5d}, {thread:5d}) ({cut_id}) {message:120s} ({filename}:{lineno})"
    )

    trace = Trace(
        run_id="workflow-123",
        parent_run_id="parent-456",
        handlers=[handler]
    )

    # Log messages
    trace.info("Workflow started")
    trace.warning("Retrying failed operation")

    # Messages are automatically saved to:
    # ./logs/traces/run_id=workflow-123/
    #   ├── stdout.txt
    #   ├── stderr.txt
    #   └── metadata.txt
    ```

#### Finding Traces

The `FileHandler` class provides utilities to search and retrieve trace logs.

!!! example "Trace Discovery"

    ```python
    from ddeutil.workflow.traces import FileHandler
    from pathlib import Path

    handler = FileHandler(type="file", path="./logs/traces")

    # Find all traces
    for trace_data in handler.find_traces():
        print(f"Run ID: {trace_data.meta[0].run_id if trace_data.meta else 'Unknown'}")
        print(f"Stdout: {trace_data.stdout}")
        print(f"Stderr: {trace_data.stderr}")

    # Find specific trace by run ID
    trace_data = handler.find_trace_with_id("workflow-123")
    print(f"Metadata entries: {len(trace_data.meta)}")
    ```

### `SQLiteHandler`

SQLite-based trace implementation for scalable logging with structured metadata storage.

!!! example "SQLite Handler"

    ```python
    from ddeutil.workflow.traces import SQLiteHandler, Trace

    handler = SQLiteHandler(
        type="sqlite",
        path="./logs/workflow_traces.db",
        table_name="traces"
    )

    trace = Trace(
        run_id="workflow-789",
        handlers=[handler]
    )
    trace.info("SQLite trace initialized")

    # Traces are stored in SQLite with comprehensive schema including
    # all metadata fields for querying and analysis
    ```

#### SQLite Schema

The SQLite handler creates a comprehensive table structure:

```sql
CREATE TABLE traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    parent_run_id TEXT,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    error_flag BOOLEAN NOT NULL,
    datetime TEXT NOT NULL,
    process INTEGER NOT NULL,
    thread INTEGER NOT NULL,
    filename TEXT NOT NULL,
    lineno INTEGER NOT NULL,
    cut_id TEXT,
    workflow_name TEXT,
    stage_name TEXT,
    job_name TEXT,
    duration_ms REAL,
    memory_usage_mb REAL,
    cpu_usage_percent REAL,
    trace_id TEXT,
    span_id TEXT,
    parent_span_id TEXT,
    exception_type TEXT,
    exception_message TEXT,
    stack_trace TEXT,
    error_code TEXT,
    user_id TEXT,
    tenant_id TEXT,
    environment TEXT,
    hostname TEXT,
    ip_address TEXT,
    python_version TEXT,
    package_version TEXT,
    tags TEXT,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### `RestAPIHandler`

REST API integration for external logging services.

!!! example "REST API Handler"

    ```python
    from ddeutil.workflow.traces import RestAPIHandler, Trace

    # Datadog integration
    handler = RestAPIHandler(
        type="restapi",
        service_type="datadog",
        api_url="https://http-intake.logs.datadoghq.com/v1/input",
        api_key="your-datadog-api-key",
        timeout=10.0,
        max_retries=3
    )

    trace = Trace(
        run_id="workflow-123",
        handlers=[handler]
    )
    trace.info("Sending logs to Datadog")
    ```

Supported service types:
- `datadog`: Datadog log ingestion
- `grafana`: Grafana Loki
- `cloudwatch`: AWS CloudWatch Logs
- `generic`: Generic REST API

### `ElasticHandler`

High-performance Elasticsearch logging with bulk indexing and search capabilities.

!!! example "Elasticsearch Handler"

    ```python
    from ddeutil.workflow.traces import ElasticHandler, Trace

    handler = ElasticHandler(
        type="elastic",
        hosts=["http://localhost:9200"],
        username="elastic",
        password="password",
        index="workflow-traces",
        timeout=30.0,
        max_retries=3
    )

    trace = Trace(
        run_id="workflow-123",
        handlers=[handler]
    )
    trace.info("Elasticsearch logging initialized")
    ```

## Data Models

### `TraceData`

Complete trace data including stdout, stderr, and metadata.

| Field    | Type            | Description                    |
|----------|-----------------|--------------------------------|
| `stdout` | str             | Standard output content        |
| `stderr` | str             | Standard error content         |
| `meta`   | list[Metadata]  | List of trace metadata entries |

### `Message`

Message model with prefix parsing and emoji support.

!!! example "Message Formatting"

    ```python
    from ddeutil.workflow.traces import Message

    # Parse message with prefix
    msg = Message.from_str("[WORKFLOW]: Starting execution")
    print(msg.name)  # "WORKFLOW"
    print(msg.message)  # "Starting execution"

    # Prepare with emoji
    formatted = msg.prepare({"log_add_emoji": True})
    print(formatted)  # "🏃 [WORKFLOW]: Starting execution"
    ```

## Logging Levels

The traces system supports standard logging levels:

- `debug`: Detailed diagnostic information
- `info`: General information about workflow progress
- `warning`: Warning messages for potential issues
- `error`: Error messages for failed operations
- `exception`: Critical errors with exception details

## Async Support

All handlers support asynchronous logging for non-blocking operations:

!!! example "Async Logging"

    ```python
    import asyncio
    from ddeutil.workflow.traces import get_trace

    async def async_workflow():
        trace = get_trace("async-workflow-123")

        await trace.amit("Async workflow started", level="info")
        await trace.amit("Processing async operation", level="debug")
        await trace.amit("Async operation failed", level="error")

    asyncio.run(async_workflow())
    ```

## Buffer Support

The `Trace` supports buffered logging for high-performance scenarios:

!!! example "Buffered Logging"

    ```python
    from ddeutil.workflow.traces import get_trace

    # Use context manager for buffered logging
    with get_trace("workflow-123") as trace:
        # All logs are buffered and flushed at exit
        trace.info("Workflow started")
        trace.debug("Processing stage 1")
        trace.info("Processing stage 2")
        trace.info("Workflow completed")

    # All logs are automatically flushed when exiting the context
    ```

## Factory Function

### `get_trace`

Factory function that returns a `Trace` instance with handlers configured from the core configuration.

!!! example "Dynamic Trace Creation"

    ```python
    from ddeutil.workflow.traces import get_trace

    # Automatically selects handlers based on configuration
    trace = get_trace(
        run_id="workflow-123",
        parent_run_id="parent-456",
        extras={"custom_config": "value"}
    )

    # Configuration determines handler types:
    # - Console handler for immediate output
    # - File handler for persistent storage
    # - SQLite handler for database storage
    # - REST API handler for external services
    # - Elasticsearch handler for distributed logging
    ```

## Configuration

Trace behavior is controlled by configuration settings:

| Setting                    | Description                           |
|---------------------------|---------------------------------------|
| `trace_handlers`          | List of handler configurations        |
| `log_format`              | Console log message format           |
| `log_format_file`         | File log message format              |
| `log_datetime_format`     | Datetime format for logs             |
| `log_tz`                  | Timezone for log timestamps          |
| `log_add_emoji`           | Whether to include emojis in messages |
| `logs_trace_frame_layer`  | Stack frame layer for metadata       |

## Performance Considerations

- **ConsoleHandler**: Best for development and debugging
- **FileHandler**: Good for small to medium-scale deployments
- **SQLiteHandler**: Recommended for production with concurrent access
- **RestAPIHandler**: Ideal for integration with external monitoring systems
- **ElasticHandler**: Best for large-scale distributed deployments with search requirements

Choose the appropriate handler(s) based on your deployment scale, persistence requirements, and monitoring needs.
