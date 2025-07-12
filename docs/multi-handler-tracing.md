# Multi-Handler Tracing System

The multi-handler tracing system allows you to log workflow execution data to multiple destinations simultaneously. This provides flexibility for different use cases, such as local debugging, centralized monitoring, and compliance requirements.

## Overview

The multi-handler system consists of two main components:

1. **MultiHandler**: A Python logging handler that combines multiple handlers
2. **MultiTrace**: A trace implementation that uses the MultiHandler

### Key Features

- **Multi-destination logging**: Log to file, SQLite, REST API, and Elasticsearch simultaneously
- **Dynamic handler management**: Add/remove handlers at runtime
- **Fail-silently behavior**: Continue logging even if some handlers fail
- **Handler-specific configuration**: Configure each handler independently
- **Performance optimization**: Buffered logging with configurable flush intervals
- **Thread safety**: Safe for concurrent access
- **Seamless integration**: Works with existing trace implementations

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MultiTrace    │    │   MultiHandler  │    │   Individual    │
│                 │───▶│                 │───▶│   Handlers      │
│ - Configuration │    │ - Handler Mgmt  │    │                 │
│ - Logging API   │    │ - Error Handling│    │ - FileHandler   │
│ - Async Support │    │ - Buffering     │    │ - SQLiteHandler │
└─────────────────┘    └─────────────────┘    │ - RestAPIHandler│
                                              │ - Elasticsearch │
                                              └─────────────────┘
```

## Usage

### Basic Configuration

```python
from ddeutil.workflow.traces import get_trace

# Configure multi-handler with file and SQLite
extras = {
    "trace_type": "multi",
    "handlers": [
        {
            "type": "file",
            "path": "./logs/multi-example",
            "buffer_size": 8192,
            "flush_interval": 1.0,
        },
        {
            "type": "sqlite",
            "path": "./logs/multi_traces.db",
            "buffer_size": 100,
            "flush_interval": 2.0,
        }
    ],
    "fail_silently": True,
    "workflow_name": "multi-handler-workflow",
    "stage_name": "multi-stage",
    "job_name": "multi-job",
}

# Create trace instance
trace = get_trace(
    run_id="multi-example-001",
    parent_run_id="parent-001",
    extras=extras
)

# Use the trace
trace.info("Starting multi-handler workflow")
trace.debug("Processing data")
trace.error("Error occurred")
trace.close()
```

### Advanced Configuration

```python
# Configure with all handler types
extras = {
    "trace_type": "multi",
    "handlers": [
        {
            "type": "file",
            "path": "./logs/advanced-multi",
            "buffer_size": 8192,
            "flush_interval": 1.0,
        },
        {
            "type": "sqlite",
            "path": "./logs/advanced_multi_traces.db",
            "buffer_size": 100,
            "flush_interval": 2.0,
        },
        {
            "type": "restapi",
            "api_url": "https://api.example.com/logs",
            "api_key": "your-api-key",
            "service_type": "datadog",
            "buffer_size": 50,
            "flush_interval": 2.0,
            "timeout": 10.0,
            "max_retries": 3,
        },
        {
            "type": "elasticsearch",
            "es_hosts": "http://localhost:9200",
            "index_name": "advanced-multi-traces",
            "username": "elastic",
            "password": "changeme",
            "buffer_size": 100,
            "flush_interval": 2.0,
            "timeout": 30.0,
            "max_retries": 3,
        }
    ],
    "fail_silently": True,
    "workflow_name": "advanced-multi-workflow",
    "environment": "production",
}
```

## Handler Types

### File Handler

```python
{
    "type": "file",
    "path": "./logs/workflow",        # Log directory
    "buffer_size": 8192,              # Buffer size in bytes
    "flush_interval": 1.0,            # Flush interval in seconds
}
```

### SQLite Handler

```python
{
    "type": "sqlite",
    "path": "./logs/workflow_traces.db",
    "buffer_size": 100,               # Number of records to buffer
    "flush_interval": 2.0,            # Flush interval in seconds
}
```

### REST API Handler

```python
{
    "type": "restapi",
    "api_url": "https://api.example.com/logs",
    "api_key": "your-api-key",        # Optional
    "service_type": "datadog",        # datadog, grafana, cloudwatch, generic
    "buffer_size": 50,                # Number of records to buffer
    "flush_interval": 2.0,            # Flush interval in seconds
    "timeout": 10.0,                  # HTTP timeout in seconds
    "max_retries": 3,                 # Maximum retry attempts
}
```

### Elasticsearch Handler

```python
{
    "type": "elasticsearch",
    "es_hosts": "http://localhost:9200",
    "index_name": "workflow-traces",
    "username": "elastic",            # Optional
    "password": "changeme",           # Optional
    "buffer_size": 100,               # Number of records to buffer
    "flush_interval": 2.0,            # Flush interval in seconds
    "timeout": 30.0,                  # Elasticsearch timeout in seconds
    "max_retries": 3,                 # Maximum retry attempts
}
```

## Dynamic Handler Management

### Adding Handlers

```python
from ddeutil.workflow.traces import SQLiteHandler, RestAPIHandler

