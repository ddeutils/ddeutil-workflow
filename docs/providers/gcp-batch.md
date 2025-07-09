# Google Cloud Batch Provider for ddeutil-workflow

This module provides Google Cloud Batch integration for workflow job execution, enabling scalable and managed execution environments for complex workflow processing on Google Cloud infrastructure.

## Features

- **Automatic Job Creation**: Creates and manages Google Cloud Batch jobs
- **Task Execution**: Executes workflow tasks on Google Cloud compute resources
- **File Management**: Handles file upload/download via Google Cloud Storage
- **Result Collection**: Retrieves and processes execution results
- **Resource Cleanup**: Automatic cleanup of Google Cloud Batch resources
- **Error Handling**: Comprehensive error handling and status monitoring

## Installation

### Prerequisites

1. **Google Cloud Project**: You need a Google Cloud project with Batch API enabled
2. **Service Account**: Create a service account with appropriate permissions
3. **Google Cloud Storage Bucket**: Create a GCS bucket for file management
4. **Batch API**: Enable the Batch API in your Google Cloud project

### Install Dependencies

```bash
# Install with Google Cloud dependencies
pip install ddeutil-workflow[gcp]

# Or install Google Cloud dependencies separately
pip install google-cloud-batch>=0.10.0 google-cloud-storage>=2.10.0
```

## Configuration

### Environment Variables

Set the following environment variables:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_REGION="us-central1"
export GCS_BUCKET="your-gcs-bucket"
```

### Google Cloud Setup

1. **Enable APIs**:
   ```bash
   gcloud services enable batch.googleapis.com
   gcloud services enable storage.googleapis.com
   ```

2. **Create Service Account**:
   ```bash
   gcloud iam service-accounts create workflow-batch \
     --display-name="Workflow Batch Service Account"

   gcloud projects add-iam-policy-binding your-project-id \
     --member="serviceAccount:workflow-batch@your-project-id.iam.gserviceaccount.com" \
     --role="roles/batch.worker"

   gcloud projects add-iam-policy-binding your-project-id \
     --member="serviceAccount:workflow-batch@your-project-id.iam.gserviceaccount.com" \
     --role="roles/storage.objectViewer"

   gcloud projects add-iam-policy-binding your-project-id \
     --member="serviceAccount:workflow-batch@your-project-id.iam.gserviceaccount.com" \
     --role="roles/storage.objectCreator"
   ```

3. **Create Service Account Key**:
   ```bash
   gcloud iam service-accounts keys create service-account.json \
     --iam-account=workflow-batch@your-project-id.iam.gserviceaccount.com
   ```

4. **Create GCS Bucket**:
   ```bash
   gsutil mb gs://my-workflow-bucket
   ```

## Usage

### Basic Configuration

```yaml
# workflow.yml
name: "gcp-batch-example"
description: "Example workflow using Google Cloud Batch"

params:
  data_source:
    type: str
    default: "gs://my-bucket/data.csv"

  output_path:
    type: str
    default: "gs://my-bucket/output"

jobs:
  data-processing:
    id: "data-processing"
    desc: "Process data using Google Cloud Batch"

    runs-on:
      type: "gcp_batch"
      with:
        project_id: "${GOOGLE_CLOUD_PROJECT}"
        region: "${GOOGLE_CLOUD_REGION}"
        gcs_bucket: "${GCS_BUCKET}"

    stages:
      - name: "start"
        type: "empty"
        echo: "Starting Google Cloud Batch job"

      - name: "process-data"
        type: "py"
        run: |
          import pandas as pd
          from google.cloud import storage

          # Download data from GCS
          storage_client = storage.Client()
          bucket = storage_client.bucket('my-bucket')
          blob = bucket.blob('data.csv')
          blob.download_to_filename('/tmp/data.csv')

          # Load and process data
          data = pd.read_csv('/tmp/data.csv')
          result = data.groupby('category').sum()

          # Save results to GCS
          result.to_csv('/tmp/output.csv')
          blob = bucket.blob('output/result.csv')
          blob.upload_from_filename('/tmp/output.csv')

          # Update context
          result.context.update({
              "processed_rows": len(data),
              "output_file": "gs://my-bucket/output/result.csv"
          })

      - name: "complete"
        type: "empty"
        echo: "Google Cloud Batch job completed"
