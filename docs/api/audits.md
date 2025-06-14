# Audits

The Audits module provides metadata audit logging for workflow execution, tracking workflow releases, parameters, and execution results for compliance and monitoring.

## Overview

The audit system provides:

- **Execution tracking**: Complete workflow execution metadata
- **Release logging**: Detailed workflow release information
- **Parameter capture**: Input parameters and context data
- **Result persistence**: Execution outcomes and status tracking
- **Query capabilities**: Search and retrieve audit logs

## Base Classes

### `BaseAudit`

Abstract base class for all audit implementations providing core audit functionality.

!!! info "Key Features"
    - Workflow execution metadata capture
    - Release timestamp tracking
    - Context and parameter logging
    - Status and result persistence

## File-based Audits

### `FileAudit`

File-based audit implementation that persists audit logs to the local filesystem in JSON format.

!!! example "File Audit Usage"

    ```python
    from ddeutil.workflow.audits import FileAudit
    from datetime import datetime

    # Create audit log
    audit = FileAudit(
        name="data-pipeline",
        type="scheduled",
        release=datetime(2024, 1, 15, 10, 30),
        context={
            "params": {"source_table": "users", "target_env": "prod"},
            "jobs": {"extract": {"status": "SUCCESS"}}
        },
        run_id="workflow-123",
        parent_run_id=None,
        update=datetime.now()
    )

    # Save audit log
    audit.save()

    # Log is saved to:
    # {audit_path}/workflow=data-pipeline/release=20240115103000/workflow-123.log
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

    # Find all audits for a workflow
    for audit in FileAudit.find_audits("data-pipeline"):
        print(f"Release: {audit.release}")
        print(f"Run ID: {audit.run_id}")
        print(f"Status: {audit.context.get('status')}")
        print(f"Parameters: {audit.context.get('params')}")

    # Check if audit exists for specific release
    exists = FileAudit.is_pointed(
        name="data-pipeline",
        release=datetime(2024, 1, 15, 10, 30)
    )
    ```

#### Audit Log Format

Each audit log is stored as JSON with the following structure:

!!! example "Audit Log Content"

    ```json
    {
      "name": "data-pipeline",
      "type": "scheduled",
      "release": "2024-01-15T10:30:00",
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
      "run_id": "workflow-123",
      "parent_run_id": null,
      "update": "2024-01-15T10:40:25"
    }
    ```

## Audit Data Model

### Field Specifications

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | str | Yes | Workflow name |
| `type` | str | Yes | Execution type (scheduled, manual, event, rerun) |
| `release` | datetime | Yes | Workflow release timestamp |
| `context` | dict | Yes | Execution context including params and job results |
| `run_id` | str | Yes | Unique execution identifier |
| `parent_run_id` | str \| None | No | Parent workflow run ID for nested executions |
| `update` | datetime | Yes | Audit record update timestamp |

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

## Audit Factory

### `get_audit`

Factory function that returns the appropriate audit implementation based on configuration.

!!! example "Dynamic Audit Creation"

    ```python
    from ddeutil.workflow.audits import get_audit

    # Automatically selects appropriate audit implementation
    audit = get_audit(
        name="data-pipeline",
        type="scheduled",
        release=datetime.now(),
        run_id="workflow-123"
    )

    # Add execution context
    audit.context = {
        "params": {"env": "prod"},
        "jobs": {"job1": {"status": "SUCCESS"}}
    }

    # Save audit log
    audit.save()
    ```

## Integration with Workflows

Audits are automatically created and managed during workflow execution:

!!! example "Workflow Integration"

    ```python
    from ddeutil.workflow import Workflow

    # Load workflow
    workflow = Workflow.from_conf("data-pipeline")

    # Execute with audit logging
    result = workflow.release(
        release=datetime.now(),
        params={"source": "users", "target": "warehouse"},
        audit=FileAudit  # Specify audit implementation
    )

    # Audit log is automatically created with:
    # - Workflow execution metadata
    # - Input parameters
    # - Job execution results
    # - Final status and timing
    ```

## Configuration

Audit behavior is controlled by environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKFLOW_CORE_AUDIT_PATH` | `./logs/audits` | Path for audit file storage |
| `WORKFLOW_CORE_ENABLE_WRITE_AUDIT` | `false` | Enable/disable audit logging |
| `WORKFLOW_CORE_AUDIT_EXCLUDED` | `[]` | Fields to exclude from audit logs |

!!! example "Configuration"

    ```bash
    # Enable audit logging
    export WORKFLOW_CORE_ENABLE_WRITE_AUDIT=true

    # Set custom audit path
    export WORKFLOW_CORE_AUDIT_PATH=/var/log/workflow/audits

    # Exclude sensitive fields
    export WORKFLOW_CORE_AUDIT_EXCLUDED='["params.password", "context.secrets"]'
    ```

## Use Cases

### Compliance Monitoring

!!! example "Compliance Tracking"

    ```python
    # Query audits for compliance reporting
    for audit in FileAudit.find_audits("financial-etl"):
        if audit.release.date() == target_date:
            print(f"Execution: {audit.run_id}")
            print(f"Status: {audit.context['status']}")
            print(f"Duration: {audit.context.get('duration')}")
    ```

### Failure Analysis

!!! example "Error Investigation"

    ```python
    # Find failed workflow executions
    for audit in FileAudit.find_audits("data-pipeline"):
        if audit.context.get("status") == "FAILED":
            print(f"Failed run: {audit.run_id}")
            print(f"Error: {audit.context.get('errors')}")
            print(f"Failed jobs: {[j for j, data in audit.context['jobs'].items()
                                  if data['status'] == 'FAILED']}")
    ```

### Performance Monitoring

!!! example "Performance Analysis"

    ```python
    # Analyze workflow performance trends
    execution_times = []
    for audit in FileAudit.find_audits("etl-workflow"):
        start = audit.release
        end = audit.update
        duration = (end - start).total_seconds()
        execution_times.append(duration)

    avg_duration = sum(execution_times) / len(execution_times)
    print(f"Average execution time: {avg_duration:.2f} seconds")
    ```

!!! tip "Best Practices"

    - **Enable auditing in production** for compliance and monitoring
    - **Configure appropriate retention policies** for audit log cleanup
    - **Exclude sensitive data** from audit logs using configuration
    - **Use audit data for alerting** on workflow failures or performance degradation
    - **Regular audit log analysis** helps identify patterns and optimization opportunities
