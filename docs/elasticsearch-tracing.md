# Elasticsearch Tracing System

The Elasticsearch tracing system provides scalable, searchable log storage and aggregation capabilities. It offers high-performance bulk indexing, rich querying capabilities, and distributed search across Elasticsearch clusters.

## Overview

The Elasticsearch tracing system consists of:

- **ElasticsearchHandler**: High-performance logging handler for Elasticsearch
- **ElasticsearchTrace**: Trace class that uses the Elasticsearch handler
- Bulk indexing for optimal performance
- Rich search and query capabilities
- Index management and mapping
- Cluster support with connection pooling

## Architecture

```
┌─────────────────┐    ┌────────────────────┐    ┌──────────────────┐
│   Workflow      │───▶│ ElasticsearchTrace │───▶│ElasticsearchHandler│
│   Execution     │    │                    │    │                  │
└─────────────────┘    └────────────────────┘    └──────────────────┘
                                                           │
                                                           ▼
                                              ┌────────────────────┐
                                              │   Elasticsearch    │
                                              │   Cluster          │
                                              │   (Single Node or  │
                                              │    Multi-Node)     │
                                              └────────────────────┘
```

## Features

### Core Features

- **Bulk Indexing**: High-performance batch operations
- **Rich Metadata**: Comprehensive trace metadata storage
- **Search Capabilities**: Full-text search and filtering
- **Index Management**: Automatic index creation and mapping
- **Cluster Support**: Multi-node Elasticsearch cluster support
- **Connection Pooling**: Efficient connection management
- **Retry Logic**: Robust error handling with retries

### Metadata Fields

The system stores rich metadata for each log entry:

```json
{
  "run_id": "workflow-123",
  "parent_run_id": "parent-456",
  "level": "info",
  "message": "Processing data",
  "mode": "stdout",
  "datetime": "2024-01-01T12:00:00",
  "process": 12345,
  "thread": 67890,
  "filename": "workflow.py",
  "lineno": 42,
  "cut_id": "workflow-123",
  "workflow_name": "data-pipeline",
  "stage_name": "validation",
  "job_name": "validate-data",
  "duration_ms": 150.5,
  "memory_usage_mb": 256.0,
  "cpu_usage_percent": 25.5,
  "trace_id": "trace-123",
  "span_id": "span-456",
  "parent_span_id": "parent-span-789",
  "exception_type": "ValueError",
  "exception_message": "Invalid data",
  "stack_trace": "...",
  "error_code": "VALIDATION_ERROR",
  "user_id": "user-123",
  "tenant_id": "tenant-456",
  "environment": "production",
  "hostname": "server-01",
  "ip_address": "192.168.1.100",
  "python_version": "3.9.0",
  "package_version": "1.2.3",
  "tags": ["service:workflow", "team:data"],
  "metadata": {"custom_field": "value"},
  "created_at": "2024-01-01T12:00:00"
}
```

## Usage

### Basic Usage

```python
from ddeutil.workflow.traces import get_trace

# Configure Elasticsearch tracing
extras = {
    "trace_type": "elasticsearch",
    "es_hosts": "http://localhost:9200",
    "index_name": "workflow-traces",
    "username": "elastic",
    "password": "changeme",
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

# Create trace instance
trace = get_trace(
    run_id="workflow-123",
    parent_run_id="parent-456",
    extras=extras
)

# Log messages
trace.info("🚀 Starting data processing workflow")
trace.debug("📊 Initializing data validation stage")
trace.warning("⚠️ Warning message")
trace.error("❌ Error occurred")

# Close trace
trace.close()
```

### Cluster Configuration

```python
# Multi-node Elasticsearch cluster
extras = {
    "trace_type": "elasticsearch",
    "es_hosts": [
        "http://es-node1:9200",
        "http://es-node2:9200",
        "http://es-node3:9200"
    ],
    "index_name": "workflow-traces-cluster",
    "username": "elastic",
    "password": "changeme",
    "workflow_name": "distributed-workflow",
}
```

### Direct Handler Usage

