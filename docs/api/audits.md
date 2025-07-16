# Audits

The Audits module provides comprehensive audit capabilities for workflow execution tracking and monitoring. It supports multiple audit backends for capturing execution metadata, status information, and detailed logging.

## Overview

The audit system provides:

- **Execution tracking**: Complete workflow execution metadata
- **Release logging**: Detailed workflow release information
- **Parameter capture**: Input parameters and context data
- **Result persistence**: Execution outcomes and status tracking
- **Query capabilities**: Search and retrieve audit logs
- **Multiple backends**: File-based JSON storage and SQLite database storage

!!! warning "Single Backend Limitation"
    You can set only one audit backend setting for the current run-time because it will conflict audit data if more than one audit backend pointer is set.

## Core Components

### `BaseAudit`

Abstract base class for all audit implementations providing core audit functionality.

!!! info "Key Features"
    - Workflow execution metadata capture
    - Release timestamp tracking
    - Context and parameter logging
    - Status and result persistence
    - Automatic configuration validation

### `AuditData`

Data model for audit information containing workflow execution details.

!!! example "AuditData Structure"

    ```python
    from ddeutil.workflow.audits import AuditData
    from datetime import datetime

    audit_data = AuditData(
        name="data-pipeline",
        release=datetime(2024, 1, 15, 10, 30),
        type="scheduled",
        context={
            "params": {"source_table": "users", "target_env": "prod"},
            "jobs": {"extract": {"status": "SUCCESS"}}
        },
        run_id="workflow-123",
        parent_run_id=None,
        runs_metadata={"execution_time": "300s", "memory_usage": "512MB"}
    )
    ```

## File-based Audits

### `FileAudit`

File-based audit implementation that persists audit logs to the local filesystem in JSON format.

!!! example "File Audit Usage"

    ```python
    from ddeutil.workflow.audits import FileAudit, AuditData
    from datetime import datetime

    # Create file audit instance
    audit = FileAudit(
        type="file",
        path="./audits",
        extras={"enable_write_audit": True}
    )

    # Create audit data
    data = AuditData(
        name="data-pipeline",
        release=datetime(2024, 1, 15, 10, 30),
        type="scheduled",
        context={
            "params": {"source_table": "users", "target_env": "prod"},
            "jobs": {"extract": {"status": "SUCCESS"}}
        },
        run_id="workflow-123",
        parent_run_id=None,
        runs_metadata={"execution_time": "300s"}
    )

    # Save audit log
    audit.save(data)

    # Log is saved to:
    # ./audits/workflow=data-pipeline/release=20240115103000/workflow-123.log
    ```

#### Audit File Structure

```
audits/
├── workflow=data-pipeline/
│   ├── release=20240115103000/
│   │   ├── workflow-123.log
│   │   └── workflow-124.log
│   └── release=20240116080000/
│       └── workflow-125.log
└── workflow=etl-process/
    └── release=20240115120000/
        └── workflow-126.log
```

#### Finding Audits

The `FileAudit` class provides utilities to search and retrieve audit logs.

!!! example "Audit Discovery"

    ```python
    from ddeutil.workflow.audits import FileAudit

    audit = FileAudit(type="file", path="./audits")

    # Find all audits for a workflow
    for audit_data in audit.find_audits("data-pipeline"):
        print(f"Release: {audit_data.release}")
        print(f"Run ID: {audit_data.run_id}")
        print(f"Type: {audit_data.type}")
        print(f"Context: {audit_data.context}")

    # Find specific audit by release
    audit_data = audit.find_audit_with_release(
        name="data-pipeline",
        release=datetime(2024, 1, 15, 10, 30)
    )

    # Check if audit exists for specific release
    exists = audit.is_pointed(
        data=audit_data
    )
    ```

#### Audit Log Format

Each audit log is stored as JSON with the following structure:

!!! example "Audit Log Content"

    ```json
    {
      "name": "data-pipeline",
      "release": "2024-01-15T10:30:00",
      "type": "scheduled",
      "context": {
        "params": {
          "source_table": "users",
          "target_env": "prod"
        },
        "jobs": {
          "extract": {
            "status": "SUCCESS",
            "start_time": "2024-01-15T10:30:05",
            "end_time": "2024-01-15T10:35:12"
          },
          "transform": {
            "status": "SUCCESS",
            "start_time": "2024-01-15T10:35:15",
            "end_time": "2024-01-15T10:40:22"
          }
        }
      },
      "parent_run_id": null,
      "run_id": "workflow-123",
      "runs_metadata": {
        "execution_time": "300s",
        "memory_usage": "512MB",
        "cpu_usage": "45%"
      }
    }
    ```

