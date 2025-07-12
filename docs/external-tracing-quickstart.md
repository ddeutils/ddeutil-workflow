# External Tracing Quick Start Guide

This guide provides a quick overview of the new external tracing handlers for REST API services and Elasticsearch.

## Overview

The external tracing system provides two new handlers:

1. **RestAPIHandler** - For external monitoring services (Datadog, Grafana, CloudWatch, etc.)
2. **ElasticsearchHandler** - For scalable, searchable log storage

## Quick Start

### 1. REST API Tracing (Datadog, Grafana, CloudWatch)

```python
from ddeutil.workflow.traces import get_trace

# Configure for your service
extras = {
    "trace_type": "restapi",
    "api_url": "https://your-service-endpoint.com",
    "api_key": "your-api-key",
    "service_type": "datadog",  # or "grafana", "cloudwatch", "generic"
    "workflow_name": "my-workflow",
    "stage_name": "my-stage",
    "job_name": "my-job",
}

# Create trace
trace = get_trace(run_id="workflow-123", extras=extras)

# Log messages
trace.info("🚀 Starting workflow")
trace.debug("📊 Processing data")
trace.error("❌ Error occurred")

# Close trace
trace.close()
```

### 2. Elasticsearch Tracing

```python
from ddeutil.workflow.traces import get_trace

# Configure Elasticsearch
extras = {
    "trace_type": "elasticsearch",
    "es_hosts": "http://localhost:9200",
    "index_name": "workflow-traces",
    "username": "elastic",
    "password": "changeme",
    "workflow_name": "my-workflow",
    "stage_name": "my-stage",
    "job_name": "my-job",
}

# Create trace
trace = get_trace(run_id="workflow-123", extras=extras)

# Log messages
trace.info("🚀 Starting workflow")
trace.debug("📊 Processing data")
trace.error("❌ Error occurred")

# Close trace
trace.close()
```

## Service-Specific Examples

### Datadog

```python
extras = {
    "trace_type": "restapi",
    "api_url": "https://http-intake.logs.datadoghq.com/v1/input",
    "api_key": "your-datadog-api-key",
    "service_type": "datadog",
    "workflow_name": "data-pipeline",
    "tags": ["service:workflow", "team:data"],
}
```

### Grafana Loki

```python
extras = {
    "trace_type": "restapi",
    "api_url": "http://localhost:3100/loki/api/v1/push",
    "api_key": "your-grafana-api-key",
    "service_type": "grafana",
    "workflow_name": "ml-pipeline",
    "tags": ["service:ml", "team:ai"],
}
```

### AWS CloudWatch

```python
extras = {
    "trace_type": "restapi",
    "api_url": "https://logs.us-east-1.amazonaws.com",
    "api_key": "your-aws-credentials",
    "service_type": "cloudwatch",
    "workflow_name": "etl-pipeline",
    "tags": ["service:etl", "team:analytics"],
}
```

### Elasticsearch Cluster

```python
extras = {
    "trace_type": "elasticsearch",
    "es_hosts": [
        "http://es-node1:9200",
        "http://es-node2:9200",
        "http://es-node3:9200"
    ],
    "index_name": "workflow-traces",
    "username": "elastic",
    "password": "changeme",
    "workflow_name": "distributed-workflow",
}
```

## Direct Handler Usage

### REST API Handler

```python
from ddeutil.workflow.traces import RestAPIHandler
import logging

handler = RestAPIHandler(
    run_id="direct-123",
    api_url="https://httpbin.org/post",
    service_type="generic",
    buffer_size=50,
    extras={"workflow_name": "direct-test"}
)

logger = logging.getLogger("direct-test")
logger.addHandler(handler)
logger.info("Direct handler test")
handler.close()
```

### Elasticsearch Handler

```python
from ddeutil.workflow.traces import ElasticsearchHandler
import logging

handler = ElasticsearchHandler(
    run_id="direct-123",
    es_hosts="http://localhost:9200",
    index_name="direct-test",
    username="elastic",
    password="changeme",
    buffer_size=100,
    extras={"workflow_name": "direct-test"}
)

logger = logging.getLogger("direct-test")
logger.addHandler(handler)
logger.info("Direct handler test")
handler.close()
```

## Async Usage

```python
import asyncio
from ddeutil.workflow.traces import get_trace

async def async_workflow():
    extras = {
        "trace_type": "restapi",  # or "elasticsearch"
        "api_url": "https://httpbin.org/post",
        "service_type": "generic",
        "workflow_name": "async-workflow",
    }

    trace = get_trace(run_id="async-123", extras=extras)

    try:
        await trace.ainfo("🚀 Starting async workflow")
        await trace.adebug("⚙️ Initializing components")
        await trace.ainfo("✅ Async workflow completed")
    finally:
        trace.close()

asyncio.run(async_workflow())
```