```python
from ddeutil.workflow.traces import ElasticsearchHandler
import logging

# Create handler directly
handler = ElasticsearchHandler(
    run_id="direct-123",
    es_hosts="http://localhost:9200",
    index_name="direct-handler-test",
    username="elastic",
    password="changeme",
    buffer_size=50,
    timeout=30.0,
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
        "trace_type": "elasticsearch",
        "es_hosts": "http://localhost:9200",
        "index_name": "async-traces",
        "username": "elastic",
        "password": "changeme",
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
| `es_hosts` | str/list | "http://localhost:9200" | Elasticsearch host(s) |
| `index_name` | str | "workflow-traces" | Elasticsearch index name |
| `username` | str | None | Elasticsearch username |
| `password` | str | None | Elasticsearch password |
| `buffer_size` | int | 100 | Number of records to buffer before indexing |
| `flush_interval` | float | 2.0 | Interval in seconds to flush buffers |
| `timeout` | float | 30.0 | Elasticsearch request timeout in seconds |
| `max_retries` | int | 3 | Maximum number of retry attempts |

### Index Mapping

The system automatically creates an optimized index mapping:

```json
{
  "mappings": {
    "properties": {
      "run_id": {"type": "keyword"},
      "parent_run_id": {"type": "keyword"},
      "level": {"type": "keyword"},
      "message": {"type": "text"},
      "mode": {"type": "keyword"},
      "datetime": {"type": "date"},
      "process": {"type": "integer"},
      "thread": {"type": "integer"},
      "filename": {"type": "keyword"},
      "lineno": {"type": "integer"},
      "cut_id": {"type": "keyword"},
      "workflow_name": {"type": "keyword"},
      "stage_name": {"type": "keyword"},
      "job_name": {"type": "keyword"},
      "duration_ms": {"type": "float"},
      "memory_usage_mb": {"type": "float"},
      "cpu_usage_percent": {"type": "float"},
      "trace_id": {"type": "keyword"},
      "span_id": {"type": "keyword"},
      "parent_span_id": {"type": "keyword"},
      "exception_type": {"type": "keyword"},
      "exception_message": {"type": "text"},
      "stack_trace": {"type": "text"},
      "error_code": {"type": "keyword"},
      "user_id": {"type": "keyword"},
      "tenant_id": {"type": "keyword"},
      "environment": {"type": "keyword"},
      "hostname": {"type": "keyword"},
      "ip_address": {"type": "ip"},
      "python_version": {"type": "keyword"},
      "package_version": {"type": "keyword"},
      "tags": {"type": "keyword"},
      "metadata": {"type": "object"},
      "created_at": {"type": "date"}
    }
  },
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "refresh_interval": "1s"
  }
}
```

## Search and Query Capabilities

### Finding Traces

```python
from ddeutil.workflow.traces import ElasticsearchTrace

# Find all traces
traces = list(ElasticsearchTrace.find_traces(extras=extras))
print(f"Found {len(traces)} trace sessions")

# Find specific trace by run ID
specific_trace = ElasticsearchTrace.find_trace_with_id(
    run_id="workflow-123",
    extras=extras
)
print(f"Found trace with {len(specific_trace.meta)} log entries")
```

### Direct Elasticsearch Queries

```python
from elasticsearch import Elasticsearch

# Create client
client = Elasticsearch(
    hosts=["http://localhost:9200"],
    basic_auth=("elastic", "changeme")
)

# Search for specific workflow
search_body = {
    "query": {
        "bool": {
            "must": [
                {"term": {"workflow_name": "data-pipeline"}},
                {"range": {"created_at": {"gte": "2024-01-01"}}}
            ]
        }
    },
    "sort": [{"created_at": {"order": "desc"}}],
    "size": 100
}

response = client.search(index="workflow-traces", body=search_body)
for hit in response["hits"]["hits"]:
    print(f"Log: {hit['_source']['message']}")
```

### Advanced Queries

```python
# Find error logs
error_query = {
    "query": {
        "bool": {
            "must": [
                {"term": {"level": "error"}},
                {"range": {"created_at": {"gte": "now-1d"}}}
            ]
        }
    }
}

