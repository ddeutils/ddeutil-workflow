# SQLite Tracing System

## Overview

The SQLite tracing system provides database-backed logging for workflow traces, offering better performance, queryability, and scalability compared to file-based logging. It uses a custom `SQLiteHandler` that writes structured log data to SQLite databases.

## Key Features

- **Database-backed storage**: All logs stored in SQLite database
- **High performance**: Buffered writes with connection pooling
- **Thread safety**: Built-in locking for concurrent access
- **Rich metadata**: Comprehensive context and metadata storage
- **Queryable**: Direct SQL queries for log analysis
- **Scalable**: Efficient indexing and batch operations

## Architecture

### SQLiteHandler

A custom Python logging handler that:
- Buffers log records for batch insertion
- Manages SQLite connections efficiently
- Provides thread-safe operations
- Stores rich metadata in structured format

### SQLiteTrace

A trace class that:
- Uses `SQLiteHandler` internally
- Maintains the same API as other trace classes
- Provides database-specific query methods
- Handles connection management automatically

## Database Schema

The system creates a `traces` table with the following structure:

```sql
CREATE TABLE traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    parent_run_id TEXT,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    mode TEXT NOT NULL,
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
);
```

### Indexes

The system automatically creates indexes for better performance:

- `idx_traces_run_id`: For querying by run ID
- `idx_traces_parent_run_id`: For querying by parent run ID
- `idx_traces_datetime`: For time-based queries
- `idx_traces_level`: For level-based filtering

## Usage

### Basic Usage

```python
from ddeutil.workflow.traces import get_trace

# Set SQLite URL in environment
import os
os.environ["WORKFLOW_LOG_TRACE_ENABLE_WRITE"] = "true"
os.environ["WORKFLOW_LOG_TRACE_URL"] = "sqlite:./logs/workflow_traces.db"

# This automatically uses SQLiteTrace when URL scheme is "sqlite"
trace = get_trace("workflow-123", parent_run_id="parent-456")

# Standard logging interface
trace.info("Workflow started")
trace.warning("High memory usage")
trace.error("Database connection failed")

# Close when done
trace.close()
```

### Direct SQLiteTrace Usage

```python
from ddeutil.workflow.traces import SQLiteTrace
from urllib.parse import urlparse

# Create SQLite trace directly
trace = SQLiteTrace(
    url=urlparse("sqlite:./logs/custom_traces.db"),
    run_id="direct-example",
    extras={
        "enable_write_log": True,
        "workflow_name": "etl-pipeline",
        "stage_name": "transform",
        "user_id": "data-engineer"
    }
)

trace.info("ETL Pipeline: Starting extraction phase")
trace.warning("Found 50 records with missing values")
trace.info("ETL Pipeline completed successfully")

trace.close()
```

### Direct Handler Usage

```python
import logging
from ddeutil.workflow.traces import SQLiteHandler
from pathlib import Path

# Create a custom logger
logger = logging.getLogger("my_sqlite_app")
logger.setLevel(logging.DEBUG)

# Create and configure the SQLite handler
handler = SQLiteHandler(
    run_id="direct-handler-example",
    db_path=Path("./logs/handler_traces.db"),
    buffer_size=50,  # Buffer 50 records before writing
    extras={
        "workflow_name": "data-pipeline",
        "environment": "production"
    }
)

# Add the handler to the logger
logger.addHandler(handler)

# Use standard Python logging
logger.info("Data pipeline started")
logger.error("Critical error in data processing")

# Cleanup
handler.close()
```

## Configuration

### Environment Variables

```bash
# Enable SQLite logging
export WORKFLOW_LOG_TRACE_ENABLE_WRITE=true

# Set SQLite database URL
export WORKFLOW_LOG_TRACE_URL="sqlite:./logs/workflow_traces.db"

# Custom log format (for display purposes)
export WORKFLOW_LOG_FORMAT_FILE="[{datetime}] [{level}] {message}"
```

### Handler Configuration

```python
handler = SQLiteHandler(
    run_id="my-workflow",
    db_path="./logs/custom.db",  # Database file path
    buffer_size=100,             # Records to buffer before writing
    flush_interval=1.0,          # Flush interval in seconds
    extras={
        "workflow_name": "my-app",
        "environment": "production"
    }
)
```

## Querying Logs

### Using find_traces()

```python
from ddeutil.workflow.traces import SQLiteTrace

# Get all traces from database
traces = list(SQLiteTrace.find_traces())
for trace_data in traces:
    print(f"Run ID: {trace_data.meta[0].run_id if trace_data.meta else 'Unknown'}")
    print(f"Messages: {len(trace_data.meta)}")
```

### Using find_trace_with_id()

```python
# Find specific trace by run ID
specific_trace = SQLiteTrace.find_trace_with_id("workflow-123")
print(f"Found trace with {len(specific_trace.meta)} messages")
for meta in specific_trace.meta:
    print(f"[{meta.level}] {meta.message}")
```

### Direct SQL Queries

```python
import sqlite3
from pathlib import Path

db_path = Path("./logs/workflow_traces.db")

with sqlite3.connect(db_path) as conn:
    cursor = conn.cursor()

    # Get all logs for a specific run
    cursor.execute("""
        SELECT level, message, datetime, workflow_name, user_id
        FROM traces
        WHERE run_id = 'workflow-123'
        ORDER BY created_at
    """)

    for row in cursor.fetchall():
        level, message, datetime, workflow_name, user_id = row
        print(f"[{level.upper()}] {datetime} | {message}")

    # Get statistics
    cursor.execute("""
        SELECT
            COUNT(*) as total_logs,
            COUNT(CASE WHEN level = 'error' THEN 1 END) as errors,
            COUNT(CASE WHEN level = 'warning' THEN 1 END) as warnings
        FROM traces
        WHERE run_id = 'workflow-123'
    """)

    stats = cursor.fetchone()
    print(f"Total: {stats[0]}, Errors: {stats[1]}, Warnings: {stats[2]}")
```