```

### Advanced Configuration

#### Custom Resource Configuration

```yaml
jobs:
  resource-intensive:
    runs-on:
      type: "gcp_batch"
      with:
        project_id: "${GOOGLE_CLOUD_PROJECT}"
        region: "${GOOGLE_CLOUD_REGION}"
        gcs_bucket: "${GCS_BUCKET}"
        machine_type: "n1-standard-8"
        max_parallel_tasks: 4
```

#### Custom Credentials

```yaml
jobs:
  custom-auth:
    runs-on:
      type: "gcp_batch"
      with:
        project_id: "${GOOGLE_CLOUD_PROJECT}"
        region: "${GOOGLE_CLOUD_REGION}"
        gcs_bucket: "${GCS_BUCKET}"
        credentials_path: "/path/to/custom-service-account.json"
```

## Architecture

### Execution Flow

1. **Job Creation**: Creates Google Cloud Batch job with task specifications
2. **File Upload**: Uploads job configuration and parameters to GCS
3. **Task Execution**: Google Cloud Batch executes the task on compute resources
4. **Result Collection**: Downloads execution results from GCS
5. **Cleanup**: Removes temporary Google Cloud Batch resources

### File Management

The provider uses Google Cloud Storage for file management:

- **Job Configuration**: Serialized job configuration uploaded as JSON
- **Parameters**: Job parameters uploaded as JSON
- **Task Script**: Python script that executes the job using `local_execute`
- **Results**: Execution results downloaded as JSON

### Compute Resource Setup

Google Cloud Batch compute resources are automatically configured with:

- Python 3.11 slim container image
- ddeutil-workflow package installation
- GCS access for file upload/download
- Configurable CPU and memory limits

## Monitoring

### Google Cloud Console

Monitor job execution through the Google Cloud Console:

1. Go to Google Cloud Console > Batch
2. Navigate to Jobs
3. Select your job and view details

### Google Cloud CLI

```bash
# List jobs
gcloud batch jobs list

# Get job details
gcloud batch jobs describe job-name

# List tasks
gcloud batch tasks list --job job-name

# Get task details
gcloud batch tasks describe task-name --job job-name
```

### Cloud Logging

```bash
# Get job logs
gcloud logging read "resource.type=batch_job" --limit=50

# Get specific job logs
gcloud logging read "resource.type=batch_job AND resource.labels.job_name=job-name" --limit=50
```

## Best Practices

### 1. Resource Management

- Use appropriate machine types for your workload
- Configure parallel task execution for better performance
- Set reasonable timeouts for job execution
- Monitor and adjust resource usage

### 2. Cost Optimization

- Use appropriate machine types
- Configure parallel task execution efficiently
- Monitor and optimize resource usage
- Use lifecycle policies for GCS objects

### 3. Security

- Store credentials securely using service account keys
- Use service accounts with minimal required permissions
- Implement proper access controls
- Monitor access logs

### 4. Performance

- Optimize GCS upload/download operations
- Use appropriate storage classes
- Configure parallel job execution
- Monitor and optimize resource usage

## Troubleshooting

### Common Issues

#### 1. Authentication Errors

**Symptoms**: `google.auth.exceptions.DefaultCredentialsError`

**Solutions**:
- Verify service account credentials
- Check service account permissions
- Ensure correct project configuration

```bash
# Verify credentials
gcloud auth application-default print-access-token

# Check service account
gcloud iam service-accounts list
```

#### 2. Job Creation Failures

**Symptoms**: `google.api_core.exceptions.InvalidArgument`

**Solutions**:
- Verify job parameters
- Check machine type availability
- Validate resource requirements

```bash
# Check available machine types
gcloud compute machine-types list --filter="zone:us-central1-a"
```

#### 3. Job Execution Failures

**Symptoms**: Job status shows "FAILED"

**Solutions**:
- Check job logs in Cloud Logging
- Verify GCS bucket access
- Review task script execution

```bash
# Get job logs
gcloud logging read "resource.type=batch_job AND resource.labels.job_name=job-name" --limit=50
```

#### 4. GCS Access Issues

**Symptoms**: File upload/download failures

**Solutions**:
- Check GCS bucket permissions
- Verify service account has GCS access
- Ensure bucket exists and is accessible

```bash
# Test GCS access
gsutil ls gs://your-bucket/
```

### Debug Information

Enable debug logging:

```python
import logging
logging.getLogger('ddeutil.workflow.plugins.providers.gcs').setLevel(logging.DEBUG)
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
      type: "gcp_batch"
      with:
        project_id: "${GOOGLE_CLOUD_PROJECT}"
        region: "${GOOGLE_CLOUD_REGION}"
        gcs_bucket: "${GCS_BUCKET}"

    stages:
      - name: "process"
        type: "py"
        run: |
          import pandas as pd
          from google.cloud import storage
          import os

          dataset = os.environ.get('DATASET', 'unknown')
          storage_client = storage.Client()
          bucket = storage_client.bucket('my-bucket')

          # Download dataset
          blob = bucket.blob(f'data/{dataset}.csv')
          blob.download_to_filename(f'/tmp/{dataset}.csv')

          # Process data
          data = pd.read_csv(f'/tmp/{dataset}.csv')
          processed = data.groupby('category').agg({
              'value': ['sum', 'mean', 'count']
          })

          # Upload results
          processed.to_csv(f'/tmp/{dataset}_processed.csv')
          blob = bucket.blob(f'output/{dataset}_processed.csv')
          blob.upload_from_filename(f'/tmp/{dataset}_processed.csv')

          result.context.update({
              "dataset": dataset,
              "rows_processed": len(data),
              "output_file": f"gs://my-bucket/output/{dataset}_processed.csv"
          })