# Find logs by user
user_query = {
    "query": {
        "term": {"user_id": "user-123"}
    }
}

# Find logs with specific tags
tag_query = {
    "query": {
        "terms": {"tags": ["service:workflow", "team:data"]}
    }
}

# Aggregation queries
agg_query = {
    "size": 0,
    "aggs": {
        "workflows": {
            "terms": {"field": "workflow_name"},
            "aggs": {
                "error_count": {
                    "filter": {"term": {"level": "error"}}
                }
            }
        }
    }
}
```

## Performance Optimization

### Bulk Indexing

The handler uses bulk indexing for optimal performance:

```python
# Bulk operations format
bulk_data = [
    {"index": {"_index": "workflow-traces", "_id": "doc-1"}},
    {"run_id": "workflow-123", "message": "Log message 1"},
    {"index": {"_index": "workflow-traces", "_id": "doc-2"}},
    {"run_id": "workflow-123", "message": "Log message 2"},
]

# Execute bulk indexing
response = client.bulk(body=bulk_data, refresh=True)
```

### Buffering Strategy

1. **Buffer Size**: Configurable buffer size (default: 100 records)
2. **Flush Triggers**:
   - Buffer full
   - Manual flush
   - Handler close
3. **Batch Indexing**: Multiple records indexed in single bulk operation

### Performance Tuning

```python
# High-volume logging configuration
extras = {
    "trace_type": "elasticsearch",
    "es_hosts": "http://localhost:9200",
    "index_name": "high-volume-traces",
    "buffer_size": 500,  # Larger buffer
    "flush_interval": 5.0,  # Longer interval
    "timeout": 60.0,  # Longer timeout
}
```

## Index Management

### Automatic Index Creation

The handler automatically creates indices with proper mapping:

```python
# Index creation with mapping
mapping = {
    "mappings": {
        "properties": {
            # ... field definitions
        }
    },
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "refresh_interval": "1s"
    }
}

client.indices.create(index="workflow-traces", body=mapping)
```

### Index Management Commands

```python
from elasticsearch import Elasticsearch

client = Elasticsearch(hosts=["http://localhost:9200"])

# List indices
indices = client.cat.indices(format="json")
for idx in indices:
    print(f"Index: {idx['index']}, Docs: {idx['docs.count']}")

# Get index mapping
mapping = client.indices.get_mapping(index="workflow-traces")

# Update index settings
client.indices.put_settings(
    index="workflow-traces",
    body={"refresh_interval": "5s"}
)

# Delete index (be careful!)
# client.indices.delete(index="workflow-traces")
```

## Error Handling

### Common Error Scenarios

1. **Connection Errors**: Automatic retry with exponential backoff
2. **Authentication Errors**: Proper error reporting
3. **Index Errors**: Automatic index creation and mapping
4. **Bulk Errors**: Individual record error reporting

### Error Recovery

```python
try:
    trace.info("Processing data")
except Exception as e:
    # Handler automatically retries on connection errors
    # Index errors trigger automatic index creation
    logger.error(f"Tracing error: {e}")
```

## Monitoring and Debugging

### Performance Metrics

```python
# Monitor handler performance
handler = ElasticsearchHandler(...)

# Check buffer status
print(f"Buffer size: {len(handler.log_buffer)}")

# Force flush
handler.flush()

# Check connection status
print(f"Client active: {handler.client is not None}")
```

### Debug Logging

Enable debug logging to monitor handler operations:

```python
import logging
logging.getLogger("ddeutil.workflow").setLevel(logging.DEBUG)
```

### Health Checks

```python
from elasticsearch import Elasticsearch

client = Elasticsearch(hosts=["http://localhost:9200"])

# Check cluster health
health = client.cluster.health()
print(f"Cluster status: {health['status']}")

# Check index health
index_health = client.cat.health(format="json")
for node in index_health:
    print(f"Node: {node['node']}, Status: {node['status']}")
```

## Best Practices

### 1. Configuration Management

```python
# Use environment variables for sensitive data
import os

