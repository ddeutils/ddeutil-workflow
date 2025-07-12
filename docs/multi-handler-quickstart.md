# Multi-Handler Tracing Quick Start

This guide will help you get started with the multi-handler tracing system quickly.

## Installation

The multi-handler system is included in the main package. No additional installation is required.

## Basic Usage

### 1. Simple Multi-Handler Setup

```python
from ddeutil.workflow.traces import get_trace

# Configure multi-handler with file and SQLite
extras = {
    "trace_type": "multi",
    "handlers": [
        {
            "type": "file",
            "path": "./logs/workflow",
        },
        {
            "type": "sqlite",
            "path": "./logs/workflow_traces.db",
        }
    ],
    "fail_silently": True,
}

# Create and use trace
trace = get_trace(run_id="my-workflow-001", extras=extras)

trace.info("Workflow started")
trace.debug("Processing data")
trace.error("Error occurred")
trace.close()
```

### 2. Add REST API Handler

```python
extras = {
    "trace_type": "multi",
    "handlers": [
        {
            "type": "file",
            "path": "./logs/workflow",
        },
        {
            "type": "restapi",
            "api_url": "https://httpbin.org/post",
            "service_type": "generic",
            "buffer_size": 50,
            "flush_interval": 2.0,
        }
    ],
    "fail_silently": True,
}
```

### 3. Add Elasticsearch Handler

```python
extras = {
    "trace_type": "multi",
    "handlers": [
        {
            "type": "file",
            "path": "./logs/workflow",
        },
        {
            "type": "elasticsearch",
            "es_hosts": "http://localhost:9200",
            "index_name": "workflow-traces",
            "username": "elastic",
            "password": "changeme",
        }
    ],
    "fail_silently": True,
}
```

## Handler Configuration Options

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
    "path": "./logs/traces.db",       # Database file path
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

### Add Handler at Runtime

```python
from ddeutil.workflow.traces import SQLiteHandler

# Create trace with initial handlers
trace = get_trace(run_id="dynamic-example", extras={"trace_type": "multi", "handlers": [...]})

# Add SQLite handler dynamically
sqlite_handler = SQLiteHandler(
    run_id=trace.run_id,
    db_path="./logs/dynamic_traces.db",
    extras=trace.extras,
)
trace.add_handler(sqlite_handler)

# Log message (will go to all handlers)
trace.info("This message goes to all handlers")
```

### Remove Handler

```python
# Remove a specific handler
trace.remove_handler(sqlite_handler)

# Check handler count
print(f"Active handlers: {trace.handler_count}")
```

### Inspect Handlers

```python
# Get handler information
print(f"Handler count: {trace.handler_count}")
print(f"Handler types: {trace.handler_types}")

# Get specific handler
from ddeutil.workflow.traces import WorkflowFileHandler
file_handler = trace.get_handler_by_type(WorkflowFileHandler)
if file_handler:
    print(f"File handler path: {file_handler.log_dir}")
```

## Environment-Specific Configurations

### Development
```python
def get_dev_config():
    return {
        "trace_type": "multi",
        "handlers": [
            {"type": "file", "path": "./logs/dev"},
            {"type": "sqlite", "path": "./logs/dev_traces.db"}
        ],
        "fail_silently": True,
    }
```

### Production
```python
def get_prod_config():
    return {
        "trace_type": "multi",
        "handlers": [
            {"type": "file", "path": "./logs/prod"},
            {"type": "sqlite", "path": "./logs/prod_traces.db"},
            {
                "type": "restapi",
                "api_url": "https://api.example.com/logs",
                "service_type": "datadog",
                "api_key": "prod-api-key",
            },
            {
                "type": "elasticsearch",
                "es_hosts": "https://elastic.example.com:9200",
                "index_name": "production-traces",
                "username": "elastic",
                "password": "secure-password",
            }
        ],
        "fail_silently": False,  # Fail fast in production
    }
```

## Error Handling

### Fail-Silently Behavior

```python
extras = {
    "trace_type": "multi",
    "handlers": [
        {"type": "file", "path": "./logs"},  # This will work
        {"type": "restapi", "api_url": "https://invalid-url.com"},  # This will fail
    ],
    "fail_silently": True,  # Continue logging even if REST API fails
}

trace = get_trace(run_id="error-test", extras=extras)
trace.info("This will still work")  # Logs to file, skips REST API
```