```

### Machine Learning Training

```yaml
jobs:
  ml-training:
    runs-on:
      type: "gcp_batch"
      with:
        project_id: "${GOOGLE_CLOUD_PROJECT}"
        region: "${GOOGLE_CLOUD_REGION}"
        gcs_bucket: "${GCS_BUCKET}"
        machine_type: "n1-standard-4"

    stages:
      - name: "train"
        type: "py"
        run: |
          import numpy as np
          import pickle
          from google.cloud import storage
          from sklearn.ensemble import RandomForestClassifier
          from sklearn.model_selection import train_test_split

          # Download training data
          storage_client = storage.Client()
          bucket = storage_client.bucket('my-bucket')
          blob = bucket.blob('data/training.csv')
          blob.download_to_filename('/tmp/training.csv')

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
          blob = bucket.blob('models/trained_model.pkl')
          blob.upload_from_filename('/tmp/model.pkl')

          result.context.update({
              "accuracy": accuracy,
              "model_path": "gs://my-bucket/models/trained_model.pkl"
          })
```

### BigQuery Data Processing

```yaml
jobs:
  bigquery-processing:
    runs-on:
      type: "gcp_batch"
      with:
        project_id: "${GOOGLE_CLOUD_PROJECT}"
        region: "${GOOGLE_CLOUD_REGION}"
        gcs_bucket: "${GCS_BUCKET}"

    stages:
      - name: "process-bigquery"
        type: "py"
        run: |
          from google.cloud import bigquery
          from google.cloud import storage
          import pandas as pd

          # Initialize BigQuery client
          bq_client = bigquery.Client()

          # Execute query
          query = """
          SELECT
            category,
            COUNT(*) as count,
            AVG(value) as avg_value
          FROM `my-project.my-dataset.my-table`
          GROUP BY category
          """

          df = bq_client.query(query).to_dataframe()

          # Save results to GCS
          df.to_csv('/tmp/bigquery_results.csv', index=False)

          storage_client = storage.Client()
          bucket = storage_client.bucket('my-bucket')
          blob = bucket.blob('output/bigquery_results.csv')
          blob.upload_from_filename('/tmp/bigquery_results.csv')

          result.context.update({
              "rows_processed": len(df),
              "output_file": "gs://my-bucket/output/bigquery_results.csv"
          })
```

## API Reference

### GoogleCloudBatchProvider

Main provider class for Google Cloud Batch operations.

#### Methods

- `execute_job(job, params, run_id=None, event=None)`: Execute a job on Google Cloud Batch
- `cleanup(job_id=None)`: Clean up Google Cloud Batch resources
- `_create_job(job_name, task_script_gcs_url, job_config_gcs_url, params_gcs_url)`: Create Google Cloud Batch job
- `_wait_for_job_completion(job_name, timeout)`: Wait for job completion

### Configuration Classes

- `BatchResourceConfig`: Compute resource configuration
- `BatchJobConfig`: Job configuration
- `BatchTaskConfig`: Task configuration

### Functions

- `gcp_batch_execute(job, params, run_id=None, event=None)`: Main execution function

## Dependencies

- `google-cloud-batch>=0.10.0`: Google Cloud Batch client library
- `google-cloud-storage>=2.10.0`: Google Cloud Storage client library
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