# Create trace with initial handlers
trace = get_trace(
    run_id="dynamic-example",
    extras={"trace_type": "multi", "handlers": [...]}
)

# Add SQLite handler dynamically
sqlite_handler = SQLiteHandler(
    run_id=trace.run_id,
    parent_run_id=trace.parent_run_id,
    db_path="./logs/dynamic_traces.db",
    extras=trace.extras,
)
trace.add_handler(sqlite_handler)

# Add REST API handler dynamically
restapi_handler = RestAPIHandler(
    run_id=trace.run_id,
    parent_run_id=trace.parent_run_id,
    api_url="https://api.example.com/logs",
    service_type="generic",
    extras=trace.extras,
)
trace.add_handler(restapi_handler)
```

### Removing Handlers

```python
# Remove a specific handler
trace.remove_handler(sqlite_handler)

# Check handler count
print(f"Active handlers: {trace.handler_count}")
```

### Handler Inspection

```python
# Get handler information
print(f"Handler count: {trace.handler_count}")
print(f"Handler types: {trace.handler_types}")

# Get handlers by type
from ddeutil.workflow.traces import WorkflowFileHandler, SQLiteHandler
file_handlers = trace.get_handlers_by_type(WorkflowFileHandler)
sqlite_handlers = trace.get_handlers_by_type(SQLiteHandler)

# Get specific handler
file_handler = trace.get_handler_by_type(WorkflowFileHandler)
if file_handler:
    print(f"File handler path: {file_handler.log_dir}")
```

## Error Handling

### Fail-Silently Behavior

The multi-handler system supports fail-silently behavior, which allows logging to continue even if some handlers fail:

```python
extras = {
    "trace_type": "multi",
    "handlers": [
        {
            "type": "file",
            "path": "./logs/working-handler",
        },
        {
            "type": "restapi",
            "api_url": "https://invalid-url.com",  # This will fail
        }
    ],
    "fail_silently": True,  # Continue even if REST API fails
}

trace = get_trace(run_id="error-test", extras=extras)
trace.info("This will still work")  # Logs to file, skips REST API
```

### Error Monitoring

```python
import logging

# Monitor handler errors
logger = logging.getLogger("ddeutil.workflow")
logger.setLevel(logging.ERROR)

# Handler errors will be logged to the main logger
trace = get_trace(run_id="error-test", extras=extras)
```

## Performance Considerations

### Buffer Configuration

Optimize performance by configuring appropriate buffer sizes and flush intervals:

```python
# High-throughput configuration
extras = {
    "trace_type": "multi",
    "handlers": [
        {
            "type": "file",
            "buffer_size": 16384,    # Larger buffer
            "flush_interval": 5.0,   # Less frequent flushes
        },
        {
            "type": "sqlite",
            "buffer_size": 500,      # More records per batch
            "flush_interval": 5.0,   # Less frequent flushes
        }
    ]
}
```

### Performance Comparison

```python
import time

# Test single handler
single_trace = get_trace(run_id="single", extras={"trace_type": "file"})
start_time = time.time()
for i in range(1000):
    single_trace.info(f"Message {i}")
single_trace.close()
single_duration = time.time() - start_time

# Test multi-handler
multi_trace = get_trace(run_id="multi", extras={"trace_type": "multi", "handlers": [...]})
start_time = time.time()
for i in range(1000):
    multi_trace.info(f"Message {i}")