#### Cleanup Functionality

The `FileAudit` class provides cleanup functionality for old audit files:

!!! example "Audit Cleanup"

    ```python
    from ddeutil.workflow.audits import FileAudit

    audit = FileAudit(type="file", path="./audits")

    # Clean up audit files older than 180 days
    cleaned_count = audit.cleanup(max_age_days=180)
    print(f"Cleaned up {cleaned_count} old audit files")
    ```

## Database Audits

### `SQLiteAudit`

SQLite-based audit implementation for scalable logging with compression support.

!!! example "SQLite Audit Usage"

    ```python
    from ddeutil.workflow.audits import SQLiteAudit, AuditData
    from datetime import datetime

    # Create SQLite audit instance
    audit = SQLiteAudit(
        type="sqlite",
        path="./audits/workflow_audits.db",
        extras={"enable_write_audit": True}
    )

    # Create audit data
    data = AuditData(
        name="data-pipeline",
        release=datetime(2024, 1, 15, 10, 30),
        type="scheduled",
        context={
            "params": {"source_table": "users"},
            "jobs": {"extract": {"status": "SUCCESS"}}
        },
        run_id="workflow-123",
        runs_metadata={"execution_time": "300s"}
    )

    # Save audit log
    audit.save(data)

    # Traces are stored in SQLite with compression for efficiency
    ```

#### SQLite Schema

The SQLite audit creates a comprehensive table structure:

```sql
CREATE TABLE IF NOT EXISTS audits (
    workflow        TEXT NOT NULL,
    release         TEXT NOT NULL,
    type            TEXT NOT NULL,
    context         BLOB NOT NULL,
    parent_run_id   TEXT,
    run_id          TEXT NOT NULL,
    metadata        BLOB NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workflow, release)
)
```

#### Finding SQLite Audits

The `SQLiteAudit` class provides utilities to search and retrieve audit logs:

!!! example "SQLite Audit Discovery"

    ```python
    from ddeutil.workflow.audits import SQLiteAudit

    audit = SQLiteAudit(type="sqlite", path="./audits/workflow_audits.db")

    # Find all audits for a workflow
    for audit_data in audit.find_audits("data-pipeline"):
        print(f"Release: {audit_data.release}")
        print(f"Run ID: {audit_data.run_id}")
        print(f"Context: {audit_data.context}")

    # Find specific audit by release
    audit_data = audit.find_audit_with_release(
        name="data-pipeline",
        release=datetime(2024, 1, 15, 10, 30)
    )

    # Find latest audit for a workflow
    latest_audit = audit.find_audit_with_release(name="data-pipeline")
    ```

#### Compression Support

SQLite audit uses compression for efficient storage:

!!! example "Compression Features"

    ```python
    from ddeutil.workflow.audits import SQLiteAudit

    # Data is automatically compressed using zlib
    # Context and metadata are stored as compressed BLOB
    # This significantly reduces storage requirements for large audit logs
    ```

#### SQLite Cleanup

The `SQLiteAudit` class provides cleanup functionality for old audit records:

!!! example "SQLite Audit Cleanup"

    ```python
    from ddeutil.workflow.audits import SQLiteAudit

    audit = SQLiteAudit(type="sqlite", path="./audits/workflow_audits.db")

    # Clean up audit records older than 180 days
    cleaned_count = audit.cleanup(max_age_days=180)
    print(f"Cleaned up {cleaned_count} old audit records")
    ```

## Audit Data Model

### Field Specifications

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | str | Yes | Workflow name |
| `release` | datetime | Yes | Workflow release timestamp |
| `type` | str | Yes | Execution type (scheduled, manual, event, rerun) |
| `context` | DictData | No | Execution context including params and job results |
| `parent_run_id` | str \| None | No | Parent workflow run ID for nested executions |
| `run_id` | str | Yes | Unique execution identifier |
| `runs_metadata` | DictData | No | Additional metadata for tracking audit logs |

### Context Structure

The `context` field contains comprehensive execution information:

