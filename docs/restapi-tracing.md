# REST API Tracing System

The REST API tracing system provides integration with external monitoring services like Datadog, Grafana, AWS CloudWatch, and other logging platforms. It offers high-performance, buffered logging with retry logic and service-specific formatting.

## Overview

The REST API tracing system consists of:

- **RestAPIHandler**: High-performance logging handler for external services
- **RestAPITrace**: Trace class that uses the REST API handler
- Support for multiple service types with optimized payload formatting
- Buffered sending with retry logic and exponential backoff
- Thread-safe operations with connection pooling

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Workflow      │───▶│  RestAPITrace    │───▶│ RestAPIHandler  │
│   Execution     │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
                                              ┌─────────────────┐
                                              │   External      │
                                              │   Service       │
                                              │   (Datadog,     │
                                              │    Grafana,     │
                                              │    CloudWatch)  │
                                              └─────────────────┘
```

## Supported Services

### 1. Datadog

**Configuration:**
```python
extras = {
    "trace_type": "restapi",
    "api_url": "https://http-intake.logs.datadoghq.com/v1/input",
    "api_key": "your-datadog-api-key",
    "service_type": "datadog",
    "workflow_name": "data-processing-pipeline",
    "stage_name": "data-validation",
    "job_name": "validate-customer-data",
    "trace_id": "trace-123",
    "span_id": "span-456",
    "user_id": "user-123",
    "tenant_id": "tenant-456",
    "environment": "production",
    "tags": ["service:workflow", "team:data-engineering"],
}
```

**Features:**
- Automatic Datadog-specific payload formatting
- Proper tagging and metadata structure
- Service and source identification
- Distributed tracing support

### 2. Grafana Loki

**Configuration:**
```python
extras = {
    "trace_type": "restapi",
    "api_url": "http://localhost:3100/loki/api/v1/push",
    "api_key": "your-grafana-api-key",
    "service_type": "grafana",
    "workflow_name": "ml-training-pipeline",
    "stage_name": "model-training",
    "job_name": "train-neural-network",
    "trace_id": "trace-123",
    "span_id": "span-456",
    "user_id": "ml-engineer-001",
    "tenant_id": "ai-team",
    "environment": "staging",
    "tags": ["service:ml-pipeline", "team:ai"],
}
```

**Features:**
- Loki-compatible stream format
- Structured logging with labels
- Timestamp formatting for Loki
- Batch stream aggregation

### 3. AWS CloudWatch

**Configuration:**
```python
extras = {
    "trace_type": "restapi",
    "api_url": "https://logs.us-east-1.amazonaws.com",
    "api_key": "your-aws-credentials",
    "service_type": "cloudwatch",
    "workflow_name": "etl-pipeline",
    "stage_name": "data-extraction",
    "job_name": "extract-customer-data",
    "trace_id": "trace-123",
    "span_id": "span-456",
    "user_id": "etl-user",
    "tenant_id": "analytics-team",
    "environment": "production",
    "tags": ["service:etl", "team:analytics"],
}
```

**Features:**
- CloudWatch Logs format
- Log group and stream management
- AWS-specific headers and authentication
- Structured JSON message format

### 4. Generic REST API

**Configuration:**
```python
extras = {
    "trace_type": "restapi",
    "api_url": "https://api.example.com/logs",
    "api_key": "your-api-key",
    "service_type": "generic",
    "workflow_name": "custom-workflow",
    "stage_name": "custom-stage",
    "job_name": "custom-job",
    "trace_id": "trace-123",
    "span_id": "span-456",
    "user_id": "custom-user",
    "tenant_id": "custom-tenant",
    "environment": "development",
    "tags": ["service:custom", "team:development"],
}
```

**Features:**
- Flexible payload format
- Custom authentication headers
- Extensible metadata structure
- Generic JSON payload

## Usage

### Basic Usage

```python
from ddeutil.workflow.traces import get_trace

# Create REST API trace
extras = {
    "trace_type": "restapi",
    "api_url": "https://httpbin.org/post",
    "service_type": "generic",
    "workflow_name": "my-workflow",
    "stage_name": "my-stage",
    "job_name": "my-job",
}

trace = get_trace(
    run_id="workflow-123",
    parent_run_id="parent-456",
    extras=extras
)

# Log messages
trace.info("🚀 Starting workflow")
trace.debug("📊 Processing data")
trace.warning("⚠️ Warning message")
trace.error("❌ Error occurred")

# Close trace
trace.close()
```

### Direct Handler Usage

```python
from ddeutil.workflow.traces import RestAPIHandler
import logging