multi_trace.close()
multi_duration = time.time() - start_time

print(f"Single handler: {single_duration:.3f}s")
print(f"Multi handler: {multi_duration:.3f}s")
print(f"Performance ratio: {single_duration / multi_duration:.2f}x")
```

## Environment-Specific Configuration

### Development Environment

```python
def get_dev_config():
    return {
        "trace_type": "multi",
        "handlers": [
            {
                "type": "file",
                "path": "./logs/dev",
                "buffer_size": 4096,
                "flush_interval": 1.0,
            },
            {
                "type": "sqlite",
                "path": "./logs/dev_traces.db",
                "buffer_size": 50,
                "flush_interval": 1.0,
            }
        ],
        "fail_silently": True,
        "environment": "development",
    }
```

### Staging Environment

```python
def get_staging_config():
    return {
        "trace_type": "multi",
        "handlers": [
            {
                "type": "file",
                "path": "./logs/staging",
                "buffer_size": 8192,
                "flush_interval": 2.0,
            },
            {
                "type": "sqlite",
                "path": "./logs/staging_traces.db",
                "buffer_size": 100,
                "flush_interval": 2.0,
            },
            {
                "type": "restapi",
                "api_url": "https://staging-api.example.com/logs",
                "service_type": "generic",
                "buffer_size": 50,
                "flush_interval": 2.0,
            }
        ],
        "fail_silently": True,
        "environment": "staging",
    }
```

### Production Environment

```python
def get_production_config():
    return {
        "trace_type": "multi",
        "handlers": [
            {
                "type": "file",
                "path": "./logs/production",
                "buffer_size": 16384,
                "flush_interval": 5.0,
            },
            {
                "type": "sqlite",
                "path": "./logs/production_traces.db",
                "buffer_size": 200,
                "flush_interval": 5.0,
            },
            {
                "type": "restapi",
                "api_url": "https://api.example.com/logs",
                "api_key": "prod-api-key",
                "service_type": "datadog",
                "buffer_size": 100,
                "flush_interval": 5.0,
            },
            {
                "type": "elasticsearch",
                "es_hosts": "https://elastic.example.com:9200",
                "index_name": "production-traces",
                "username": "elastic",
                "password": "secure-password",
                "buffer_size": 200,
                "flush_interval": 5.0,
            }
        ],
        "fail_silently": False,  # Fail fast in production
        "environment": "production",
    }
```

## Async Support

The multi-handler system supports async logging operations:

```python
import asyncio

async def async_workflow():
    trace = get_trace(
        run_id="async-example",
        extras={"trace_type": "multi", "handlers": [...]}
    )

    try:
        await trace.ainfo("Starting async workflow")
        await trace.adebug("Processing async data")

        # Simulate async work
        await asyncio.sleep(1)

        await trace.ainfo("Async workflow completed")
    finally:
        trace.close()

# Run async workflow
asyncio.run(async_workflow())
```

## Direct Handler Usage

You can also use the MultiHandler directly with Python's logging system:

```python
import logging
from ddeutil.workflow.traces import MultiHandler, WorkflowFileHandler, SQLiteHandler

# Create individual handlers
file_handler = WorkflowFileHandler(
    run_id="direct-example",
    base_path="./logs/direct",
    extras={"workflow_name": "direct-test"}
)

sqlite_handler = SQLiteHandler(
    run_id="direct-example",
    db_path="./logs/direct_traces.db",
    extras={"workflow_name": "direct-test"}
)

# Create multi-handler
multi_handler = MultiHandler(
    run_id="direct-example",
    handlers=[file_handler, sqlite_handler],
    extras={"workflow_name": "direct-test"},
    fail_silently=True,
)

# Use with Python logger
logger = logging.getLogger("direct-test")
logger.setLevel(logging.DEBUG)
logger.addHandler(multi_handler)

# Log messages
logger.info("Direct multi-handler test")
logger.debug("Debug information")
logger.warning("Warning message")
logger.error("Error message")

