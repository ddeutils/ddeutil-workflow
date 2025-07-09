# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Google Cloud Batch Provider Module.

This module provides Google Cloud Batch integration for workflow job execution.
It handles job creation, task execution, and result retrieval using Google Cloud
Batch service and Google Cloud Storage.

The Google Cloud Batch provider enables running workflow jobs on Google Cloud
Batch compute resources, providing scalable and managed execution environments
for complex workflow processing.

Key Features:
    - Automatic job creation and management
    - Task execution on Google Cloud compute resources
    - Result file upload/download via Google Cloud Storage
    - Error handling and status monitoring
    - Resource cleanup and management
    - Optimized file operations and caching

Classes:
    GoogleCloudBatchProvider: Main provider for Google Cloud Batch operations
    BatchJobConfig: Configuration for Google Cloud Batch jobs
    BatchTaskConfig: Configuration for Google Cloud Batch tasks
    BatchResourceConfig: Configuration for compute resources

References:
    - https://cloud.google.com/batch/docs
    - https://googleapis.dev/python/batch/latest/index.html

Config Example:

    ```dotenv
    export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
    export GOOGLE_CLOUD_PROJECT="your-project-id"
    export GOOGLE_CLOUD_REGION="us-central1"
    export GCS_BUCKET="your-gcs-bucket"
    ```

    ```yaml
    jobs:
    my-job:
        runs-on:
        type: "gcp_batch"
        with:
            project_id: "${GOOGLE_CLOUD_PROJECT}"
            region: "${GOOGLE_CLOUD_REGION}"
            gcs_bucket: "${GCS_BUCKET}"
            machine_type: "e2-standard-4"
            max_parallel_tasks: 10
        stages:
        - name: "process"
            type: "py"
            run: |
            # Your processing logic here
            result.context.update({"output": "processed"})
    ```

