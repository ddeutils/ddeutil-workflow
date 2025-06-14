# Workflow API Reference

The Workflow module provides the core orchestration functionality for the workflow system. It manages job execution, scheduling, parameter handling, and provides comprehensive execution capabilities for complex workflows.

## Overview

The workflow system implements timeout strategy at the workflow execution layer because the main purpose is to use Workflow as an orchestrator for complex job execution scenarios. The system supports both immediate execution and scheduled execution via cron-like expressions.

## Classes

### Workflow

Main workflow orchestration model for job and schedule management.

The Workflow class is the core component of the workflow orchestration system. It manages job execution, scheduling via cron expressions, parameter handling, and provides comprehensive execution capabilities for complex workflows.

#### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `extras` | `dict` | `{}` | Extra parameters for overriding configuration values |
| `name` | `str` | - | Unique workflow identifier |
| `desc` | `str \| None` | `None` | Workflow description supporting markdown content |
| `params` | `dict[str, Param]` | `{}` | Parameter definitions for the workflow |
| `on` | `list[Crontab]` | `[]` | Schedule definitions using cron expressions |
| `jobs` | `dict[str, Job]` | `{}` | Collection of jobs within this workflow |

#### Methods

##### `from_conf(name, *, path=None, extras=None)`

Create Workflow instance from configuration file.

**Parameters:**
- `name` (str): Workflow name to load from configuration
- `path` (Path, optional): Optional custom configuration path to search
- `extras` (dict, optional): Additional parameters to override configuration values

**Returns:**
- `Workflow`: Validated Workflow instance loaded from configuration

**Raises:**
- `ValueError`: If workflow type doesn't match or configuration invalid
- `FileNotFoundError`: If workflow configuration file not found

##### `execute(params, *, run_id=None, parent_run_id=None, event=None, timeout=3600, max_job_parallel=2)`

Execute the workflow with provided parameters.

**Parameters:**
- `params` (dict): Parameter values for workflow execution
- `run_id` (str, optional): Unique identifier for this execution run
- `parent_run_id` (str, optional): Parent workflow run identifier
- `event` (Event, optional): Threading event for cancellation control
- `timeout` (float): Maximum execution time in seconds
- `max_job_parallel` (int): Maximum number of concurrent jobs

**Returns:**
- `Result`: Execution result with status and output data

##### `release(release, params, *, release_type='normal', run_id=None, parent_run_id=None, audit=None, override_log_name=None, result=None, timeout=600, excluded=None)`

Release workflow execution at specified datetime.

**Parameters:**
- `release` (datetime): Scheduled release datetime
- `params` (dict): Parameter values for execution
- `release_type` (ReleaseType): Type of release execution
- `run_id` (str, optional): Unique run identifier
- `parent_run_id` (str, optional): Parent run identifier
- `audit` (Audit, optional): Audit logging configuration
- `override_log_name` (str, optional): Custom log name override
- `result` (Result, optional): Pre-existing result context
- `timeout` (int): Execution timeout in seconds
- `excluded` (list[str], optional): Jobs to exclude from execution

**Returns:**
- `Result`: Release execution result

### ReleaseType

Release type enumeration for workflow execution modes.

#### Values

- `NORMAL`: Standard workflow release execution
- `RERUN`: Re-execution of previously failed workflow
- `EVENT`: Event-triggered workflow execution
- `FORCE`: Forced execution bypassing normal conditions

## Usage Examples

### Basic Workflow Creation and Execution

```python
from ddeutil.workflow import Workflow

# Load workflow from configuration
workflow = Workflow.from_conf('data-pipeline')

# Execute with parameters
result = workflow.execute({
    'input_path': '/data/input',
    'output_path': '/data/output',
    'processing_date': '2024-01-01'
})

if result.status == 'SUCCESS':
    print("Workflow completed successfully")
    print(f"Output: {result.context.get('outputs', {})}")
else:
    print(f"Workflow failed: {result.errors}")
```

### Workflow with Custom Configuration