# Cleanup
multi_handler.close()
```

## Best Practices

### 1. Handler Configuration

- **Buffer sizes**: Larger buffers improve performance but use more memory
- **Flush intervals**: Longer intervals reduce I/O but increase risk of data loss
- **Fail-silently**: Use `True` for development, `False` for production

### 2. Error Handling

- Monitor handler errors through the main logger
- Use appropriate retry configurations for network handlers
- Implement circuit breakers for external services

### 3. Performance Optimization

- Use appropriate buffer sizes for your workload
- Configure flush intervals based on data criticality
- Monitor handler performance and adjust accordingly

### 4. Security

- Store API keys and passwords securely
- Use HTTPS for external API calls
- Implement proper authentication for Elasticsearch

### 5. Monitoring

- Monitor handler success/failure rates
- Track buffer utilization and flush frequency
- Set up alerts for handler failures

## Troubleshooting

### Common Issues

1. **Handler initialization failures**
   - Check file permissions for file handlers
   - Verify database connectivity for SQLite handlers
   - Test network connectivity for REST API handlers

2. **Performance issues**
   - Increase buffer sizes
   - Adjust flush intervals
   - Monitor system resources

3. **Data loss**
   - Reduce flush intervals
   - Check fail-silently configuration
   - Monitor handler errors

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.getLogger("ddeutil.workflow").setLevel(logging.DEBUG)

trace = get_trace(run_id="debug-test", extras={"trace_type": "multi", "handlers": [...]})
```

## Migration Guide

### From Single Handler

```python
# Before: Single file handler
trace = get_trace(run_id="example", extras={"trace_type": "file"})

# After: Multi-handler with file and SQLite
trace = get_trace(
    run_id="example",
    extras={
        "trace_type": "multi",
        "handlers": [
            {"type": "file", "path": "./logs"},
            {"type": "sqlite", "path": "./logs/traces.db"}
        ]
    }
)
```

### From Multiple Trace Instances

```python
# Before: Multiple trace instances
file_trace = get_trace(run_id="example", extras={"trace_type": "file"})
sqlite_trace = get_trace(run_id="example", extras={"trace_type": "sqlite"})

file_trace.info("Message")
sqlite_trace.info("Message")

# After: Single multi-handler trace
trace = get_trace(
    run_id="example",
    extras={
        "trace_type": "multi",
        "handlers": [
            {"type": "file", "path": "./logs"},
            {"type": "sqlite", "path": "./logs/traces.db"}
        ]
    }
)

trace.info("Message")  # Logs to both destinations
```

## API Reference

### MultiHandler

#### Constructor

```python
MultiHandler(
    run_id: str,
    parent_run_id: Optional[str] = None,
    handlers: Optional[list[logging.Handler]] = None,
    extras: Optional[DictData] = None,
    fail_silently: bool = True,
)
```

#### Methods

- `add_handler(handler: logging.Handler)`: Add a new handler
- `remove_handler(handler: logging.Handler)`: Remove a handler
- `get_handler_by_type(handler_type: type)`: Get handler by type
- `get_handlers_by_type(handler_type: type)`: Get all handlers of a type
- `flush()`: Flush all handlers
- `close()`: Close all handlers

#### Properties

- `handler_count`: Number of active handlers
- `handler_types`: List of handler type names

### MultiTrace

#### Constructor

```python
MultiTrace(
    url: ParseResult,
    run_id: str,
    parent_run_id: Optional[str] = None,
    extras: Optional[DictData] = None,
)
```

#### Methods

- `add_handler(handler: logging.Handler)`: Add a new handler
- `remove_handler(handler: logging.Handler)`: Remove a handler
- `get_handler_by_type(handler_type: type)`: Get handler by type
- `get_handlers_by_type(handler_type: type)`: Get all handlers of a type
- `writer(message: str, level: str, is_err: bool = False)`: Write log message
- `awriter(message: str, level: str, is_err: bool = False)`: Async write
- `close()`: Close the trace

#### Properties

- `handler_count`: Number of active handlers
- `handler_types`: List of handler type names

## Examples

See the `examples/multi_handler_tracing_example.py` file for comprehensive examples demonstrating:

- Basic multi-handler usage
- Advanced configurations
- Dynamic handler management
- Handler inspection
- Fail-silently behavior
- Direct handler usage
- Performance comparison
- Async operations
- Environment-specific configurations