## Configuration Options

### Common Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `trace_type` | str | Required | "restapi" or "elasticsearch" |
| `workflow_name` | str | None | Name of the workflow |
| `stage_name` | str | None | Name of the current stage |
| `job_name` | str | None | Name of the current job |
| `trace_id` | str | None | Distributed tracing ID |
| `span_id` | str | None | Span ID for tracing |
| `user_id` | str | None | User who triggered the workflow |
| `tenant_id` | str | None | Tenant ID for multi-tenancy |
| `environment` | str | None | Environment (dev, staging, prod) |
| `tags` | list | [] | Custom tags for categorization |

### REST API Specific

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `api_url` | str | Required | REST API endpoint URL |
| `api_key` | str | None | API key for authentication |
| `service_type` | str | "generic" | "datadog", "grafana", "cloudwatch", "generic" |
| `buffer_size` | int | 50 | Records to buffer before sending |
| `timeout` | float | 10.0 | HTTP request timeout |
| `max_retries` | int | 3 | Maximum retry attempts |

### Elasticsearch Specific

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `es_hosts` | str/list | "http://localhost:9200" | Elasticsearch host(s) |
| `index_name` | str | "workflow-traces" | Elasticsearch index name |
| `username` | str | None | Elasticsearch username |
| `password` | str | None | Elasticsearch password |
| `buffer_size` | int | 100 | Records to buffer before indexing |
| `timeout` | float | 30.0 | Elasticsearch request timeout |
| `max_retries` | int | 3 | Maximum retry attempts |

## Dependencies

### REST API Handler
```bash
pip install requests
```

### Elasticsearch Handler
```bash
pip install elasticsearch
```

## Environment Variables

```python
import os

# REST API Configuration
extras = {
    "trace_type": "restapi",
    "api_url": os.getenv("REST_API_URL"),
    "api_key": os.getenv("REST_API_KEY"),
    "service_type": os.getenv("REST_SERVICE_TYPE", "generic"),
}

# Elasticsearch Configuration
extras = {
    "trace_type": "elasticsearch",
    "es_hosts": os.getenv("ES_HOSTS", "http://localhost:9200"),
    "username": os.getenv("ES_USERNAME"),
    "password": os.getenv("ES_PASSWORD"),
    "index_name": os.getenv("ES_INDEX", "workflow-traces"),
}
```

## Error Handling

```python
try:
    trace = get_trace(run_id="workflow-123", extras=extras)
    trace.info("Processing data")
except Exception as e:
    # Handle tracing errors gracefully
    fallback_logger.error(f"Tracing failed: {e}")
finally:
    if 'trace' in locals():
        trace.close()
```

## Performance Tuning

### High-Volume Logging

```python
# REST API - High volume
extras = {
    "trace_type": "restapi",
    "api_url": "https://api.example.com/logs",
    "buffer_size": 200,  # Larger buffer
    "timeout": 30.0,     # Longer timeout
}

# Elasticsearch - High volume
extras = {
    "trace_type": "elasticsearch",
    "es_hosts": "http://localhost:9200",
    "buffer_size": 500,  # Larger buffer
    "timeout": 60.0,     # Longer timeout
}
```

## Migration from Existing Handlers

### From File Tracing

```python
# Old
from ddeutil.workflow.traces import FileTrace
trace = FileTrace(url="file://./logs", run_id="workflow-123")

# New - REST API
trace = get_trace(run_id="workflow-123", extras={
    "trace_type": "restapi",
    "api_url": "https://api.example.com/logs",
    "service_type": "generic",
})

# New - Elasticsearch
trace = get_trace(run_id="workflow-123", extras={
    "trace_type": "elasticsearch",
    "es_hosts": "http://localhost:9200",
    "index_name": "workflow-traces",
})
```

### From SQLite Tracing

```python
# Old
from ddeutil.workflow.traces import SQLiteTrace
trace = SQLiteTrace(url="sqlite://./logs/traces.db", run_id="workflow-123")

# New - Elasticsearch (recommended replacement)
trace = get_trace(run_id="workflow-123", extras={
    "trace_type": "elasticsearch",
    "es_hosts": "http://localhost:9200",
    "index_name": "workflow-traces",
})
```

## Next Steps

For detailed information, see:

- [REST API Tracing Documentation](restapi-tracing.md)
- [Elasticsearch Tracing Documentation](elasticsearch-tracing.md)
- [Complete Examples](../examples/restapi_tracing_example.py)
- [Complete Examples](../examples/elasticsearch_tracing_example.py)

## Support

For issues and questions:

1. Check the detailed documentation
2. Review the example scripts
3. Enable debug logging for troubleshooting
4. Verify service connectivity and credentials
