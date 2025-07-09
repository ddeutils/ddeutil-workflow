# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""AWS Batch Provider Module.

This module provides AWS Batch integration for workflow job execution.
It handles compute environment creation, job queue management, job submission,
task execution, and result retrieval.

The AWS Batch provider enables running workflow jobs on AWS Batch compute
environments, providing scalable and managed execution environments for complex
workflow processing.

Key Features:
    - Automatic compute environment creation and management
    - Job queue management and job submission
    - Result file upload/download via S3
    - Error handling and status monitoring
    - Resource cleanup and management
    - Optimized file operations and caching

Classes:
    AWSBatchProvider: Main provider for AWS Batch operations
    BatchComputeEnvironmentConfig: Configuration for AWS Batch compute environments
    BatchJobQueueConfig: Configuration for AWS Batch job queues
    BatchJobConfig: Configuration for AWS Batch jobs
    BatchTaskConfig: Configuration for AWS Batch tasks

References:
    - https://docs.aws.amazon.com/batch/latest/userguide/what-is-batch.html
    - https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/batch.html

Config Example:

    ```dotenv
    export AWS_ACCESS_KEY_ID="your-access-key"
    export AWS_SECRET_ACCESS_KEY="your-secret-key"
    export AWS_DEFAULT_REGION="us-east-1"
    export AWS_BATCH_JOB_QUEUE_ARN="arn:aws:batch:region:account:job-queue/queue-name"
    export AWS_S3_BUCKET="your-s3-bucket"
    ```

    ```yaml
    jobs:
    my-job:
        runs-on:
        type: "aws_batch"
        with:
            job_queue_arn: "${AWS_BATCH_JOB_QUEUE_ARN}"
            s3_bucket: "${AWS_S3_BUCKET}"
            compute_environment_type: "EC2"
            instance_types: ["c5.large", "c5.xlarge"]
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
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError

    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False

from pydantic import BaseModel, Field

from ...__types import DictData
from ...job import Job
from ...result import FAILED, SUCCESS, Result
from ...traces import get_trace
from ...utils import gen_id


class BatchComputeEnvironmentConfig(BaseModel):
    """AWS Batch compute environment configuration."""

    compute_environment_name: str = Field(
        description="Unique compute environment name"
    )
    compute_environment_type: str = Field(
        default="EC2", description="Compute environment type (EC2/SPOT)"
    )
    instance_types: list[str] = Field(
        default=["c5.large"], description="EC2 instance types"
    )
    min_vcpus: int = Field(default=0, description="Minimum vCPUs")
    max_vcpus: int = Field(default=256, description="Maximum vCPUs")
    desired_vcpus: int = Field(default=0, description="Desired vCPUs")
    subnets: list[str] = Field(description="Subnet IDs for compute resources")
    security_group_ids: list[str] = Field(description="Security group IDs")
    instance_role: str = Field(description="IAM instance profile ARN")
    service_role: str = Field(description="IAM service role ARN")
    enable_managed_compute: bool = Field(
        default=True, description="Enable managed compute"
    )
    spot_iam_fleet_role: Optional[str] = Field(
        default=None, description="Spot IAM fleet role ARN"
    )
    bid_percentage: Optional[int] = Field(
        default=None, description="Spot bid percentage"
    )


class BatchJobQueueConfig(BaseModel):
    """AWS Batch job queue configuration."""

    job_queue_name: str = Field(description="Unique job queue name")
    state: str = Field(default="ENABLED", description="Job queue state")
    priority: int = Field(default=1, description="Job queue priority")
    compute_environment_order: list[dict[str, str]] = Field(
        description="Compute environment order"
    )
    scheduling_policy_arn: Optional[str] = Field(
        default=None, description="Scheduling policy ARN"
    )


class BatchJobConfig(BaseModel):
    """AWS Batch job configuration."""

    job_name: str = Field(description="Unique job name")
    job_queue_arn: str = Field(description="Job queue ARN")
    job_definition_arn: str = Field(description="Job definition ARN")
    parameters: Optional[dict[str, str]] = Field(
        default=None, description="Job parameters"
    )
    timeout: Optional[dict[str, int]] = Field(
        default=None, description="Job timeout"
    )
    retry_strategy: Optional[dict[str, Any]] = Field(
        default=None, description="Retry strategy"
    )
    depends_on: Optional[list[dict[str, str]]] = Field(
        default=None, description="Job dependencies"
    )


class BatchTaskConfig(BaseModel):
    """AWS Batch task configuration."""

    task_name: str = Field(description="Unique task name")
    command: list[str] = Field(description="Command to execute")
    vcpus: int = Field(default=1, description="Number of vCPUs")
    memory: int = Field(default=1024, description="Memory in MiB")
    job_role_arn: Optional[str] = Field(
        default=None, description="IAM job role ARN"
    )
    timeout: Optional[dict[str, int]] = Field(
        default=None, description="Task timeout"
    )
    environment_variables: Optional[dict[str, str]] = Field(
        default=None, description="Environment variables"
    )
    mount_points: Optional[list[dict[str, str]]] = Field(
        default=None, description="Mount points"
    )
    volumes: Optional[list[dict[str, Any]]] = Field(
        default=None, description="Volumes"
    )


class AWSBatchProvider:
    """AWS Batch provider for workflow job execution.

    This provider handles the complete lifecycle of AWS Batch operations
    including compute environment creation, job queue management, job submission,
    task execution, and result retrieval. It integrates with S3 for file management
    and provides comprehensive error handling and monitoring.

    Attributes:
        batch_client: AWS Batch client
        s3_client: AWS S3 client
        ec2_client: AWS EC2 client
        iam_client: AWS IAM client
        s3_bucket: S3 bucket name for files
        compute_env_config: Compute environment configuration
        job_queue_config: Job queue configuration
        job_config: Job configuration
        task_config: Task configuration

    Example:
        ```python
        provider = AWSBatchProvider(
            job_queue_arn="arn:aws:batch:region:account:job-queue/queue-name",
            s3_bucket="my-workflow-bucket",
            region_name="us-east-1"
        )

        result = provider.execute_job(job, params, run_id="job-123")
        ```
    """

    def __init__(
        self,
        job_queue_arn: str,
        s3_bucket: str,
        region_name: str = "us-east-1",
        compute_env_config: Optional[BatchComputeEnvironmentConfig] = None,
        job_queue_config: Optional[BatchJobQueueConfig] = None,
        job_config: Optional[BatchJobConfig] = None,
        task_config: Optional[BatchTaskConfig] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
    ):
        """Initialize AWS Batch provider.

        Args:
            job_queue_arn: AWS Batch job queue ARN
            s3_bucket: S3 bucket name for files
            region_name: AWS region name
            compute_env_config: Compute environment configuration
            job_queue_config: Job queue configuration
            job_config: Job configuration
            task_config: Task configuration
            aws_access_key_id: AWS access key ID
            aws_secret_access_key: AWS secret access key
            aws_session_token: AWS session token
        """
        if not AWS_AVAILABLE:
            raise ImportError(
                "AWS dependencies not available. "
                "Install with: pip install boto3"
            )

        self.job_queue_arn = job_queue_arn
        self.s3_bucket = s3_bucket
        self.region_name = region_name

        # Initialize AWS clients with optimized configuration
        session = boto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            region_name=region_name,
        )

        # Configure clients with retry and timeout settings
        config = Config(
            retries={"max_attempts": 3, "mode": "adaptive"},
            connect_timeout=30,
            read_timeout=300,
        )

        self.batch_client = session.client("batch", config=config)
        self.s3_client = session.client("s3", config=config)
        self.ec2_client = session.client("ec2", config=config)
        self.iam_client = session.client("iam", config=config)

        # Set configurations
        self.compute_env_config = compute_env_config
        self.job_queue_config = job_queue_config
        self.job_config = job_config
        self.task_config = task_config

        # Cache for bucket operations
        self._bucket_exists: Optional[bool] = None

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

    def _ensure_s3_bucket(self) -> None:
        """Ensure S3 bucket exists with optimized settings."""
        if self._bucket_exists is None:
            try:
                self.s3_client.head_bucket(Bucket=self.s3_bucket)
                self._bucket_exists = True
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code == "404":
                    # Create bucket with optimized settings
                    create_kwargs = {
                        "Bucket": self.s3_bucket,
                        "CreateBucketConfiguration": {
                            "LocationConstraint": self.region_name
                        },
                    }

                    # Add versioning for better data protection
                    self.s3_client.create_bucket(**create_kwargs)
                    self.s3_client.put_bucket_versioning(
                        Bucket=self.s3_bucket,
                        VersioningConfiguration={"Status": "Enabled"},
                    )

                    # Add lifecycle policy for cost optimization
                    lifecycle_config = {
                        "Rules": [
                            {
                                "ID": "workflow-cleanup",
                                "Status": "Enabled",
                                "Filter": {"Prefix": "jobs/"},
                                "Expiration": {
                                    "Days": 7  # Keep workflow files for 7 days
                                },
                            }
                        ]
                    }

                    try:
                        self.s3_client.put_bucket_lifecycle_configuration(
                            Bucket=self.s3_bucket,
                            LifecycleConfiguration=lifecycle_config,
                        )
                    except ClientError:
                        # Lifecycle configuration might not be supported
                        pass

                    self._bucket_exists = True
                else:
                    raise

    def _upload_file_to_s3(self, file_path: str, s3_key: str) -> str:
        """Upload file to S3 with optimized settings.

        Args:
            file_path: Local file path
            s3_key: S3 object key

        Returns:
            str: S3 object URL
        """
        self._ensure_s3_bucket()

        # Set optimized metadata for workflow files
        metadata = {
            "workflow_provider": "aws_batch",
            "upload_time": str(time.time()),
            "content_type": "application/octet-stream",
        }

        with open(file_path, "rb") as data:
            self.s3_client.upload_fileobj(
                data,
                self.s3_bucket,
                s3_key,
                ExtraArgs={
                    "Metadata": metadata,
                    "StorageClass": "STANDARD_IA",  # Use IA for cost optimization
                },
            )

        return f"s3://{self.s3_bucket}/{s3_key}"

    def _download_file_from_s3(self, s3_key: str, local_path: str) -> None:
        """Download file from S3 with optimized settings.

        Args:
            s3_key: S3 object key
            local_path: Local file path
        """
        self.s3_client.download_file(
            self.s3_bucket,
            s3_key,
            local_path,
            ExtraArgs={
                "RequestPayer": "requester"
            },  # Handle cross-account access
        )

    def _create_job_definition_if_not_exists(self, job_def_name: str) -> str:
        """Create AWS Batch job definition if it doesn't exist with optimized settings.

        Args:
            job_def_name: Job definition name

        Returns:
            str: Job definition ARN
        """
        try:
            response = self.batch_client.describe_job_definitions(
                jobDefinitionName=job_def_name, status="ACTIVE"
            )
            if response["jobDefinitions"]:
                return response["jobDefinitions"][0]["jobDefinitionArn"]
        except ClientError:
            pass

        # Create optimized job definition
        job_def_config = self.task_config or BatchTaskConfig(
            task_name=job_def_name, command=["python3", "task_script.py"]
        )

        # Build environment variables
        environment = []
        if job_def_config.environment_variables:
            for key, value in job_def_config.environment_variables.items():
                environment.append({"name": key, "value": value})

        # Add optimized environment variables
        environment.extend(
            [
                {"name": "PYTHONUNBUFFERED", "value": "1"},
                {"name": "PYTHONDONTWRITEBYTECODE", "value": "1"},
                {"name": "AWS_DEFAULT_REGION", "value": self.region_name},
            ]
        )

        # Build container properties
        container_props = {
            "image": "python:3.11-slim",
            "vcpus": job_def_config.vcpus,
            "memory": job_def_config.memory,
            "command": job_def_config.command,
            "environment": environment,
            "resourceRequirements": [
                {"type": "VCPU", "value": str(job_def_config.vcpus)},
                {"type": "MEMORY", "value": str(job_def_config.memory)},
            ],
        }

        # Add optional configurations
        if job_def_config.job_role_arn:
            container_props["jobRoleArn"] = job_def_config.job_role_arn
            container_props["executionRoleArn"] = job_def_config.job_role_arn

        if job_def_config.mount_points and job_def_config.volumes:
            container_props["mountPoints"] = job_def_config.mount_points
            container_props["volumes"] = job_def_config.volumes

        response = self.batch_client.register_job_definition(
            jobDefinitionName=job_def_name,
            type="container",
            containerProperties=container_props,
            platformCapabilities=["EC2"],  # Specify platform capabilities
        )

        return response["jobDefinitionArn"]

    def _create_job(
        self, job_name: str, job_def_arn: str, parameters: dict[str, str]
    ) -> str:
        """Create AWS Batch job with optimized settings.

        Args:
            job_name: Job name
            job_def_arn: Job definition ARN
            parameters: Job parameters

        Returns:
            str: Job ARN
        """
        job_config = self.job_config or BatchJobConfig(
            job_name=job_name,
            job_queue_arn=self.job_queue_arn,
            job_definition_arn=job_def_arn,
        )

        # Build job parameters
        job_params = {
            "jobName": job_name,
            "jobQueue": self.job_queue_arn,
            "jobDefinition": job_def_arn,
            "parameters": parameters or {},
        }

        # Add optional configurations
        if job_config.timeout:
            job_params["timeout"] = job_config.timeout

        if job_config.retry_strategy:
            job_params["retryStrategy"] = job_config.retry_strategy

        if job_config.depends_on:
            job_params["dependsOn"] = job_config.depends_on

        response = self.batch_client.submit_job(**job_params)
        return response["jobArn"]

    def _wait_for_job_completion(
        self, job_arn: str, timeout: int = 3600
    ) -> dict[str, Any]:
        """Wait for job completion with optimized polling.

        Args:
            job_arn: Job ARN
            timeout: Timeout in seconds

        Returns:
            Dict[str, Any]: Job results
        """
        start_time = time.time()
        poll_interval = 10  # Start with 10 second intervals

        while time.time() - start_time < timeout:
            try:
                response = self.batch_client.describe_jobs(jobs=[job_arn])
                job = response["jobs"][0]

                if job["status"] == "SUCCEEDED":
                    return self._process_successful_job(job, job_arn)

                elif job["status"] == "FAILED":
                    return self._process_failed_job(job)

                elif job["status"] in ["RUNNING", "SUBMITTED", "PENDING"]:
                    # Adaptive polling: increase interval for long-running jobs
                    if time.time() - start_time > 300:  # After 5 minutes
                        poll_interval = min(
                            poll_interval * 1.5, 60
                        )  # Max 60 seconds

                    time.sleep(poll_interval)
                else:
                    # For other states, use shorter polling
                    time.sleep(5)

            except ClientError as e:
                if e.response["Error"]["Code"] == "JobNotFoundException":
                    # Job might be deleted, wait a bit and retry
                    time.sleep(poll_interval)
                else:
                    # Continue polling on error with exponential backoff
                    poll_interval = min(poll_interval * 2, 60)
                    time.sleep(poll_interval)
            except Exception:
                # Continue polling on error with exponential backoff
                poll_interval = min(poll_interval * 2, 60)
                time.sleep(poll_interval)

        return {"status": "timeout", "exit_code": 1}

    def _process_successful_job(
        self, job: dict[str, Any], job_arn: str
    ) -> dict[str, Any]:
        """Process successful job and download results.

        Args:
            job: Job object
            job_arn: Job ARN

        Returns:
            Dict[str, Any]: Job results with files
        """
        result_files = {}
        try:
            # List objects in job's S3 prefix
            job_id = job_arn.split("/")[-1]
            prefix = f"jobs/{job_id}/"

            response = self.s3_client.list_objects_v2(
                Bucket=self.s3_bucket, Prefix=prefix
            )

            # Download result files efficiently
            for obj in response.get("Contents", []):
                if obj["Key"].endswith((".json", ".txt", ".log")):
                    with self._temp_file_context() as tmp_file:
                        self.s3_client.download_file(
                            self.s3_bucket, obj["Key"], tmp_file
                        )
                        with open(tmp_file) as f:
                            result_files[obj["Key"]] = f.read()
        except Exception:
            # File download failed, continue with empty results
            pass

        return {"status": "completed", "exit_code": 0, "files": result_files}

    def _process_failed_job(self, job: dict[str, Any]) -> dict[str, Any]:
        """Process failed job and extract error information.

        Args:
            job: Job object

        Returns:
            Dict[str, Any]: Failure information
        """
        failure_reason = "Job failed"

        # Try to extract more detailed error information
        if "attempts" in job and job["attempts"]:
            last_attempt = job["attempts"][-1]
            if "reason" in last_attempt:
                failure_reason = last_attempt["reason"]

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

def download_file(s3_url, local_path):
    """Download file with retry logic."""
    for attempt in range(3):
        try:
            subprocess.run(['aws', 's3', 'cp', s3_url, local_path],
                         check=True, capture_output=True, timeout=300)
            return True
        except subprocess.CalledProcessError:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)

# Install ddeutil-workflow with retry
install_package('ddeutil-workflow')

# Download files with retry
download_file(os.environ['JOB_CONFIG_S3_URL'], 'job_config.json')
download_file(os.environ['PARAMS_S3_URL'], 'params.json')
download_file(os.environ['SCRIPT_S3_URL'], 'task_script.py')

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

# Upload result to S3 with retry
job_id = '{run_id}'
bucket = '{self.s3_bucket}'

# Create directory structure
subprocess.run(['aws', 's3', 'mkdir', 's3://{{bucket}}/jobs/{{job_id}}'],
              check=True, capture_output=True)

# Upload result file with retry
download_file('result.json', f's3://{{bucket}}/jobs/{{job_id}}/result.json')

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
        """Execute job on AWS Batch with optimized performance.

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
                run_id=run_id or gen_id("aws-batch"),
                extras={},
            )

        # Generate run ID if not provided
        if not run_id:
            run_id = gen_id(job.id or "aws-batch", unique=True)

        trace = get_trace(run_id, extras=job.extras)
        trace.info(f"[AWS_BATCH]: Starting job execution: {job.id}")

        try:
            # Create job definition
            job_def_name = f"workflow-job-def-{run_id}"
            trace.info(f"[AWS_BATCH]: Creating job definition: {job_def_name}")
            job_def_arn = self._create_job_definition_if_not_exists(
                job_def_name
            )

            # Create optimized task script
            script_path = self._create_optimized_task_script(
                job, params, run_id
            )

            # Upload files efficiently
            job_config_s3_key = f"jobs/{run_id}/job_config.json"
            params_s3_key = f"jobs/{run_id}/params.json"
            script_s3_key = f"jobs/{run_id}/task_script.py"

            # Upload files efficiently
            trace.info("[AWS_BATCH]: Uploading files to S3")

            with self._temp_file_context(suffix=".json") as job_config_path:
                with open(job_config_path, "w") as f:
                    json.dump(job.model_dump(), f)
                self._upload_file_to_s3(job_config_path, job_config_s3_key)

            with self._temp_file_context(suffix=".json") as params_path:
                with open(params_path, "w") as f:
                    json.dump(params, f)
                self._upload_file_to_s3(params_path, params_s3_key)

            self._upload_file_to_s3(script_path, script_s3_key)

            # Create job
            job_name = f"workflow-job-{run_id}"
            job_parameters = {
                "job_config_s3_url": f"s3://{self.s3_bucket}/{job_config_s3_key}",
                "params_s3_url": f"s3://{self.s3_bucket}/{params_s3_key}",
                "script_s3_url": f"s3://{self.s3_bucket}/{script_s3_key}",
            }

            trace.info(f"[AWS_BATCH]: Creating job: {job_name}")
            job_arn = self._create_job(job_name, job_def_arn, job_parameters)

            # Wait for job completion
            trace.info("[AWS_BATCH]: Waiting for job completion")
            job_result = self._wait_for_job_completion(job_arn)

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

                trace.info("[AWS_BATCH]: Job completed successfully")
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

                trace.error(f"[AWS_BATCH]: {error_msg}")
                return Result(
                    status=FAILED,
                    context={"errors": {"message": error_msg}},
                    run_id=run_id,
                    extras=job.extras or {},
                )

        except Exception as e:
            trace.error(f"[AWS_BATCH]: Execution failed: {str(e)}")
            return Result(
                status=FAILED,
                context={"errors": {"message": str(e)}},
                run_id=run_id,
                extras=job.extras or {},
            )

    def cleanup(self, job_id: Optional[str] = None) -> None:
        """Clean up AWS Batch resources efficiently.

        Args:
            job_id: Job ID to clean up (if None, cleans up all workflow jobs)
        """
        try:
            prefix = f"jobs/{job_id}/" if job_id else "jobs/"

            # List objects with pagination for large datasets
            paginator = self.s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.s3_bucket, Prefix=prefix)

            # Delete objects in batches for better performance
            batch_size = 1000
            objects_to_delete = []

            for page in pages:
                for obj in page.get("Contents", []):
                    objects_to_delete.append({"Key": obj["Key"]})

                    if len(objects_to_delete) >= batch_size:
                        self.s3_client.delete_objects(
                            Bucket=self.s3_bucket,
                            Delete={"Objects": objects_to_delete},
                        )
                        objects_to_delete = []

            # Delete remaining objects
            if objects_to_delete:
                self.s3_client.delete_objects(
                    Bucket=self.s3_bucket, Delete={"Objects": objects_to_delete}
                )

        except Exception:
            pass


def aws_batch_execute(
    job: Job,
    params: DictData,
    *,
    run_id: Optional[str] = None,
    event: Optional[Any] = None,
) -> Result:
    """AWS Batch job execution function with optimized performance.

    This function creates an AWS Batch provider and executes the job
    on AWS Batch compute environments. It handles the complete lifecycle
    including job definition creation, job submission, and result retrieval.

    Args:
        job: Job to execute
        params: Job parameters
        run_id: Execution run ID
        event: Event for cancellation

    Returns:
        Result: Execution result
    """
    # Extract AWS Batch configuration from job
    batch_args = job.runs_on.args

    provider = AWSBatchProvider(
        job_queue_arn=batch_args.job_queue_arn,
        s3_bucket=batch_args.s3_bucket,
        region_name=batch_args.region_name,
        aws_access_key_id=batch_args.aws_access_key_id,
        aws_secret_access_key=batch_args.aws_secret_access_key,
        aws_session_token=batch_args.aws_session_token,
    )

    try:
        return provider.execute_job(job, params, run_id=run_id, event=event)
    finally:
        # Clean up resources
        if run_id:
            provider.cleanup(run_id)
