# Quick Start Guide: Optimized Tracing System

## 🚀 Getting Started

The optimized tracing system provides 2-5x performance improvements over the traditional `FileTrace` model. Here's how to use it:

## Basic Usage

### 1. Simple Logging (Recommended)

```python
from ddeutil.workflow.traces import get_trace

# This automatically uses OptimizedFileTrace now
trace = get_trace("workflow-123", parent_run_id="parent-456")

# Standard logging interface
trace.info("Workflow started")
trace.warning("High memory usage")
trace.error("Database connection failed")

# Close when done (optional, but recommended)
trace.close()
```

### 2. With Context Information

```python
trace = get_trace(
    "workflow-123",
    extras={
        "enable_write_log": True,
        "workflow_name": "data-pipeline",
        "stage_name": "extract",
        "user_id": "data-engineer",
        "environment": "production"
    }
)

trace.info("Starting data extraction")
trace.info("Processing 10,000 records")
trace.warning("Found 50 records with missing values")
trace.info("Extraction completed")
```

### 3. Error Handling

```python
trace = get_trace("workflow-123")

try:
    trace.info("Starting risky operation")
    # ... your code here ...
    raise ValueError("Something went wrong")
except Exception as e:
    trace.error(f"Operation failed: {e}")
    trace.exception("Full exception details:")
finally:
    trace.info("Cleanup completed")
```

## Configuration

### Environment Variables

```bash
# Enable file logging
export WORKFLOW_LOG_TRACE_ENABLE_WRITE=true

# Set log directory
export WORKFLOW_LOG_TRACE_URL="file:./logs"

# Custom log format
export WORKFLOW_LOG_FORMAT_FILE="[{datetime}] [{level}] {message}"

# Timezone
export WORKFLOW_LOG_TIMEZONE="UTC"
```

### Programmatic Configuration

```python
import os

# Set configuration programmatically
os.environ["WORKFLOW_LOG_TRACE_ENABLE_WRITE"] = "true"
os.environ["WORKFLOW_LOG_TRACE_URL"] = "file:./my_logs"

# Then use get_trace()
trace = get_trace("workflow-123")
```

## Advanced Usage

### 1. Direct Handler Usage

```python
import logging
from ddeutil.workflow.traces import WorkflowFileHandler

# Create handler
handler = WorkflowFileHandler(
    run_id="my-workflow",
    base_path="./logs",
    buffer_size=8192,  # 8KB buffer
    extras={"workflow_name": "my-app"}
)

# Add to logger
logger = logging.getLogger("my_app")
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Use standard Python logging
logger.info("Application started")
logger.error("An error occurred")

# Cleanup
handler.close()
```

### 2. Async Logging

```python
import asyncio
from ddeutil.workflow.traces import get_trace

async def async_workflow():
    trace = get_trace("async-workflow-123")

    await trace.ainfo("Async workflow started")
    await trace.awarning("Processing batch 1")
    await trace.ainfo("Async workflow completed")

    trace.close()

# Run async workflow
asyncio.run(async_workflow())
```

### 3. Concurrent Logging

```python
import threading
from concurrent.futures import ThreadPoolExecutor
from ddeutil.workflow.traces import get_trace

def worker(worker_id):
    trace = get_trace(f"worker-{worker_id}")

    for i in range(10):
        trace.info(f"Worker {worker_id}: Processing item {i}")

    trace.close()

# Run multiple workers
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(worker, i) for i in range(4)]
    for future in futures:
        future.result()
```

## Performance Tips

### 1. Batch Operations

```python
trace = get_trace("batch-example")

# Log batch start
trace.info("Starting batch processing: 1000 items")

# Process items (don't log every single item)
for i in range(0, 1000, 100):
    # Process batch
    # ...

    # Log batch completion
    trace.info(f"Completed batch {i//100 + 1}/10")

trace.info("Batch processing completed")
```

### 2. Context Management

```python
from contextlib import contextmanager

@contextmanager
def workflow_trace(run_id, **extras):
    trace = get_trace(run_id, extras=extras)
    try:
        yield trace
    finally:
        trace.close()

# Usage
with workflow_trace("workflow-123", workflow_name="data-pipeline") as trace:
    trace.info("Workflow started")
    # ... your code ...
    trace.info("Workflow completed")
```

### 3. Custom Buffer Sizes

```python
from ddeutil.workflow.traces import WorkflowFileHandler

# For high-volume logging, use larger buffers
handler = WorkflowFileHandler(
    run_id="high-volume",
    buffer_size=16384,  # 16KB buffer
    flush_interval=0.5  # Flush every 500ms
)
```

## Migration from FileTrace

### Automatic Migration

If you're using `get_trace()`, you're already using the optimized version:

```python
# This now returns OptimizedFileTrace automatically
trace = get_trace("workflow-123")
```

### Manual Migration

If you were using `FileTrace` directly:

```python
# Old way
from ddeutil.workflow.traces import FileTrace
trace = FileTrace(url="file://./logs", run_id="123")

# New way (recommended)
from ddeutil.workflow.traces import OptimizedFileTrace
trace = OptimizedFileTrace(url="file://./logs", run_id="123")

# Or use get_trace() (best)
from ddeutil.workflow.traces import get_trace
trace = get_trace("123")
```

## File Structure

The optimized system creates the same file structure as the original:

```
./logs/
└── run_id=workflow-123/
    ├── stdout.txt      # Standard output logs
    ├── stderr.txt      # Error logs
    └── metadata.json   # Structured metadata
```

## Monitoring and Debugging

### Check Buffer Status

```python
handler = WorkflowFileHandler("test")
print(f"Buffer sizes: stdout={len(handler.stdout_buffer)}, "
      f"stderr={len(handler.stderr_buffer)}")
```

### Performance Monitoring

```python
import time

start_time = time.time()
trace = get_trace("performance-test")

for i in range(10000):
    trace.info(f"Log message {i}")

trace.close()
duration = time.time() - start_time
print(f"Logged 10,000 messages in {duration:.2f} seconds")
```

## Best Practices

1. **Always close traces** when done
2. **Use context managers** for automatic cleanup
3. **Configure buffer sizes** based on your logging volume
4. **Don't log every single operation** - batch when possible
5. **Use appropriate log levels** (DEBUG, INFO, WARNING, ERROR)
6. **Add context information** for better debugging
7. **Monitor performance** and adjust buffer sizes as needed

## Troubleshooting

### Common Issues

1. **Import errors**: Make sure you're running from the project root
2. **Permission errors**: Check write permissions to log directory
3. **Memory usage**: Reduce buffer size if memory is constrained
4. **Performance**: Increase buffer size for high-volume logging

### Debug Mode

```python
import logging
logging.getLogger("ddeutil.workflow.traces").setLevel(logging.DEBUG)
```

## Next Steps

- Read the [full documentation](docs/optimized-tracing.md)
- Run the [performance comparison](examples/performance_comparison.py)
- Try the [comprehensive examples](examples/tracing_usage_examples.py)
- Check the [simple examples](examples/simple_tracing_example.py)