"""
from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import contextmanager
from typing import Any, Optional

try:
    from google.api_core import exceptions as google_exceptions
    from google.api_core import retry
    from google.cloud import batch_v1, storage

    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False

from pydantic import BaseModel, Field

from ...__types import DictData
from ...job import Job
from ...result import FAILED, SUCCESS, Result
from ...traces import get_trace
from ...utils import gen_id


class BatchResourceConfig(BaseModel):
    """Google Cloud Batch resource configuration."""

    machine_type: str = Field(
        default="e2-standard-4", description="Machine type"
    )
    cpu_count: int = Field(default=4, description="Number of CPUs")
    memory_mb: int = Field(default=16384, description="Memory in MB")
    boot_disk_size_gb: int = Field(
        default=50, description="Boot disk size in GB"
    )
    max_parallel_tasks: int = Field(
        default=1, description="Maximum parallel tasks"
    )
    gpu_count: int = Field(default=0, description="Number of GPUs")
    gpu_type: Optional[str] = Field(default=None, description="GPU type")


class BatchJobConfig(BaseModel):
    """Google Cloud Batch job configuration."""

    job_name: str = Field(description="Unique job name")
    project_id: str = Field(description="Google Cloud project ID")
    region: str = Field(description="Google Cloud region")
    gcs_bucket: str = Field(description="Google Cloud Storage bucket")
    resource_config: Optional[BatchResourceConfig] = Field(
        default=None, description="Resource configuration"
    )
    timeout_seconds: int = Field(
        default=3600, description="Job timeout in seconds"
    )
    retry_count: int = Field(default=2, description="Number of retries")
    preemptible: bool = Field(
        default=False, description="Use preemptible instances"
    )


class BatchTaskConfig(BaseModel):
    """Google Cloud Batch task configuration."""

    task_name: str = Field(description="Unique task name")
    command: list[str] = Field(description="Command to execute")
    image: str = Field(
        default="python:3.11-slim", description="Container image"
    )
    timeout_seconds: int = Field(
        default=3600, description="Task timeout in seconds"
    )
    environment_variables: Optional[dict[str, str]] = Field(
        default=None, description="Environment variables"
    )


class GoogleCloudBatchProvider:
    """Google Cloud Batch provider for workflow job execution.

    This provider handles the complete lifecycle of Google Cloud Batch operations
    including job creation, task execution, and result retrieval. It integrates
    with Google Cloud Storage for file management and provides comprehensive
    error handling and monitoring.

    Attributes:
        batch_client: Google Cloud Batch client
        storage_client: Google Cloud Storage client
        project_id: Google Cloud project ID
        region: Google Cloud region
        gcs_bucket: Google Cloud Storage bucket name
        job_config: Job configuration
        task_config: Task configuration

    Example:
        ```python
        provider = GoogleCloudBatchProvider(
            project_id="my-project",
            region="us-central1",
            gcs_bucket="my-workflow-bucket"
        )

        result = provider.execute_job(job, params, run_id="job-123")
        ```
    """

    def __init__(
        self,
        project_id: str,
        region: str,
        gcs_bucket: str,
        job_config: Optional[BatchJobConfig] = None,
        task_config: Optional[BatchTaskConfig] = None,
        credentials_path: Optional[str] = None,
    ):
        """Initialize Google Cloud Batch provider.

        Args:
            project_id: Google Cloud project ID
            region: Google Cloud region
            gcs_bucket: Google Cloud Storage bucket name
            job_config: Job configuration
            task_config: Task configuration
            credentials_path: Path to service account credentials file
        """
        if not GCP_AVAILABLE:
            raise ImportError(
                "Google Cloud dependencies not available. "
                "Install with: pip install google-cloud-batch google-cloud-storage"
            )

        self.project_id = project_id
        self.region = region
        self.gcs_bucket = gcs_bucket

        # Set credentials if provided
        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

        # Initialize Google Cloud clients with retry configuration
        self.batch_client = batch_v1.BatchServiceClient()
        self.storage_client = storage.Client(project=project_id)

        # Set configurations
        self.job_config = job_config
        self.task_config = task_config

        # Cache for bucket and blob operations
        self._bucket_cache: Optional[storage.Bucket] = None

    @property
    def bucket(self) -> storage.Bucket:
        """Get or create cached bucket instance."""
        if self._bucket_cache is None:
            self._bucket_cache = self.storage_client.bucket(self.gcs_bucket)
        return self._bucket_cache

    def _ensure_gcs_bucket(self) -> None:
        """Ensure Google Cloud Storage bucket exists."""
        try:
            self.bucket.reload()
        except google_exceptions.NotFound:
            # Create bucket with optimized settings
            bucket = self.storage_client.create_bucket(
                self.gcs_bucket,
                location=self.region,
                storage_class=storage.StorageClass.STANDARD,
            )
            self._bucket_cache = bucket

    @contextmanager
    def _temp_file_context(self, suffix: str = ".tmp"):
        """Context manager for temporary file operations."""
        temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        try:
            yield temp_file.name
        finally:
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass

    def _upload_file_to_gcs(self, file_path: str, gcs_blob_name: str) -> str:
        """Upload file to Google Cloud Storage with optimized settings.

        Args:
            file_path: Local file path
            gcs_blob_name: GCS blob name

        Returns:
            str: GCS blob URL
        """
        self._ensure_gcs_bucket()

        blob = self.bucket.blob(gcs_blob_name)

        # Set optimized metadata for workflow files
        blob.metadata = {
            "workflow_provider": "gcp_batch",
            "upload_time": str(time.time()),
        }

        # Use optimized upload settings
        with open(file_path, "rb") as data:
            blob.upload_from_file(
                data,
                content_type="application/octet-stream",
                timeout=300,  # 5 minute timeout
            )

        return f"gs://{self.gcs_bucket}/{gcs_blob_name}"

    def _download_file_from_gcs(
        self, gcs_blob_name: str, local_path: str
    ) -> None:
        """Download file from Google Cloud Storage with optimized settings.

        Args:
            gcs_blob_name: GCS blob name
            local_path: Local file path
        """
        blob = self.bucket.blob(gcs_blob_name)

        with open(local_path, "wb") as data:
            blob.download_to_file(data, timeout=300)

    def _create_job_definition(
        self,
        job_name: str,
        task_script_gcs_url: str,
        job_config_gcs_url: str,
        params_gcs_url: str,
    ) -> batch_v1.Job:
        """Create optimized job definition.

        Args:
            job_name: Job name
            task_script_gcs_url: GCS URL of task script
            job_config_gcs_url: GCS URL of job configuration
            params_gcs_url: GCS URL of parameters

        Returns:
            batch_v1.Job: Job definition
        """
        job_config = self.job_config or BatchJobConfig(
            job_name=job_name,
            project_id=self.project_id,
            region=self.region,
            gcs_bucket=self.gcs_bucket,
        )

        resource_config = job_config.resource_config or BatchResourceConfig()

        # Create optimized runnable
        runnable = batch_v1.Runnable()
        runnable.container = batch_v1.Runnable.Container()
        runnable.container.image_uri = "python:3.11-slim"
        runnable.container.commands = ["python3", "task_script.py"]

        # Add environment variables with optimized settings
        env_vars = {
            "TASK_SCRIPT_URL": task_script_gcs_url,
            "JOB_CONFIG_URL": job_config_gcs_url,
            "PARAMS_URL": params_gcs_url,
            "PYTHONUNBUFFERED": "1",  # Ensure immediate output
            "PYTHONDONTWRITEBYTECODE": "1",  # Don't create .pyc files
        }

        if self.task_config and self.task_config.environment_variables:
            env_vars.update(self.task_config.environment_variables)

        runnable.container.environment = batch_v1.Environment()
        runnable.container.environment.variables = env_vars

        # Create optimized task specification
        task = batch_v1.TaskSpec()
        task.runnables = [runnable]
        task.max_retry_count = job_config.retry_count
        task.max_run_duration = f"{job_config.timeout_seconds}s"

        # Configure compute resources
        resources = batch_v1.ComputeResource()
        resources.cpu_milli = resource_config.cpu_count * 1000
        resources.memory_mib = resource_config.memory_mb

        # Add GPU configuration if specified
        if resource_config.gpu_count > 0 and resource_config.gpu_type:
            resources.gpu_count = resource_config.gpu_count
            resources.gpu_type = resource_config.gpu_type

        task.compute_resource = resources

        # Create job with optimized allocation policy
        job = batch_v1.Job()
        job.name = job_name
        job.task_groups = [
            batch_v1.TaskGroup(
                task_spec=task,
                task_count=1,
                parallelism=resource_config.max_parallel_tasks,
            )
        ]

        # Configure allocation policy
        job.allocation_policy = batch_v1.AllocationPolicy()

        # Set provisioning model based on configuration
        provisioning_model = (
            batch_v1.AllocationPolicy.ProvisioningModel.PREEMPTIBLE
            if job_config.preemptible
            else batch_v1.AllocationPolicy.ProvisioningModel.STANDARD
        )

        job.allocation_policy.instances = [
            batch_v1.AllocationPolicy.InstancePolicyOrTemplate(
                install_gpu_drivers=resource_config.gpu_count > 0,
                machine_type=resource_config.machine_type,
                provisioning_model=provisioning_model,
            )
        ]

        return job

    def _create_job(
        self,
        job_name: str,
        task_script_gcs_url: str,
        job_config_gcs_url: str,
        params_gcs_url: str,
    ) -> str:
        """Create Google Cloud Batch job with optimized settings.

        Args:
            job_name: Job name
            task_script_gcs_url: GCS URL of task script
            job_config_gcs_url: GCS URL of job configuration
            params_gcs_url: GCS URL of parameters

        Returns:
            str: Job name
        """
        job = self._create_job_definition(
            job_name, task_script_gcs_url, job_config_gcs_url, params_gcs_url
        )

        # Create the job with retry logic
        parent = f"projects/{self.project_id}/locations/{self.region}"

        request = batch_v1.CreateJobRequest(
            parent=parent, job_id=job_name, job=job
        )

        # Use retry decorator for better reliability
        @retry.Retry(
            predicate=retry.if_exception_type(
                google_exceptions.ServiceUnavailable
            )
        )
        def create_job_with_retry():
            operation = self.batch_client.create_job(request=request)
            return operation.result()

        result = create_job_with_retry()
        return result.name

    def _wait_for_job_completion(
        self, job_name: str, timeout: int = 3600
    ) -> dict[str, Any]:
        """Wait for job completion with optimized polling.

        Args:
            job_name: Job name
            timeout: Timeout in seconds

        Returns:
            Dict[str, Any]: Job results
        """
        start_time = time.time()
        poll_interval = 10  # Start with 10 second intervals

        while time.time() - start_time < timeout:
            try:
                request = batch_v1.GetJobRequest(name=job_name)
                job = self.batch_client.get_job(request=request)

                if job.status.state == batch_v1.JobStatus.State.SUCCEEDED:
                    return self._process_successful_job(job, job_name)

                elif job.status.state == batch_v1.JobStatus.State.FAILED:
                    return self._process_failed_job(job)

                elif job.status.state in [
                    batch_v1.JobStatus.State.RUNNING,
                    batch_v1.JobStatus.State.SCHEDULED,
                    batch_v1.JobStatus.State.QUEUED,
                ]:
                    # Adaptive polling: increase interval for long-running jobs
                    if time.time() - start_time > 300:  # After 5 minutes
                        poll_interval = min(
                            poll_interval * 1.5, 60
                        )  # Max 60 seconds

                    time.sleep(poll_interval)
                else:
                    # For other states, use shorter polling
                    time.sleep(5)

            except google_exceptions.NotFound:
                # Job might be deleted, wait a bit and retry
                time.sleep(poll_interval)
            except Exception:
                # Continue polling on error with exponential backoff
                poll_interval = min(poll_interval * 2, 60)
                time.sleep(poll_interval)

        return {"status": "timeout", "exit_code": 1}

    def _process_successful_job(
        self, job: batch_v1.Job, job_name: str
    ) -> dict[str, Any]:
        """Process successful job and download results.

        Args:
            job: Job object
            job_name: Job name

        Returns:
            Dict[str, Any]: Job results with files
        """
        result_files = {}
        try:
            # List objects in job's GCS prefix
            job_id = job_name.split("/")[-1]
            prefix = f"jobs/{job_id}/"

            blobs = self.bucket.list_blobs(prefix=prefix)

            # Download result files in parallel (simplified)
            for blob in blobs:
                if blob.name.endswith((".json", ".txt", ".log")):
                    with self._temp_file_context() as tmp_file:
                        blob.download_to_filename(tmp_file)
                        with open(tmp_file) as f:
                            result_files[blob.name] = f.read()
        except Exception:
            # File download failed, continue with empty results
            pass

        return {"status": "completed", "exit_code": 0, "files": result_files}

    def _process_failed_job(self, job: batch_v1.Job) -> dict[str, Any]:
        """Process failed job and extract error information.

        Args:
            job: Job object

        Returns:
            Dict[str, Any]: Failure information
        """
        failure_reason = "Job failed"

        # Try to extract more detailed error information
        if hasattr(job, "status") and hasattr(job.status, "status_events"):
            for event in job.status.status_events:
                if event.type_ == batch_v1.JobStatus.StatusEvent.Type.FAILED:
                    failure_reason = event.description or failure_reason
                    break

        return {
            "status": "failed",
            "exit_code": 1,
            "failure_reason": failure_reason,
        }

    def _create_optimized_task_script(
        self, job: Job, params: DictData, run_id: str
    ) -> str:
        """Create optimized Python script for task execution.

        Args:
            job: Job to execute
            params: Job parameters
            run_id: Execution run ID

        Returns:
            str: Path to created script
        """
        script_content = f'''#!/usr/bin/env python3
import json
import sys
import os
import subprocess
import time
from pathlib import Path

def install_package(package):
    """Install package with retry logic."""
    for attempt in range(3):
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', package],
                         check=True, capture_output=True, timeout=300)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)

def download_file(url, local_path):
    """Download file with retry logic."""
    for attempt in range(3):
        try:
            subprocess.run(['gsutil', 'cp', url, local_path],
                         check=True, capture_output=True, timeout=300)
            return True
        except subprocess.CalledProcessError:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)

# Install ddeutil-workflow with retry
install_package('ddeutil-workflow')

# Download files with retry
download_file(os.environ['TASK_SCRIPT_URL'], 'task_script.py')
download_file(os.environ['JOB_CONFIG_URL'], 'job_config.json')
download_file(os.environ['PARAMS_URL'], 'params.json')

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

from ddeutil.workflow.job import local_execute
from ddeutil.workflow import Job

# Load job configuration
with open('job_config.json', 'r') as f:
    job_data = json.load(f)

# Load parameters
with open('params.json', 'r') as f:
    params = json.load(f)

# Create job instance
job = Job(**job_data)

# Execute job
result = local_execute(job, params, run_id='{run_id}')

# Save result
with open('result.json', 'w') as f:
    json.dump(result.model_dump(), f, indent=2)

# Upload result to GCS with retry
job_id = '{run_id}'
bucket = '{self.gcs_bucket}'

# Create directory structure
subprocess.run(['gsutil', 'mkdir', '-p', f'gs://{{bucket}}/jobs/{{job_id}}'],
              check=True, capture_output=True)

# Upload result file with retry
download_file('result.json', f'gs://{{bucket}}/jobs/{{job_id}}/result.json')

sys.exit(0 if result.status == 'success' else 1)
'''

        with self._temp_file_context(suffix=".py") as script_path:
            with open(script_path, "w") as f:
                f.write(script_content)
            return script_path

    def execute_job(
        self,
        job: Job,
        params: DictData,
        *,
        run_id: Optional[str] = None,
        event: Optional[Any] = None,
    ) -> Result:
        """Execute job on Google Cloud Batch with optimized performance.

        Args:
            job: Job to execute
            params: Job parameters
            run_id: Execution run ID
            event: Event for cancellation

        Returns:
            Result: Execution result
        """
        if event and event.is_set():
            return Result(
                status=FAILED,
                context={
                    "errors": {"message": "Execution was canceled before start"}
                },
                run_id=run_id or gen_id("gcp-batch"),
                extras={},
            )

        # Generate run ID if not provided
        if not run_id:
            run_id = gen_id(job.id or "gcp-batch", unique=True)

        trace = get_trace(run_id, extras=job.extras)
        trace.info(f"[GCP_BATCH]: Starting job execution: {job.id}")

        try:
            # Create optimized task script
            script_path = self._create_optimized_task_script(
                job, params, run_id
            )

            # Prepare file paths
            job_config_gcs_blob = f"jobs/{run_id}/job_config.json"
            params_gcs_blob = f"jobs/{run_id}/params.json"
            script_gcs_blob = f"jobs/{run_id}/task_script.py"

            # Upload files efficiently
            trace.info("[GCP_BATCH]: Uploading files to GCS")

            with self._temp_file_context(suffix=".json") as job_config_path:
                with open(job_config_path, "w") as f:
                    json.dump(job.model_dump(), f)
                job_config_gcs_url = self._upload_file_to_gcs(
                    job_config_path, job_config_gcs_blob
                )

            with self._temp_file_context(suffix=".json") as params_path:
                with open(params_path, "w") as f:
                    json.dump(params, f)
                params_gcs_url = self._upload_file_to_gcs(
                    params_path, params_gcs_blob
                )

            task_script_gcs_url = self._upload_file_to_gcs(
                script_path, script_gcs_blob
            )

            # Create job
            job_name = f"workflow-job-{run_id}"

            trace.info(f"[GCP_BATCH]: Creating job: {job_name}")
            job_full_name = self._create_job(
                job_name,
                task_script_gcs_url,
                job_config_gcs_url,
                params_gcs_url,
            )

            # Wait for job completion
            trace.info("[GCP_BATCH]: Waiting for job completion")
            job_result = self._wait_for_job_completion(job_full_name)

            # Process results
            if job_result["status"] == "completed":
                result_data = {}
                result_file_key = f"jobs/{run_id}/result.json"

                if result_file_key in job_result.get("files", {}):
                    try:
                        result_data = json.loads(
                            job_result["files"][result_file_key]
                        )
                    except (json.JSONDecodeError, KeyError):
                        result_data = {"status": SUCCESS}

                trace.info("[GCP_BATCH]: Job completed successfully")
                return Result(
                    status=SUCCESS,
                    context=result_data,
                    run_id=run_id,
                    extras=job.extras or {},
                )
            else:
                error_msg = f"Job failed: {job_result.get('status', 'unknown')}"
                if job_result.get("failure_reason"):
                    error_msg += f" - {job_result['failure_reason']}"

                trace.error(f"[GCP_BATCH]: {error_msg}")
                return Result(
                    status=FAILED,
                    context={"errors": {"message": error_msg}},
                    run_id=run_id,
                    extras=job.extras or {},
                )

        except Exception as e:
            trace.error(f"[GCP_BATCH]: Execution failed: {str(e)}")
            return Result(
                status=FAILED,
                context={"errors": {"message": str(e)}},
                run_id=run_id,
                extras=job.extras or {},
            )

    def cleanup(self, job_id: Optional[str] = None) -> None:
        """Clean up Google Cloud Batch resources efficiently.

        Args:
            job_id: Job ID to clean up (if None, cleans up all workflow jobs)
        """
        try:
            prefix = f"jobs/{job_id}/" if job_id else "jobs/"
            blobs = self.bucket.list_blobs(prefix=prefix)

            # Delete blobs in batches for better performance
            batch_size = 100
            blob_batch = []

            for blob in blobs:
                blob_batch.append(blob)
                if len(blob_batch) >= batch_size:
                    self.bucket.delete_blobs(blob_batch)
                    blob_batch = []

            # Delete remaining blobs
            if blob_batch:
                self.bucket.delete_blobs(blob_batch)

        except Exception:
            pass


def gcp_batch_execute(
    job: Job,
    params: DictData,
    *,
    run_id: Optional[str] = None,
    event: Optional[Any] = None,
) -> Result:
    """Google Cloud Batch job execution function with optimized performance.

    This function creates a Google Cloud Batch provider and executes the job
    on Google Cloud Batch compute resources. It handles the complete lifecycle
    including job creation, task submission, and result retrieval.

    Args:
        job: Job to execute
        params: Job parameters
        run_id: Execution run ID
        event: Event for cancellation

    Returns:
        Result: Execution result
    """
    # Extract Google Cloud Batch configuration from job
    batch_args = job.runs_on.args

    provider = GoogleCloudBatchProvider(
        project_id=batch_args.project_id,
        region=batch_args.region,
        gcs_bucket=batch_args.gcs_bucket,
        credentials_path=batch_args.credentials_path,
    )

    try:
        return provider.execute_job(job, params, run_id=run_id, event=event)
    finally:
        # Clean up resources
        if run_id:
            provider.cleanup(run_id)