extras = {
    "trace_type": "elasticsearch",
    "es_hosts": os.getenv("ES_HOSTS", "http://localhost:9200"),
    "username": os.getenv("ES_USERNAME"),
    "password": os.getenv("ES_PASSWORD"),
    "index_name": os.getenv("ES_INDEX", "workflow-traces"),
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

### 3. Index Naming

```python
# Use time-based index names for better management
from datetime import datetime

index_name = f"workflow-traces-{datetime.now().strftime('%Y.%m.%d')}"
extras = {
    "trace_type": "elasticsearch",
    "index_name": index_name,
}
```

### 4. Performance Tuning

```python
# Adjust settings based on workload
extras = {
    "trace_type": "elasticsearch",
    "buffer_size": 200,  # Larger buffer for high volume
    "flush_interval": 10.0,  # Longer interval for batch processing
    "timeout": 60.0,  # Longer timeout for bulk operations
}
```

### 5. Security

```python
# Use TLS for production
extras = {
    "trace_type": "elasticsearch",
    "es_hosts": "https://es-cluster:9200",
    "username": "elastic",
    "password": "secure-password",
    # Additional security options
    "verify_certs": True,
    "ca_certs": "/path/to/ca.crt",
}
```

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

# New Elasticsearch approach
from ddeutil.workflow.traces import get_trace

trace = get_trace(
    run_id="workflow-123",
    extras={
        "trace_type": "elasticsearch",
        "es_hosts": "http://localhost:9200",
        "index_name": "workflow-traces",
    }
)
```

### From SQLite Tracing

```python
# Old SQLite approach
from ddeutil.workflow.traces import SQLiteTrace

trace = SQLiteTrace(
    url="sqlite://./logs/traces.db",
    run_id="workflow-123",
    extras={}
)

# New Elasticsearch approach
trace = get_trace(
    run_id="workflow-123",
    extras={
        "trace_type": "elasticsearch",
        "es_hosts": "http://localhost:9200",
        "index_name": "workflow-traces",
    }
)
```

## Troubleshooting

### Common Issues

1. **Connection Timeouts**
   - Increase timeout value
   - Check network connectivity
   - Verify Elasticsearch is running

2. **Authentication Errors**
   - Verify username/password
   - Check Elasticsearch security settings
   - Ensure proper permissions

3. **Index Errors**
   - Check index permissions
   - Verify mapping compatibility
   - Monitor disk space

4. **Performance Issues**
   - Adjust buffer size
   - Increase flush interval
   - Monitor cluster resources

### Debug Commands

```python
# Enable detailed logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Test connection
handler = ElasticsearchHandler(...)
handler.flush()  # Force send to test connectivity

# Check index status
client = handler.client
print(client.indices.exists(index="workflow-traces"))
```

## Examples

See the complete examples in `examples/elasticsearch_tracing_example.py` for:

- Basic Elasticsearch integration
- Cluster configuration
- Direct handler usage
- Search and query capabilities
- Performance comparison
- Context-aware logging
- Async logging
- Index management
- Bulk operations

## Dependencies

Required packages:
- `elasticsearch` - Elasticsearch Python client

Install dependencies:
```bash
pip install elasticsearch
```

## API Reference

### ElasticsearchHandler

**Constructor:**
```python
ElasticsearchHandler(
    run_id: str,
    parent_run_id: Optional[str] = None,
    es_hosts: Union[str, list[str]] = "http://localhost:9200",
    index_name: str = "workflow-traces",
    username: Optional[str] = None,
    password: Optional[str] = None,
    extras: Optional[DictData] = None,
    buffer_size: int = 100,
    flush_interval: float = 2.0,
    timeout: float = 30.0,
    max_retries: int = 3,
)
```

**Methods:**
- `emit(record)`: Process log record
- `flush()`: Flush buffered records
- `close()`: Close handler and cleanup
- `find_traces()`: Find all traces (class method)
- `find_trace_with_id()`: Find specific trace (class method)

### ElasticsearchTrace

**Constructor:**
```python
ElasticsearchTrace(
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
- `find_traces()`: Find all traces (class method)
- `find_trace_with_id()`: Find specific trace (class method)