# Create handler directly
handler = RestAPIHandler(
    run_id="direct-123",
    api_url="https://httpbin.org/post",
    service_type="generic",
    buffer_size=50,
    timeout=10.0,
    max_retries=3,
    extras={
        "workflow_name": "direct-test",
        "stage_name": "direct-stage",
        "job_name": "direct-job",
    }
)

# Create logger and add handler
logger = logging.getLogger("direct-test")
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

# Log messages
logger.info("Direct handler test")
logger.error("Error message")

# Flush and close
handler.flush()
handler.close()
```

### Async Usage

```python
import asyncio
from ddeutil.workflow.traces import get_trace

async def async_workflow():
    extras = {
        "trace_type": "restapi",
        "api_url": "https://httpbin.org/post",
        "service_type": "generic",
        "workflow_name": "async-workflow",
    }

    trace = get_trace(run_id="async-123", extras=extras)

    try:
        await trace.ainfo("🚀 Starting async workflow")
        await trace.adebug("⚙️ Initializing components")

        # Simulate async work
        await asyncio.sleep(0.1)

        await trace.ainfo("✅ Async workflow completed")

    finally:
        trace.close()

# Run async workflow
asyncio.run(async_workflow())
```

## Configuration Options

### Handler Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `run_id` | str | Required | Unique identifier for the trace session |
| `parent_run_id` | str | None | Parent workflow run ID |
| `api_url` | str | Required | REST API endpoint URL |
| `api_key` | str | None | API key for authentication |
| `service_type` | str | "generic" | Service type (datadog, grafana, cloudwatch, generic) |
| `buffer_size` | int | 50 | Number of records to buffer before sending |
| `flush_interval` | float | 2.0 | Interval in seconds to flush buffers |
| `timeout` | float | 10.0 | HTTP request timeout in seconds |
| `max_retries` | int | 3 | Maximum number of retry attempts |

### Service-Specific Headers

**Datadog:**
```python
headers = {
    "Content-Type": "application/json",
    "DD-API-KEY": api_key,
    "User-Agent": "ddeutil-workflow/1.0",
}
```

**Grafana:**
```python
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}",
    "User-Agent": "ddeutil-workflow/1.0",
}
```

**CloudWatch:**
```python
headers = {
    "Content-Type": "application/json",
    "X-Amz-Target": "Logs_20140328.PutLogEvents",
    "Authorization": f"AWS4-HMAC-SHA256 {api_key}",
    "User-Agent": "ddeutil-workflow/1.0",
}
```

## Performance Optimization

### Buffering Strategy

The handler uses intelligent buffering to optimize performance:

1. **Buffer Size**: Configurable buffer size (default: 50 records)
2. **Flush Triggers**:
   - Buffer full
   - Manual flush
   - Handler close
3. **Batch Sending**: Multiple records sent in single HTTP request

### Retry Logic

Robust retry mechanism with exponential backoff:

```python
for attempt in range(max_retries):
    try:
        response = session.post(api_url, json=payload, timeout=timeout)
        response.raise_for_status()
        return True
    except Exception as e:
        if attempt == max_retries - 1:
            logger.error(f"Failed after {max_retries} attempts: {e}")
            return False
        else:
            time.sleep(2 ** attempt)  # Exponential backoff
```

### Thread Safety

- Thread-safe operations using locks
- Connection pooling with requests.Session
- Proper resource cleanup

## Error Handling

### Common Error Scenarios

1. **Network Errors**: Automatic retry with exponential backoff
2. **Authentication Errors**: Logged and reported
3. **Rate Limiting**: Respects service limits
4. **Invalid Payload**: Validation before sending

### Error Recovery

```python
try:
    trace.info("Processing data")
except Exception as e:
    # Handler automatically retries on network errors
    # Authentication errors are logged
    logger.error(f"Tracing error: {e}")
```

## Monitoring and Debugging

### Performance Metrics

```python
# Monitor handler performance
handler = RestAPIHandler(...)

# Check buffer status
print(f"Buffer size: {len(handler.log_buffer)}")

# Force flush
handler.flush()

# Check connection status
print(f"Session active: {handler.session is not None}")
```

### Debug Logging

Enable debug logging to monitor handler operations:

```python
import logging
logging.getLogger("ddeutil.workflow").setLevel(logging.DEBUG)
```

## Best Practices

### 1. Configuration Management

```python
# Use environment variables for sensitive data
import os