!!! example "Context Structure"

    ```python
    context = {
        "params": {
            # Input parameters passed to workflow
            "source_table": "users",
            "batch_date": "2024-01-15",
            "environment": "production"
        },
        "jobs": {
            # Results from each job execution
            "job_name": {
                "status": "SUCCESS|FAILED|SKIP|CANCEL",
                "start_time": "2024-01-15T10:30:00",
                "end_time": "2024-01-15T10:35:00",
                "stages": {
                    # Stage-level execution details
                    "stage_name": {
                        "status": "SUCCESS",
                        "output": {"key": "value"}
                    }
                }
            }
        },
        "status": "SUCCESS",  # Overall workflow status
        "errors": {           # Error information if failed
            "error_type": "WorkflowError",
            "message": "Error description"
        }
    }
    ```

## Factory Function

### `get_audit`

Factory function that returns the appropriate audit implementation based on configuration.

!!! example "Dynamic Audit Creation"

    ```python
    from ddeutil.workflow.audits import get_audit

    # Automatically selects appropriate audit implementation
    audit = get_audit(extras={"custom_config": "value"})

    # Configuration determines audit type:
    # - If audit_url points to file: FileAudit
    # - If audit_url points to database: SQLiteAudit
    ```

## Configuration

Audit behavior is controlled by configuration settings:

| Setting | Description |
|---------|-------------|
| `audit_conf` | Audit configuration including type and path |
| `enable_write_audit` | Enable/disable audit logging |
| `audit_url` | URL/path for audit storage |

!!! example "Configuration"

    ```python
    # Enable audit logging
    extras = {"enable_write_audit": True}

    # File-based audit
    audit_conf = {
        "type": "file",
        "path": "./audits"
    }

    # SQLite-based audit
    audit_conf = {
        "type": "sqlite",
        "path": "./audits/workflow_audits.db"
    }
    ```

## Integration with Workflows

Audits are automatically created and managed during workflow execution:

!!! example "Workflow Integration"

    ```python
    from ddeutil.workflow import Workflow
    from ddeutil.workflow.audits import get_audit

    # Load workflow
    workflow = Workflow.from_conf("data-pipeline")

    # Get audit instance
    audit = get_audit(extras={"enable_write_audit": True})

    # Execute with audit logging
    result = workflow.release(
        release=datetime.now(),
        params={"source": "users", "target": "warehouse"}
    )

    # Audit log is automatically created with:
    # - Workflow execution metadata
    # - Input parameters
    # - Job execution results
    # - Final status and timing
    ```

## Use Cases

### Compliance Monitoring

!!! example "Compliance Tracking"

    ```python
    from ddeutil.workflow.audits import FileAudit

    audit = FileAudit(type="file", path="./audits")

    # Query audits for compliance reporting
    for audit_data in audit.find_audits("financial-etl"):
        if audit_data.release.date() == target_date:
            print(f"Execution: {audit_data.run_id}")
            print(f"Status: {audit_data.context.get('status')}")
            print(f"Parameters: {audit_data.context.get('params')}")
    ```

### Failure Analysis

!!! example "Error Investigation"

    ```python
    from ddeutil.workflow.audits import SQLiteAudit

    audit = SQLiteAudit(type="sqlite", path="./audits/workflow_audits.db")

    # Find failed workflow executions
    for audit_data in audit.find_audits("data-pipeline"):
        if audit_data.context.get("status") == "FAILED":
            print(f"Failed run: {audit_data.run_id}")
            print(f"Error: {audit_data.context.get('errors')}")
            print(f"Failed jobs: {[j for j, data in audit_data.context['jobs'].items()
                                  if data['status'] == 'FAILED']}")
    ```

### Performance Monitoring

!!! example "Performance Analysis"

    ```python
    from ddeutil.workflow.audits import FileAudit
    from datetime import datetime

    audit = FileAudit(type="file", path="./audits")

    # Analyze workflow performance trends
    execution_times = []
    for audit_data in audit.find_audits("etl-workflow"):
        start = audit_data.release
        # Calculate duration from metadata or context
        duration = audit_data.runs_metadata.get("execution_time", "0s")
        execution_times.append(duration)

    print(f"Total executions: {len(execution_times)}")
    ```

!!! tip "Best Practices"

    - **Enable auditing in production** for compliance and monitoring
    - **Configure appropriate retention policies** for audit log cleanup
    - **Use SQLite for high-volume deployments** with compression benefits
    - **Use file-based audit for simple deployments** with easy file access
    - **Regular audit log analysis** helps identify patterns and optimization opportunities
    - **Monitor audit storage usage** and implement cleanup schedules
