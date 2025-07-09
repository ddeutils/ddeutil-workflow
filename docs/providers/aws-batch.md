# AWS Batch Provider for ddeutil-workflow

This module provides AWS Batch integration for workflow job execution, enabling scalable and managed execution environments for complex workflow processing on AWS infrastructure.

## Features

- **Automatic Job Definition Management**: Creates and manages AWS Batch job definitions
- **Job Submission**: Submits workflow jobs to AWS Batch job queues
- **File Management**: Handles file upload/download via S3
- **Result Collection**: Retrieves and processes execution results
- **Resource Cleanup**: Automatic cleanup of AWS Batch resources
- **Error Handling**: Comprehensive error handling and status monitoring

## Installation

### Prerequisites

1. **AWS Account**: You need an AWS account with Batch and S3 services
2. **AWS Batch Job Queue**: Create an AWS Batch job queue in the AWS console
3. **S3 Bucket**: Create an S3 bucket for file management
4. **IAM Roles**: Configure appropriate IAM roles for Batch execution

### Install Dependencies

```bash
# Install with AWS dependencies
pip install ddeutil-workflow[aws]

# Or install AWS dependencies separately
pip install boto3>=1.34.0
```

## Configuration

### Environment Variables

Set the following environment variables:

```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
export AWS_BATCH_JOB_QUEUE_ARN="arn:aws:batch:region:account:job-queue/queue-name"
export AWS_S3_BUCKET="your-s3-bucket"
```

### AWS Batch Setup

1. **Create Job Queue**:
   ```bash
   aws batch create-job-queue \
     --job-queue-name my-job-queue \
     --state ENABLED \
     --priority 1 \
     --compute-environment-order order=1,computeEnvironment=arn:aws:batch:region:account:compute-environment/env-name
   ```

2. **Create Compute Environment**:
   ```bash
   aws batch create-compute-environment \
     --compute-environment-name my-compute-env \
     --type MANAGED \
     --state ENABLED \
     --compute-resources type=EC2,minvCpus=0,maxvCpus=256,desiredvCpus=0,subnets=subnet-12345,securityGroupIds=sg-12345,instanceRole=arn:aws:iam::account:instance-profile/BatchInstanceRole
   ```

3. **Create S3 Bucket**:
   ```bash
   aws s3 mb s3://my-workflow-bucket
   ```

## Usage

### Basic Configuration

```yaml
# workflow.yml
name: "aws-batch-example"
description: "Example workflow using AWS Batch"

params:
  data_source:
    type: str
    default: "s3://my-bucket/data.csv"

  output_path:
    type: str
    default: "s3://my-bucket/output"

jobs:
  data-processing:
    id: "data-processing"
    desc: "Process data using AWS Batch"

    runs-on:
      type: "aws_batch"
      with:
        job_queue_arn: "${AWS_BATCH_JOB_QUEUE_ARN}"
        s3_bucket: "${AWS_S3_BUCKET}"
        region_name: "${AWS_DEFAULT_REGION}"

    stages:
      - name: "start"
        type: "empty"
        echo: "Starting AWS Batch job"

      - name: "process-data"
        type: "py"
        run: |
          import pandas as pd
          import boto3

          # Download data from S3
          s3_client = boto3.client('s3')
          s3_client.download_file('my-bucket', 'data.csv', '/tmp/data.csv')

          # Load and process data
          data = pd.read_csv('/tmp/data.csv')
          result = data.groupby('category').sum()

          # Save results to S3
          result.to_csv('/tmp/output.csv')
          s3_client.upload_file('/tmp/output.csv', 'my-bucket', 'output/result.csv')

          # Update context
          result.context.update({
              "processed_rows": len(data),
              "output_file": "s3://my-bucket/output/result.csv"
          })

      - name: "complete"
        type: "empty"
        echo: "AWS Batch job completed"
```

### Advanced Configuration

#### Custom Job Definition

```yaml
jobs:
  custom-job:
    runs-on:
      type: "aws_batch"
      with:
        job_queue_arn: "${AWS_BATCH_JOB_QUEUE_ARN}"
        s3_bucket: "${AWS_S3_BUCKET}"
        region_name: "us-west-2"
        aws_access_key_id: "${AWS_ACCESS_KEY_ID}"
        aws_secret_access_key: "${AWS_SECRET_ACCESS_KEY}"
```

