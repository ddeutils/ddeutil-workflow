# Azure Batch Provider for ddeutil-workflow

This module provides Azure Batch integration for workflow job execution, enabling scalable and managed execution environments for complex workflow processing.

## Features

- **Automatic Pool Management**: Creates and manages Azure Batch pools
- **Job Submission**: Submits workflow jobs to Azure Batch compute nodes
- **File Management**: Handles file upload/download via Azure Storage
- **Result Collection**: Retrieves and processes execution results
- **Resource Cleanup**: Automatic cleanup of Azure Batch resources
- **Error Handling**: Comprehensive error handling and status monitoring

## Installation

### Prerequisites

1. **Azure Account**: You need an Azure account with Batch and Storage services
2. **Azure Batch Account**: Create an Azure Batch account in the Azure portal
3. **Azure Storage Account**: Create an Azure Storage account for file management

### Install Dependencies

```bash
# Install with Azure dependencies
pip install ddeutil-workflow[azure]

# Or install Azure dependencies separately
pip install azure-batch>=13.0.0 azure-storage-blob>=12.0.0
```

## Configuration

### Environment Variables

Set the following environment variables:

```bash
export AZURE_BATCH_ACCOUNT_NAME="your-batch-account"
export AZURE_BATCH_ACCOUNT_KEY="your-batch-key"
export AZURE_BATCH_ACCOUNT_URL="https://your-batch-account.region.batch.azure.com"
export AZURE_STORAGE_ACCOUNT_NAME="your-storage-account"
export AZURE_STORAGE_ACCOUNT_KEY="your-storage-key"
```

### Azure Batch Account Setup

1. **Create Batch Account**:
   ```bash
   az batch account create \
     --name your-batch-account \
     --resource-group your-resource-group \
     --location eastus
   ```

2. **Get Account Credentials**:
   ```bash
   az batch account keys list \
     --name your-batch-account \
     --resource-group your-resource-group
   ```

3. **Create Storage Account**:
   ```bash
   az storage account create \
     --name your-storage-account \
     --resource-group your-resource-group \
     --location eastus \
     --sku Standard_LRS
   ```

## Usage

### Basic Configuration

```yaml
# workflow.yml
name: "azure-batch-example"
description: "Example workflow using Azure Batch"

params:
  data_source:
    type: str
    default: "https://example.com/data.csv"

  output_path:
    type: str
    default: "/tmp/output"

jobs:
  data-processing:
    id: "data-processing"
    desc: "Process data using Azure Batch"

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

      - name: "process-data"
        type: "py"
        run: |
          import pandas as pd

          # Load and process data
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

#### Custom Pool Configuration

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

#### Custom Job Configuration

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

#### Custom Task Configuration

```python
from ddeutil.workflow.plugins.providers.az import BatchTaskConfig

task_config = BatchTaskConfig(
    task_id="my-custom-task",
    command_line="python3 my_script.py",
    max_wall_clock_time="PT2H",  # 2 hours
    retention_time="PT1H"        # 1 hour
)
```

### Programmatic Usage

```python
from ddeutil.workflow.plugins.providers.az import AzureBatchProvider
from ddeutil.workflow.job import Job

# Create provider
provider = AzureBatchProvider(
    batch_account_name="mybatchaccount",
    batch_account_key="mykey",
    batch_account_url="https://mybatchaccount.region.batch.azure.com",
    storage_account_name="mystorageaccount",
    storage_account_key="mystoragekey"
)

# Execute job
job = Job(...)  # Your job configuration
params = {"param1": "value1"}
result = provider.execute_job(job, params, run_id="job-123")

# Clean up
provider.cleanup("workflow-job-job-123")
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

## Monitoring

### Azure Portal

Monitor job execution through the Azure Portal:

1. Go to Azure Portal > Batch accounts
2. Select your batch account
3. Navigate to Jobs > Pools > Tasks

### Azure CLI

```bash
# List pools
az batch pool list

# List jobs
az batch job list

# List tasks
az batch task list --job-id <job-id>

# Get task details
az batch task show --job-id <job-id> --task-id <task-id>

# Get task files
az batch file list --job-id <job-id> --task-id <task-id>
```

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

#### 1. Authentication Errors

**Symptoms**: `BatchErrorException: 401 Unauthorized`

**Solutions**:
- Verify Azure credentials
- Check account permissions
- Ensure correct account URLs

```bash
# Verify credentials
az batch account keys list --name your-batch-account
```

#### 2. Pool Creation Failures

**Symptoms**: `BatchErrorException: 400 Bad Request`

**Solutions**:
- Verify VM size availability
- Check subscription quotas
- Validate image references

```bash
# Check VM sizes
az vm list-sizes --location eastus --output table
```

#### 3. Task Execution Failures

**Symptoms**: Task status shows "failed"

**Solutions**:
- Check task command line
- Verify file uploads
- Review task logs

```bash
# Get task logs
az batch file download --job-id <job-id> --task-id <task-id> --file-path stdout.txt
```

#### 4. Timeout Issues

**Symptoms**: Task status shows "timeout"

**Solutions**:
- Increase task timeout
- Optimize task execution
- Check resource availability

### Debug Information

Enable debug logging:

```python
import logging
logging.getLogger('ddeutil.workflow.plugins.providers.az').setLevel(logging.DEBUG)
```

### Error Codes

| Error Code | Description | Solution |
|------------|-------------|----------|
| 401 | Unauthorized | Check credentials |
| 403 | Forbidden | Check permissions |
| 404 | Not Found | Check resource names |
| 409 | Conflict | Resource already exists |
| 429 | Too Many Requests | Implement retry logic |

## Examples

### Data Processing Workflow

See `docs/examples/azure-batch-example.yml` for a complete example.

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

### Parallel Processing

```yaml
jobs:
  parallel-processing:
    strategy:
      matrix:
        worker_id: [1, 2, 3, 4]
      max_parallel: 2

    runs-on:
      type: "azure_batch"
      with:
        batch_account_name: "${AZURE_BATCH_ACCOUNT_NAME}"
        batch_account_key: "${AZURE_BATCH_ACCOUNT_KEY}"
        batch_account_url: "${AZURE_BATCH_ACCOUNT_URL}"
        storage_account_name: "${AZURE_STORAGE_ACCOUNT_NAME}"
        storage_account_key: "${AZURE_STORAGE_ACCOUNT_KEY}"

    stages:
      - name: "process-chunk"
        type: "py"
        run: |
          # Process data chunk based on worker_id
          chunk_id = params['matrix']['worker_id']
          # Processing logic here
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

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
