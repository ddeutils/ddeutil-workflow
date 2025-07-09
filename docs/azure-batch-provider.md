# Azure Batch Provider

The Azure Batch provider enables workflow job execution on Azure Batch compute nodes, providing scalable and managed execution environments for complex workflow processing.

## Overview

The Azure Batch provider handles the complete lifecycle of Azure Batch operations including:

- **Pool Management**: Automatic creation and management of Azure Batch pools
- **Job Submission**: Creating and submitting jobs to Azure Batch
- **Task Execution**: Running workflow tasks on compute nodes
- **File Management**: Uploading/downloading files via Azure Storage
- **Result Retrieval**: Collecting execution results and outputs
- **Resource Cleanup**: Automatic cleanup of Azure Batch resources

## Installation

Install the Azure Batch provider with optional dependencies:

```bash
pip install ddeutil-workflow[azure]
```

This installs the required Azure SDK packages:
- `azure-batch>=13.0.0`
- `azure-storage-blob>=12.0.0`

## Configuration

### Azure Batch Account Setup

1. Create an Azure Batch account in the Azure portal
2. Create an Azure Storage account for file management
3. Note down the following credentials:
   - Batch account name
   - Batch account key
   - Batch account URL
   - Storage account name
   - Storage account key

### Environment Variables

Set the following environment variables:

```bash
export AZURE_BATCH_ACCOUNT_NAME="your-batch-account"
export AZURE_BATCH_ACCOUNT_KEY="your-batch-key"
export AZURE_BATCH_ACCOUNT_URL="https://your-batch-account.region.batch.azure.com"
export AZURE_STORAGE_ACCOUNT_NAME="your-storage-account"
export AZURE_STORAGE_ACCOUNT_KEY="your-storage-key"
```

## Usage

### Basic Configuration

Configure a job to run on Azure Batch:

```yaml
jobs:
  my-job:
    id: "my-job"
    desc: "Job running on Azure Batch"

    runs-on:
      type: "azure_batch"
      with:
        batch_account_name: "${AZURE_BATCH_ACCOUNT_NAME}"
        batch_account_key: "${AZURE_BATCH_ACCOUNT_KEY}"
        batch_account_url: "${AZURE_BATCH_ACCOUNT_URL}"
        storage_account_name: "${AZURE_STORAGE_ACCOUNT_NAME}"
        storage_account_key: "${AZURE_STORAGE_ACCOUNT_KEY}"

    stages:
      - name: "start"
        type: "empty"
        echo: "Starting Azure Batch job"

      - name: "process"
        type: "py"
        run: |
          import pandas as pd

          # Your processing logic here
          data = pd.read_csv('/tmp/input.csv')
          result = data.groupby('category').sum()

          # Save results
          result.to_csv('/tmp/output.csv')

          # Update context
          result.context.update({
              "processed_rows": len(data),
              "output_file": "/tmp/output.csv"
          })

      - name: "complete"
        type: "empty"
        echo: "Azure Batch job completed"
```

### Advanced Configuration

#### Pool Configuration

Customize the Azure Batch pool settings:

```python
from ddeutil.workflow.plugins.providers.az import BatchPoolConfig

pool_config = BatchPoolConfig(
    pool_id="my-custom-pool",
    vm_size="Standard_D4s_v3",
    node_count=2,
    max_tasks_per_node=8,
    enable_auto_scale=True,
    auto_scale_formula="$TargetDedicatedNodes=min(10, $PendingTasks)"
)
```

#### Job Configuration

Configure job-specific settings:

```python
from ddeutil.workflow.plugins.providers.az import BatchJobConfig

job_config = BatchJobConfig(
    job_id="my-custom-job",
    pool_id="my-custom-pool",
    display_name="My Custom Job",
    priority=100,
    uses_task_dependencies=True
)
```

#### Task Configuration

Customize task execution settings:

```python
from ddeutil.workflow.plugins.providers.az import BatchTaskConfig

task_config = BatchTaskConfig(
    task_id="my-custom-task",
    command_line="python3 my_script.py",
    max_wall_clock_time="PT2H",  # 2 hours
    retention_time="PT1H"        # 1 hour
)
```

## Architecture

### Execution Flow

1. **Pool Creation**: Creates Azure Batch pool if it doesn't exist
2. **Job Creation**: Creates a new Azure Batch job
3. **File Upload**: Uploads job configuration and parameters to Azure Storage
4. **Task Creation**: Creates a task that executes the workflow job
5. **Task Execution**: The task runs on Azure Batch compute nodes
6. **Result Collection**: Downloads execution results from Azure Storage
7. **Cleanup**: Removes temporary Azure Batch resources

### File Management

The provider uses Azure Storage for file management:

- **Job Configuration**: Serialized job configuration uploaded as JSON
- **Parameters**: Job parameters uploaded as JSON
- **Task Script**: Python script that executes the job using `local_execute`
- **Results**: Execution results downloaded as JSON

### Compute Node Setup

Azure Batch compute nodes are automatically configured with:

- Ubuntu 20.04 LTS
- Python 3.x
- ddeutil-workflow package
- Required system packages

## Error Handling

The provider includes comprehensive error handling:

- **Connection Errors**: Handles Azure service connection issues
- **Authentication Errors**: Validates Azure credentials
- **Resource Errors**: Manages pool and job creation failures
- **Execution Errors**: Captures and reports task execution failures
- **Timeout Handling**: Configurable timeouts for long-running tasks

## Monitoring and Logging

### Azure Batch Monitoring

Monitor job execution through:

- Azure Portal Batch service
- Azure CLI Batch commands
- Azure Batch REST API

### Logging

The provider integrates with the workflow logging system:

```python
from ddeutil.workflow.traces import get_trace

trace = get_trace(run_id)
trace.info("[AZURE_BATCH]: Starting job execution")
trace.debug("[AZURE_BATCH]: Pool status: active")
trace.error("[AZURE_BATCH]: Task failed: timeout")
```

## Best Practices

### 1. Resource Management

- Use appropriate VM sizes for your workload
- Configure auto-scaling for variable workloads
- Set reasonable timeouts for task execution
- Clean up resources after job completion

### 2. Cost Optimization

- Use low-priority VMs for non-critical jobs
- Configure appropriate node counts
- Monitor and adjust resource usage
- Use spot instances when possible

### 3. Security

- Store credentials securely using environment variables
- Use Azure Key Vault for sensitive configuration
- Implement proper access controls
- Monitor access logs

### 4. Performance

- Optimize file upload/download operations
- Use appropriate storage tiers
- Configure parallel task execution
- Monitor and optimize resource usage

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify Azure credentials
   - Check account permissions
   - Ensure correct account URLs

2. **Pool Creation Failures**
   - Verify VM size availability
   - Check subscription quotas
   - Validate image references

3. **Task Execution Failures**
   - Check task command line
   - Verify file uploads
   - Review task logs

4. **Timeout Issues**
   - Increase task timeout
   - Optimize task execution
   - Check resource availability

### Debug Information

Enable debug logging:

```python
import logging
logging.getLogger('ddeutil.workflow.plugins.providers.az').setLevel(logging.DEBUG)
```

### Azure CLI Commands

Use Azure CLI for troubleshooting:

```bash
# List pools
az batch pool list

# List jobs
az batch job list

# List tasks
az batch task list --job-id <job-id>

# Get task details
az batch task show --job-id <job-id> --task-id <task-id>
```

## Examples

### Data Processing Workflow

See `docs/examples/azure-batch-example.yml` for a complete example of a data processing workflow using Azure Batch.

### Machine Learning Pipeline

```yaml
jobs:
  ml-training:
    runs-on:
      type: "azure_batch"
      with:
        batch_account_name: "${AZURE_BATCH_ACCOUNT_NAME}"
        batch_account_key: "${AZURE_BATCH_ACCOUNT_KEY}"
        batch_account_url: "${AZURE_BATCH_ACCOUNT_URL}"
        storage_account_name: "${AZURE_STORAGE_ACCOUNT_NAME}"
        storage_account_key: "${AZURE_STORAGE_ACCOUNT_KEY}"

    stages:
      - name: "prepare-data"
        type: "py"
        run: |
          # Data preparation logic
          pass

      - name: "train-model"
        type: "py"
        run: |
          # Model training logic
          pass

      - name: "evaluate-model"
        type: "py"
        run: |
          # Model evaluation logic
          pass
```

## API Reference

### AzureBatchProvider

Main provider class for Azure Batch operations.

#### Methods

- `execute_job(job, params, run_id=None, event=None)`: Execute a job on Azure Batch
- `cleanup(job_id=None)`: Clean up Azure Batch resources
- `_create_pool_if_not_exists(pool_id)`: Create pool if it doesn't exist
- `_create_job(job_id, pool_id)`: Create Azure Batch job
- `_create_task(job_id, task_id, command_line, ...)`: Create Azure Batch task

### Configuration Classes

- `BatchPoolConfig`: Pool configuration
- `BatchJobConfig`: Job configuration
- `BatchTaskConfig`: Task configuration

### Functions

- `azure_batch_execute(job, params, run_id=None, event=None)`: Main execution function

## Dependencies

- `azure-batch>=13.0.0`: Azure Batch SDK
- `azure-storage-blob>=12.0.0`: Azure Storage SDK
- `pydantic>=2.11.7`: Data validation
- `ddeutil-workflow`: Core workflow engine