### Monitor Errors

```python
import logging

# Monitor handler errors
logging.getLogger("ddeutil.workflow").setLevel(logging.ERROR)

trace = get_trace(run_id="error-test", extras=extras)
# Handler errors will be logged to the main logger
```

## Performance Tips

### High-Throughput Configuration

```python
extras = {
    "trace_type": "multi",
    "handlers": [
        {
            "type": "file",
            "path": "./logs",
            "buffer_size": 16384,    # Larger buffer
            "flush_interval": 5.0,   # Less frequent flushes
        },
        {
            "type": "sqlite",
            "path": "./logs/traces.db",
            "buffer_size": 500,      # More records per batch
            "flush_interval": 5.0,   # Less frequent flushes
        }
    ]
}
```

### Low-Latency Configuration

```python
extras = {
    "trace_type": "multi",
    "handlers": [
        {
            "type": "file",
            "path": "./logs",
            "buffer_size": 4096,     # Smaller buffer
            "flush_interval": 0.5,   # More frequent flushes
        },
        {
            "type": "sqlite",
            "path": "./logs/traces.db",
            "buffer_size": 10,       # Fewer records per batch
            "flush_interval": 0.5,   # More frequent flushes
        }
    ]
}
```

## Async Support

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
        await trace.ainfo("Async workflow completed")
    finally:
        trace.close()

# Run async workflow
asyncio.run(async_workflow())
```

## Direct Handler Usage

```python
import logging
from ddeutil.workflow.traces import MultiHandler, WorkflowFileHandler, SQLiteHandler

# Create handlers
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

# Cleanup
multi_handler.close()
```

## Common Patterns

### Conditional Handlers

```python
import os

def get_conditional_config():
    handlers = [
        {"type": "file", "path": "./logs"}
    ]

    # Add SQLite in development
    if os.getenv("ENVIRONMENT") == "development":
        handlers.append({
            "type": "sqlite",
            "path": "./logs/dev_traces.db"
        })

    # Add REST API in staging/production
    if os.getenv("ENVIRONMENT") in ["staging", "production"]:
        handlers.append({
            "type": "restapi",
            "api_url": os.getenv("LOG_API_URL"),
            "service_type": "datadog",
        })

    # Add Elasticsearch only in production
    if os.getenv("ENVIRONMENT") == "production":
        handlers.append({
            "type": "elasticsearch",
            "es_hosts": os.getenv("ES_HOSTS"),
            "index_name": "production-traces",
        })

    return {
        "trace_type": "multi",
        "handlers": handlers,
        "fail_silently": True,
    }
```

### Handler Rotation

```python
def rotate_handlers(trace, new_handlers):
    """Replace all handlers with new ones."""
    # Remove existing handlers
    for handler in trace._handler.handlers[:]:
        trace.remove_handler(handler)

    # Add new handlers
    for handler in new_handlers:
        trace.add_handler(handler)
```

## Troubleshooting

### Check Handler Status

```python
# Check if handlers are working
print(f"Handler count: {trace.handler_count}")
print(f"Handler types: {trace.handler_types}")

# Test each handler
trace.info("Test message")
trace.flush()  # Force flush to see if handlers work
```

### Debug Mode

```python
import logging

# Enable debug logging
logging.getLogger("ddeutil.workflow").setLevel(logging.DEBUG)

# Create trace and check for errors
trace = get_trace(run_id="debug-test", extras=extras)
```

### Common Issues

1. **File permission errors**: Check write permissions for log directories
2. **Network timeouts**: Increase timeout values for REST API/Elasticsearch handlers
3. **Memory usage**: Reduce buffer sizes if memory is limited
4. **Data loss**: Reduce flush intervals for critical data

## Next Steps

- Read the full [Multi-Handler Tracing Documentation](multi-handler-tracing.md)
- Explore the [Multi-Handler Examples](examples/multi_handler_tracing_example.py)
- Check out [REST API Tracing](restapi-tracing.md) and [Elasticsearch Tracing](elasticsearch-tracing.md) for specific handler details