#### Resource Configuration

```yaml
jobs:
  resource-intensive:
    runs-on:
      type: "aws_batch"
      with:
        job_queue_arn: "${AWS_BATCH_JOB_QUEUE_ARN}"
        s3_bucket: "${AWS_S3_BUCKET}"
        region_name: "us-east-1"

    stages:
      - name: "heavy-computation"
        type: "py"
        run: |
          # Resource-intensive processing
          import numpy as np
          import multiprocessing as mp

          # Use all available cores
          data = np.random.rand(10000, 10000)
          result = np.linalg.eig(data)

          result.context.update({
              "computation_completed": True,
              "eigenvalues_count": len(result[0])
          })
```

## Architecture

### Execution Flow

1. **Job Definition Creation**: Creates AWS Batch job definition if it doesn't exist
2. **File Upload**: Uploads job configuration and parameters to S3
3. **Job Submission**: Submits job to AWS Batch job queue
4. **Task Execution**: AWS Batch executes the task on compute resources
5. **Result Collection**: Downloads execution results from S3
6. **Cleanup**: Removes temporary AWS Batch resources

### File Management

The provider uses S3 for file management:

- **Job Configuration**: Serialized job configuration uploaded as JSON
- **Parameters**: Job parameters uploaded as JSON
- **Task Script**: Python script that executes the job using `local_execute`
- **Results**: Execution results downloaded as JSON

### Compute Resource Setup

AWS Batch compute resources are automatically configured with:

- Python 3.11 slim container image
- ddeutil-workflow package installation
- S3 access for file upload/download
- Configurable CPU and memory limits

## Monitoring

### AWS Console

Monitor job execution through the AWS Console:

1. Go to AWS Console > Batch
2. Navigate to Jobs > Job queues
3. Select your job queue and view jobs

### AWS CLI

```bash
# List job queues
aws batch describe-job-queues

# List jobs
aws batch list-jobs --job-queue my-job-queue

# Get job details
aws batch describe-jobs --jobs job-arn

# List job definitions
aws batch describe-job-definitions --job-definition-name workflow-job-def-*
```

### CloudWatch Logs

```bash
# Get job logs
aws logs describe-log-groups --log-group-name-prefix /aws/batch/job

# Get specific job logs
aws logs filter-log-events --log-group-name /aws/batch/job --filter-pattern "job-arn"
```

## Best Practices

### 1. Resource Management

- Use appropriate instance types for your workload
- Configure job queue priorities for different job types
- Set reasonable timeouts for job execution
- Monitor and adjust resource usage

### 2. Cost Optimization

- Use Spot instances for non-critical jobs
- Configure appropriate instance types
- Monitor and optimize resource usage
- Use lifecycle policies for S3 objects

### 3. Security

- Store credentials securely using environment variables
- Use IAM roles with minimal required permissions
- Implement proper access controls
- Monitor access logs

### 4. Performance

- Optimize S3 upload/download operations
- Use appropriate storage tiers
- Configure parallel job execution
- Monitor and optimize resource usage

## Troubleshooting

### Common Issues

#### 1. Authentication Errors

**Symptoms**: `ClientError: An error occurred (UnauthorizedOperation)`

**Solutions**:
- Verify AWS credentials
- Check IAM permissions
- Ensure correct region configuration

```bash
# Verify credentials
aws sts get-caller-identity

# Check Batch permissions
aws batch describe-job-queues
```

#### 2. Job Definition Failures

**Symptoms**: `ClientError: An error occurred (InvalidParameterValue)`

**Solutions**:
- Verify job definition parameters
- Check container image availability
- Validate resource requirements

```bash
# Check job definition
aws batch describe-job-definitions --job-definition-name workflow-job-def-*
```

#### 3. Job Execution Failures

**Symptoms**: Job status shows "FAILED"

**Solutions**:
- Check job logs in CloudWatch
- Verify S3 bucket access
- Review task script execution

```bash
# Get job logs
aws logs filter-log-events --log-group-name /aws/batch/job --filter-pattern "job-name"
```

#### 4. S3 Access Issues