extras = {
    "trace_type": "restapi",
    "api_url": os.getenv("REST_API_URL"),
    "api_key": os.getenv("REST_API_KEY"),
    "service_type": "datadog",
}
```

### 2. Resource Management

```python
# Always close traces to flush buffers
try:
    trace = get_trace(run_id="workflow-123", extras=extras)
    trace.info("Processing...")
finally:
    trace.close()  # Ensures buffers are flushed
```

### 3. Error Handling

```python
# Handle tracing errors gracefully
try:
    trace.info("Important message")
except Exception as e:
    # Log to fallback destination
    fallback_logger.error(f"Tracing failed: {e}")
```

### 4. Performance Tuning

```python
# Adjust buffer size based on workload
extras = {
    "trace_type": "restapi",
    "api_url": "https://api.example.com/logs",
    "buffer_size": 100,  # Larger buffer for high-volume logging
    "flush_interval": 5.0,  # Longer interval for batch processing
}
```

### 5. Service-Specific Optimization

**Datadog:**
- Use appropriate tags for filtering
- Include service and source information
- Leverage distributed tracing fields

**Grafana:**
- Structure logs for efficient querying
- Use consistent label patterns
- Optimize timestamp formatting

**CloudWatch:**
- Organize logs into logical groups
- Use structured JSON for complex data
- Consider log retention policies

## Migration Guide

### From File Tracing

```python
# Old file-based approach
from ddeutil.workflow.traces import FileTrace

trace = FileTrace(
    url="file://./logs",
    run_id="workflow-123",
    extras={}
)

# New REST API approach
from ddeutil.workflow.traces import get_trace

trace = get_trace(
    run_id="workflow-123",
    extras={
        "trace_type": "restapi",
        "api_url": "https://api.example.com/logs",
        "service_type": "generic",
    }
)
```

### From Console Tracing

```python
# Old console-based approach
from ddeutil.workflow.traces import ConsoleTrace

trace = ConsoleTrace(
    run_id="workflow-123",
    extras={}
)

# New REST API approach
trace = get_trace(
    run_id="workflow-123",
    extras={
        "trace_type": "restapi",
        "api_url": "https://api.example.com/logs",
        "service_type": "generic",
    }
)
```

## Troubleshooting

### Common Issues

1. **Connection Timeouts**
   - Increase timeout value
   - Check network connectivity
   - Verify API endpoint

2. **Authentication Errors**
   - Verify API key format
   - Check service-specific requirements
   - Ensure proper headers

3. **Rate Limiting**
   - Reduce buffer size
   - Increase flush interval
   - Check service limits

4. **Payload Format Errors**
   - Verify service type configuration
   - Check payload structure
   - Validate JSON formatting

### Debug Commands

```python
# Enable detailed logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Test connection
handler = RestAPIHandler(...)
handler.flush()  # Force send to test connectivity

# Check payload format
print(handler._format_for_service(trace_meta))
```

## Examples

See the complete examples in `examples/restapi_tracing_example.py` for:

- Datadog integration
- Grafana Loki integration
- AWS CloudWatch integration
- Generic REST API usage
- Direct handler usage
- Performance comparison
- Context-aware logging
- Async logging

## Dependencies

Required packages:
- `requests` - HTTP client for REST API calls

Optional packages:
- `aiofiles` - For async file operations (if needed)

Install dependencies:
```bash
pip install requests
```

## API Reference

### RestAPIHandler

**Constructor:**
```python
RestAPIHandler(
    run_id: str,
    parent_run_id: Optional[str] = None,
    api_url: str = "",
    api_key: Optional[str] = None,
    service_type: Literal["datadog", "grafana", "cloudwatch", "generic"] = "generic",
    extras: Optional[DictData] = None,
    buffer_size: int = 50,
    flush_interval: float = 2.0,
    timeout: float = 10.0,
    max_retries: int = 3,
)
```

**Methods:**
- `emit(record)`: Process log record
- `flush()`: Flush buffered records
- `close()`: Close handler and cleanup

### RestAPITrace

**Constructor:**
```python
RestAPITrace(
    url: ParseResult,
    run_id: str,
    parent_run_id: Optional[str] = None,
    extras: Optional[DictData] = None,
)
```

**Methods:**
- `info(message)`: Log info message
- `debug(message)`: Log debug message
- `warning(message)`: Log warning message
- `error(message)`: Log error message
- `exception(message)`: Log exception message
- `close()`: Close trace and cleanup
- `ainfo(message)`: Async log info message
- `adebug(message)`: Async log debug message
- `awarning(message)`: Async log warning message
- `aerror(message)`: Async log error message
- `aexception(message)`: Async log exception message