## Advanced Queries

### Error Analysis

```sql
-- Find all errors in the last 24 hours
SELECT run_id, message, datetime, workflow_name, user_id
FROM traces
WHERE level = 'error'
  AND datetime >= datetime('now', '-1 day')
ORDER BY datetime DESC;
```

### Performance Analysis

```sql
-- Find slow workflows
SELECT
    run_id,
    workflow_name,
    COUNT(*) as message_count,
    MIN(datetime) as start_time,
    MAX(datetime) as end_time,
    (julianday(MAX(datetime)) - julianday(MIN(datetime))) * 24 * 60 * 60 as duration_seconds
FROM traces
GROUP BY run_id
HAVING duration_seconds > 300  -- More than 5 minutes
ORDER BY duration_seconds DESC;
```

### User Activity

```sql
-- User activity summary
SELECT
    user_id,
    COUNT(DISTINCT run_id) as workflow_count,
    COUNT(*) as total_messages,
    COUNT(CASE WHEN level = 'error' THEN 1 END) as error_count
FROM traces
WHERE user_id IS NOT NULL
GROUP BY user_id
ORDER BY workflow_count DESC;
```

## Performance Optimization

### Buffer Configuration

```python
# For high-volume logging
handler = SQLiteHandler(
    run_id="high-volume",
    buffer_size=500,      # Larger buffer for batch operations
    flush_interval=0.5    # More frequent flushes
)

# For low-volume logging
handler = SQLiteHandler(
    run_id="low-volume",
    buffer_size=10,       # Smaller buffer for immediate writes
    flush_interval=5.0    # Less frequent flushes
)
```

### Database Optimization

```sql
-- Analyze table for better query planning
ANALYZE traces;

-- Vacuum database to reclaim space
VACUUM;

-- Reindex for better performance
REINDEX;
```

## Migration from File-based Logging

### Automatic Migration

If you're using `get_trace()`, simply change the URL scheme:

```python
# Old: File-based
os.environ["WORKFLOW_LOG_TRACE_URL"] = "file:./logs"

# New: SQLite-based
os.environ["WORKFLOW_LOG_TRACE_URL"] = "sqlite:./logs/workflow_traces.db"

# Same code works
trace = get_trace("workflow-123")
```

### Manual Migration

```python
# Old way
from ddeutil.workflow.traces import FileTrace
trace = FileTrace(url="file://./logs", run_id="123")

# New way
from ddeutil.workflow.traces import SQLiteTrace
trace = SQLiteTrace(url="sqlite://./logs/traces.db", run_id="123")
```

## Best Practices

### 1. Database Management

- **Regular maintenance**: Run `VACUUM` and `ANALYZE` periodically
- **Backup strategy**: Implement regular database backups
- **Size monitoring**: Monitor database file size and growth
- **Connection pooling**: Let the handler manage connections

### 2. Performance

- **Buffer sizing**: Adjust buffer size based on logging volume
- **Index usage**: Use indexed columns in queries
- **Batch operations**: Leverage the built-in buffering
- **Query optimization**: Use appropriate WHERE clauses

### 3. Monitoring

```python
# Monitor buffer status
handler = SQLiteHandler("test")
print(f"Buffer size: {len(handler.log_buffer)}")

# Monitor database size
db_path = Path("./logs/workflow_traces.db")
if db_path.exists():
    size_mb = db_path.stat().st_size / (1024 * 1024)
    print(f"Database size: {size_mb:.2f} MB")
```

### 4. Error Handling

```python
try:
    trace = get_trace("workflow-123")
    trace.info("Starting workflow")
    # ... your code ...
except Exception as e:
    trace.error(f"Workflow failed: {e}")
    trace.exception("Full exception details:")
finally:
    trace.close()
```

## Troubleshooting

### Common Issues

1. **Permission errors**: Ensure write permissions to database directory
2. **Disk space**: Monitor available disk space
3. **Lock errors**: Check for concurrent access issues
4. **Performance**: Adjust buffer size and flush interval

### Debug Mode

```python
import logging
logging.getLogger("ddeutil.workflow.traces").setLevel(logging.DEBUG)
```

### Database Inspection

```bash
# Connect to database
sqlite3 ./logs/workflow_traces.db

# Check table structure
.schema traces

# Check indexes
.indices traces

# Sample data
SELECT * FROM traces LIMIT 5;

# Check database size
SELECT page_count * page_size as size_bytes FROM pragma_page_count(), pragma_page_size();
```

## Comparison with File-based Logging

| Aspect | File-based | SQLite-based |
|--------|------------|--------------|
| Storage | Text files | Database |
| Querying | Manual parsing | SQL queries |
| Performance | Good for small volumes | Excellent for large volumes |
| Concurrent access | Limited | Full support |
| Metadata | Limited | Rich structured data |
| Scalability | File system limits | Database optimization |
| Maintenance | Manual file management | Database tools |

## Future Enhancements

- **Compression**: Automatic database compression
- **Partitioning**: Time-based table partitioning
- **Replication**: Database replication for high availability
- **Metrics**: Built-in performance metrics collection
- **Archiving**: Automatic log archiving and cleanup