```python
from pathlib import Path
from ddeutil.workflow import Workflow

# Load with custom path and extras
workflow = Workflow.from_conf(
    'data-pipeline',
    path=Path('./custom-configs'),
    extras={'environment': 'production'}
)

# Execute with timeout and job parallelism control
result = workflow.execute(
    params={'batch_size': 1000},
    timeout=1800,  # 30 minutes
    max_job_parallel=4
)
```

### Scheduled Workflow Execution

```python
from datetime import datetime
from ddeutil.workflow import Workflow, NORMAL

workflow = Workflow.from_conf('scheduled-pipeline')

# Schedule for specific time
release_time = datetime(2024, 1, 1, 9, 0, 0)
result = workflow.release(
    release=release_time,
    params={'mode': 'batch'},
    release_type=NORMAL,
    timeout=3600
)
```

### Error Handling

```python
from ddeutil.workflow import Workflow, WorkflowError

try:
    workflow = Workflow.from_conf('my-workflow')
    result = workflow.execute({'param1': 'value1'})

    if result.status == 'FAILED':
        for error in result.errors:
            print(f"Error in {error.name}: {error.message}")

except WorkflowError as e:
    print(f"Workflow execution error: {e}")
except FileNotFoundError:
    print("Workflow configuration file not found")
```

## YAML Configuration

### Basic Workflow Configuration

```yaml
my-workflow:
  type: Workflow
  desc: |
    Sample data processing workflow
    with multiple stages

  params:
    input_file:
      type: str
      description: Input file path
    environment:
      type: str
      default: development

  on:
    - cron: "0 9 * * 1-5"  # Weekdays at 9 AM
      timezone: "UTC"

  jobs:
    data-ingestion:
      runs-on:
        type: local
      stages:
        - name: "Download data"
          bash: |
            wget ${{ params.data_url }} -O /tmp/data.csv

        - name: "Validate data"
          run: |
            import pandas as pd
            df = pd.read_csv('/tmp/data.csv')
            assert len(df) > 0, "Data file is empty"

    data-processing:
      needs: [data-ingestion]
      strategy:
        matrix:
          env: [dev, staging, prod]
        max-parallel: 2
      stages:
        - name: "Process data for ${{ matrix.env }}"
          run: |
            process_data(env='${{ matrix.env }}')
```

### Advanced Configuration with Dependencies

```yaml
complex-workflow:
  type: Workflow

  params:
    start_date: datetime
    end_date: datetime
    batch_size:
      type: int
      default: 1000

  jobs:
    setup:
      stages:
        - name: "Initialize workspace"
          bash: mkdir -p /tmp/workflow-data

    parallel-processing:
      needs: [setup]
      strategy:
        matrix:
          region: [us-east, us-west, eu-central]
          shard: [1, 2, 3, 4]
        max-parallel: 4
        fail-fast: false

      stages:
        - name: "Process ${{ matrix.region }} shard ${{ matrix.shard }}"
          if: "${{ params.start_date }} < '${{ params.end_date }}'"
          run: |
            process_shard(
                region='${{ matrix.region }}',
                shard=${{ matrix.shard }},
                batch_size=${{ params.batch_size }}
            )

    cleanup:
      needs: [parallel-processing]
      trigger-rule: all_done  # Run even if some parallel jobs failed
      stages:
        - name: "Cleanup temporary files"
          bash: rm -rf /tmp/workflow-data
```

## Best Practices

### 1. Parameter Management

- Define clear parameter types and descriptions
- Use default values for optional parameters
- Validate parameters before execution

### 2. Error Handling

- Implement proper error handling in workflows
- Use appropriate trigger rules for job dependencies
- Monitor workflow execution results

### 3. Resource Management

- Set appropriate timeouts for long-running workflows
- Control job parallelism based on available resources
- Use conditional execution to optimize resource usage

### 4. Configuration Management

- Keep configuration files organized and version-controlled
- Use meaningful names for workflows and jobs
- Document workflow purpose and usage in descriptions

### 5. Monitoring and Logging

- Enable audit logging for production workflows
- Monitor workflow execution metrics
- Implement alerting for critical workflow failures