**Symptoms**: File upload/download failures

**Solutions**:
- Check S3 bucket permissions
- Verify IAM roles have S3 access
- Ensure bucket exists and is accessible

```bash
# Test S3 access
aws s3 ls s3://your-bucket/
```

### Debug Information

Enable debug logging:

```python
import logging
logging.getLogger('ddeutil.workflow.plugins.providers.aws').setLevel(logging.DEBUG)
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

### Data Processing Pipeline

```yaml
jobs:
  data-pipeline:
    strategy:
      matrix:
        dataset: ["sales", "inventory", "users"]
      max_parallel: 3

    runs-on:
      type: "aws_batch"
      with:
        job_queue_arn: "${AWS_BATCH_JOB_QUEUE_ARN}"
        s3_bucket: "${AWS_S3_BUCKET}"
        region_name: "${AWS_DEFAULT_REGION}"

    stages:
      - name: "process"
        type: "py"
        run: |
          import pandas as pd
          import boto3
          import os

          dataset = os.environ.get('DATASET', 'unknown')
          s3_client = boto3.client('s3')

          # Download dataset
          s3_client.download_file('my-bucket', f'data/{dataset}.csv', f'/tmp/{dataset}.csv')

          # Process data
          data = pd.read_csv(f'/tmp/{dataset}.csv')
          processed = data.groupby('category').agg({
              'value': ['sum', 'mean', 'count']
          })

          # Upload results
          processed.to_csv(f'/tmp/{dataset}_processed.csv')
          s3_client.upload_file(
              f'/tmp/{dataset}_processed.csv',
              'my-bucket',
              f'output/{dataset}_processed.csv'
          )

          result.context.update({
              "dataset": dataset,
              "rows_processed": len(data),
              "output_file": f"s3://my-bucket/output/{dataset}_processed.csv"
          })
```

### Machine Learning Training

```yaml
jobs:
  ml-training:
    runs-on:
      type: "aws_batch"
      with:
        job_queue_arn: "${AWS_BATCH_JOB_QUEUE_ARN}"
        s3_bucket: "${AWS_S3_BUCKET}"
        region_name: "${AWS_DEFAULT_REGION}"

    stages:
      - name: "train"
        type: "py"
        run: |
          import numpy as np
          import pickle
          import boto3
          from sklearn.ensemble import RandomForestClassifier
          from sklearn.model_selection import train_test_split

          # Download training data
          s3_client = boto3.client('s3')
          s3_client.download_file('my-bucket', 'data/training.csv', '/tmp/training.csv')

          # Load and prepare data
          data = np.loadtxt('/tmp/training.csv', delimiter=',')
          X, y = data[:, :-1], data[:, -1]
          X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

          # Train model
          model = RandomForestClassifier(n_estimators=100, random_state=42)
          model.fit(X_train, y_train)

          # Evaluate model
          accuracy = model.score(X_test, y_test)

          # Save model
          with open('/tmp/model.pkl', 'wb') as f:
              pickle.dump(model, f)

          # Upload model
          s3_client.upload_file('/tmp/model.pkl', 'my-bucket', 'models/trained_model.pkl')

          result.context.update({
              "accuracy": accuracy,
              "model_path": "s3://my-bucket/models/trained_model.pkl"
          })
```

## API Reference

### AWSBatchProvider

Main provider class for AWS Batch operations.

#### Methods

- `execute_job(job, params, run_id=None, event=None)`: Execute a job on AWS Batch
- `cleanup(job_id=None)`: Clean up AWS Batch resources
- `_create_job_definition_if_not_exists(job_def_name)`: Create job definition if it doesn't exist
- `_create_job(job_name, job_def_arn, parameters)`: Create AWS Batch job
- `_wait_for_job_completion(job_arn, timeout)`: Wait for job completion

### Configuration Classes

- `BatchComputeEnvironmentConfig`: Compute environment configuration
- `BatchJobQueueConfig`: Job queue configuration
- `BatchJobConfig`: Job configuration
- `BatchTaskConfig`: Task configuration

### Functions

- `aws_batch_execute(job, params, run_id=None, event=None)`: Main execution function

## Dependencies

- `boto3>=1.34.0`: AWS SDK for Python
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
