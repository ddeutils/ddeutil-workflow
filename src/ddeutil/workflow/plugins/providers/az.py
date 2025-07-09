# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Azure Batch Provider Module.

This module provides Azure Batch integration for workflow job execution.
It handles pool creation, job submission, task execution, and result retrieval.

The Azure Batch provider enables running workflow jobs on Azure Batch compute
nodes, providing scalable and managed execution environments for complex
workflow processing.

Key Features:
    - Automatic pool creation and management
    - Job and task submission to Azure Batch
    - Result file upload/download via Azure Storage
    - Error handling and status monitoring
    - Resource cleanup and management
    - Optimized file operations and caching

Classes:
    AzureBatchProvider: Main provider for Azure Batch operations
    BatchPoolConfig: Configuration for Azure Batch pools
    BatchJobConfig: Configuration for Azure Batch jobs
    BatchTaskConfig: Configuration for Azure Batch tasks

References:
    - https://docs.microsoft.com/en-us/azure/batch/batch-python-tutorial
    - https://docs.microsoft.com/en-us/azure/batch/batch-api-basics

Config Example:

    ```dotenv
    export AZURE_BATCH_ACCOUNT_NAME="your-batch-account"
    export AZURE_BATCH_ACCOUNT_KEY="your-batch-key"
    export AZURE_BATCH_ACCOUNT_URL="https://your-batch-account.region.batch.azure.com"
    export AZURE_STORAGE_ACCOUNT_NAME="your-storage-account"
    export AZURE_STORAGE_ACCOUNT_KEY="your-storage-key"
    ```

    ```yaml
    jobs:
    my-job:
        runs-on:
        type: "azure_batch"
        with:
            batch_account_name: "${AZURE_BATCH_ACCOUNT_NAME}"
            batch_account_key: "${AZURE_BATCH_ACCOUNT_KEY}"
            batch_account_url: "${AZURE_BATCH_ACCOUNT_URL}"
            storage_account_name: "${AZURE_STORAGE_ACCOUNT_NAME}"
            storage_account_key: "${AZURE_STORAGE_ACCOUNT_KEY}"
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
    from azure.batch import BatchServiceClient
    from azure.batch.batch_auth import SharedKeyCredentials
    from azure.batch.models import (
        AutoUserSpecification,
        BatchErrorException,
        CloudServiceConfiguration,
        JobAddParameter,
        NetworkConfiguration,
        PoolAddParameter,
        PoolInformation,
        ResourceFile,
        StartTask,
        TaskAddParameter,
        TaskState,
        UserIdentity,
    )
    from azure.core.exceptions import AzureError
    from azure.storage.blob import BlobServiceClient

    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

from pydantic import BaseModel, Field

from ...__types import DictData
from ...job import Job
from ...result import FAILED, SUCCESS, Result
from ...traces import get_trace
from ...utils import gen_id


class BatchPoolConfig(BaseModel):
    """Azure Batch pool configuration."""

    pool_id: str = Field(description="Unique pool identifier")
    vm_size: str = Field(
        default="Standard_D2s_v3", description="VM size for compute nodes"
    )
    node_count: int = Field(default=1, description="Number of compute nodes")
    max_tasks_per_node: int = Field(
        default=4, description="Maximum tasks per node"
    )
    enable_auto_scale: bool = Field(
        default=False, description="Enable auto-scaling"
    )
    auto_scale_formula: Optional[str] = Field(
        default=None, description="Auto-scale formula"
    )
    os_family: str = Field(
        default="5", description="OS family (5=Ubuntu 20.04)"
    )
    os_version: str = Field(default="latest", description="OS version")
    enable_inter_node_communication: bool = Field(
        default=False, description="Enable inter-node communication"
    )
    network_configuration: Optional[dict[str, Any]] = Field(
        default=None, description="Network configuration"
    )


class BatchJobConfig(BaseModel):
    """Azure Batch job configuration."""

    job_id: str = Field(description="Unique job identifier")
    pool_id: str = Field(description="Pool ID to run the job on")
    display_name: Optional[str] = Field(
        default=None, description="Job display name"
    )
    priority: int = Field(default=0, description="Job priority")
    uses_task_dependencies: bool = Field(
        default=False, description="Use task dependencies"
    )
    on_all_tasks_complete: str = Field(
        default="noaction", description="Action when all tasks complete"
    )
    on_task_failure: str = Field(
        default="noaction", description="Action when task fails"
    )
    metadata: Optional[list[dict[str, str]]] = Field(
        default=None, description="Job metadata"
    )


class BatchTaskConfig(BaseModel):
    """Azure Batch task configuration."""

    task_id: str = Field(description="Unique task identifier")
    command_line: str = Field(description="Command line to execute")
    resource_files: Optional[list[ResourceFile]] = Field(
        default=None, description="Resource files"
    )
    environment_settings: Optional[dict[str, str]] = Field(
        default=None, description="Environment variables"
    )
    max_wall_clock_time: Optional[str] = Field(
        default="PT1H", description="Maximum wall clock time"
    )
    retention_time: Optional[str] = Field(
        default="PT1H", description="Task retention time"
    )
    user_identity: Optional[dict[str, Any]] = Field(
        default=None, description="User identity"
    )
    constraints: Optional[dict[str, Any]] = Field(
        default=None, description="Task constraints"
    )


class AzureBatchProvider:
    """Azure Batch provider for workflow job execution.

    This provider handles the complete lifecycle of Azure Batch operations
    including pool creation, job submission, task execution, and result
    retrieval. It integrates with Azure Storage for file management and
    provides comprehensive error handling and monitoring.

    Attributes:
        batch_client: Azure Batch service client
        blob_client: Azure Blob storage client
        storage_container: Storage container name for files
        pool_config: Pool configuration
        job_config: Job configuration
        task_config: Task configuration

    Example:
        ```python
        provider = AzureBatchProvider(
            batch_account_name="mybatchaccount",
            batch_account_key="mykey",
            batch_account_url="https://mybatchaccount.region.batch.azure.com",
            storage_account_name="mystorageaccount",
            storage_account_key="mystoragekey"
        )

        result = provider.execute_job(job, params, run_id="job-123")
        ```
    """

    def __init__(
        self,
        batch_account_name: str,
        batch_account_key: str,
        batch_account_url: str,
        storage_account_name: str,
        storage_account_key: str,
        storage_container: str = "workflow-files",
        pool_config: Optional[BatchPoolConfig] = None,
        job_config: Optional[BatchJobConfig] = None,
        task_config: Optional[BatchTaskConfig] = None,
    ):
        """Initialize Azure Batch provider.

        Args:
            batch_account_name: Azure Batch account name
            batch_account_key: Azure Batch account key
            batch_account_url: Azure Batch account URL
            storage_account_name: Azure Storage account name
            storage_account_key: Azure Storage account key
            storage_container: Storage container name for files
            pool_config: Pool configuration
            job_config: Job configuration
            task_config: Task configuration
        """
        if not AZURE_AVAILABLE:
            raise ImportError(
                "Azure Batch dependencies not available. "
                "Install with: pip install ddeutil-workflow[azure]"
            )

        self.batch_account_name = batch_account_name
        self.batch_account_key = batch_account_key
        self.batch_account_url = batch_account_url
        self.storage_account_name = storage_account_name
        self.storage_account_key = storage_account_key
        self.storage_container = storage_container

        # Initialize clients with optimized configuration
        self.batch_client = self._create_batch_client()
        self.blob_client = self._create_blob_client()

        # Set configurations
        self.pool_config = pool_config or BatchPoolConfig(
            pool_id=f"workflow-pool-{gen_id('pool')}"
        )
        self.job_config = job_config
        self.task_config = task_config

        # Cache for container operations
        self._container_exists: Optional[bool] = None

    def _create_batch_client(self) -> BatchServiceClient:
        """Create Azure Batch service client with optimized configuration."""
        credentials = SharedKeyCredentials(
            self.batch_account_name, self.batch_account_key
        )
        return BatchServiceClient(credentials, self.batch_account_url)

    def _create_blob_client(self) -> BlobServiceClient:
        """Create Azure Blob storage client with optimized configuration."""
        connection_string = (
            f"DefaultEndpointsProtocol=https;"
            f"AccountName={self.storage_account_name};"
            f"AccountKey={self.storage_account_key};"
            f"EndpointSuffix=core.windows.net"
        )
        return BlobServiceClient.from_connection_string(connection_string)

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

    def _ensure_storage_container(self) -> None:
        """Ensure storage container exists with optimized settings."""
        if self._container_exists is None:
            container_client = self.blob_client.get_container_client(
                self.storage_container
            )
            try:
                container_client.get_container_properties()
                self._container_exists = True
            except AzureError:
                # Create container with optimized settings
                container_client.create_container(
                    metadata={
                        "workflow_provider": "azure_batch",
                        "created_time": str(time.time()),
                    }
                )
                self._container_exists = True

    def _upload_file_to_storage(self, file_path: str, blob_name: str) -> str:
        """Upload file to Azure Storage with optimized settings.

        Args:
            file_path: Local file path
            blob_name: Blob name in storage

        Returns:
            str: Blob URL
        """
        self._ensure_storage_container()
        container_client = self.blob_client.get_container_client(
            self.storage_container
        )
        blob_client = container_client.get_blob_client(blob_name)

        # Set optimized metadata
        metadata = {
            "workflow_provider": "azure_batch",
            "upload_time": str(time.time()),
            "content_type": "application/octet-stream",
        }

        with open(file_path, "rb") as data:
            blob_client.upload_blob(
                data,
                overwrite=True,
                metadata=metadata,
                content_settings=None,  # Let Azure determine content type
            )

        return blob_client.url

    def _download_file_from_storage(
        self, blob_name: str, local_path: str
    ) -> None:
        """Download file from Azure Storage with optimized settings.

        Args:
            blob_name: Blob name in storage
            local_path: Local file path
        """
        container_client = self.blob_client.get_container_client(
            self.storage_container
        )
        blob_client = container_client.get_blob_client(blob_name)

        with open(local_path, "wb") as data:
            blob_client.download_blob().readinto(data)

    def _create_optimized_pool(self, pool_id: str) -> None:
        """Create Azure Batch pool with optimized settings.

        Args:
            pool_id: Pool identifier
        """
        try:
            self.batch_client.pool.get(pool_id)
            return
        except BatchErrorException as e:
            if e.response.status_code != 404:
                raise

        pool_config = self.pool_config

        # Create optimized start task for pool initialization
        start_task = StartTask(
            command_line=(
                "apt-get update && "
                "apt-get install -y python3 python3-pip curl && "
                "pip3 install --no-cache-dir ddeutil-workflow && "
                "echo 'Pool initialization completed'"
            ),
            wait_for_success=True,
            user_identity=UserIdentity(
                auto_user=AutoUserSpecification(
                    scope="pool", elevation_level="admin"
                )
            ),
            max_task_retry_count=2,
        )

        # Build pool configuration
        pool_params = {
            "id": pool_id,
            "vm_size": pool_config.vm_size,
            "target_dedicated_nodes": pool_config.node_count,
            "task_slots_per_node": pool_config.max_tasks_per_node,
            "enable_auto_scale": pool_config.enable_auto_scale,
            "start_task": start_task,
            "enable_inter_node_communication": pool_config.enable_inter_node_communication,
        }

        # Add auto-scale formula if enabled
        if pool_config.enable_auto_scale and pool_config.auto_scale_formula:
            pool_params["auto_scale_formula"] = pool_config.auto_scale_formula

        # Add network configuration if specified
        if pool_config.network_configuration:
            pool_params["network_configuration"] = NetworkConfiguration(
                **pool_config.network_configuration
            )

        # Use Cloud Service configuration for better compatibility
        pool_params["cloud_service_configuration"] = CloudServiceConfiguration(
            os_family=pool_config.os_family, os_version=pool_config.os_version
        )

        new_pool = PoolAddParameter(**pool_params)
        self.batch_client.pool.add(new_pool)

        # Wait for pool to be ready with optimized polling
        self._wait_for_pool_ready(pool_id)

    def _wait_for_pool_ready(self, pool_id: str, timeout: int = 1800) -> None:
        """Wait for pool to be ready with optimized polling.

        Args:
            pool_id: Pool identifier
            timeout: Timeout in seconds
        """
        start_time = time.time()
        poll_interval = 10

        while time.time() - start_time < timeout:
            try:
                pool = self.batch_client.pool.get(pool_id)

                if (
                    pool.state.value == "active"
                    and pool.allocation_state.value == "steady"
                ):
                    return
                elif pool.state.value in ["deleting", "upgrading"]:
                    raise Exception(
                        f"Pool {pool_id} is in invalid state: {pool.state.value}"
                    )

                # Adaptive polling
                if time.time() - start_time > 300:  # After 5 minutes
                    poll_interval = min(poll_interval * 1.5, 60)

                time.sleep(poll_interval)

            except BatchErrorException as e:
                if e.response.status_code == 404:
                    # Pool might be deleted, wait and retry
                    time.sleep(poll_interval)
                else:
                    raise

        raise Exception(
            f"Pool {pool_id} did not become ready within {timeout} seconds"
        )

    def _create_job(self, job_id: str, pool_id: str) -> None:
        """Create Azure Batch job with optimized settings.

        Args:
            job_id: Job identifier
            pool_id: Pool identifier
        """
        job_config = self.job_config or BatchJobConfig(
            job_id=job_id, pool_id=pool_id
        )

        # Build job parameters
        job_params = {
            "id": job_id,
            "pool_info": PoolInformation(pool_id=pool_id),
            "priority": job_config.priority,
            "uses_task_dependencies": job_config.uses_task_dependencies,
            "on_all_tasks_complete": job_config.on_all_tasks_complete,
            "on_task_failure": job_config.on_task_failure,
        }

        # Add optional configurations
        if job_config.display_name:
            job_params["display_name"] = job_config.display_name

        if job_config.metadata:
            job_params["metadata"] = job_config.metadata

        job = JobAddParameter(**job_params)
        self.batch_client.job.add(job)

    def _create_task(
        self,
        job_id: str,
        task_id: str,
        command_line: str,
        resource_files: Optional[list[ResourceFile]] = None,
        environment_settings: Optional[dict[str, str]] = None,
    ) -> None:
        """Create Azure Batch task with optimized settings.

        Args:
            job_id: Job identifier
            task_id: Task identifier
            command_line: Command line to execute
            resource_files: Resource files for the task
            environment_settings: Environment variables
        """
        task_config = self.task_config or BatchTaskConfig(
            task_id=task_id, command_line=command_line
        )

        # Convert environment settings to Azure Batch format
        env_settings = None
        if environment_settings:
            env_settings = [
                {"name": k, "value": v} for k, v in environment_settings.items()
            ]

        # Add optimized environment variables
        if env_settings is None:
            env_settings = []

        env_settings.extend(
            [
                {"name": "PYTHONUNBUFFERED", "value": "1"},
                {"name": "PYTHONDONTWRITEBYTECODE", "value": "1"},
            ]
        )

        # Build task parameters
        task_params = {
            "id": task_id,
            "command_line": command_line,
            "resource_files": resource_files or task_config.resource_files,
            "environment_settings": env_settings,
            "max_wall_clock_time": task_config.max_wall_clock_time,
            "retention_time": task_config.retention_time,
        }

        # Add optional configurations
        if task_config.user_identity:
            task_params["user_identity"] = UserIdentity(
                **task_config.user_identity
            )

        if task_config.constraints:
            task_params["constraints"] = task_config.constraints

        task = TaskAddParameter(**task_params)
        self.batch_client.task.add(job_id, task)

    def _wait_for_task_completion(
        self, job_id: str, task_id: str, timeout: int = 3600
    ) -> dict[str, Any]:
        """Wait for task completion with optimized polling.

        Args:
            job_id: Job identifier
            task_id: Task identifier
            timeout: Timeout in seconds

        Returns:
            Dict[str, Any]: Task results
        """
        start_time = time.time()
        poll_interval = 10

        while time.time() - start_time < timeout:
            try:
                task = self.batch_client.task.get(job_id, task_id)

                if task.state == TaskState.completed:
                    return self._process_successful_task(job_id, task_id, task)

                elif task.state == TaskState.failed:
                    return self._process_failed_task(task)

                elif task.state in [
                    TaskState.running,
                    TaskState.active,
                    TaskState.preparing,
                ]:
                    # Adaptive polling: increase interval for long-running tasks
                    if time.time() - start_time > 300:  # After 5 minutes
                        poll_interval = min(
                            poll_interval * 1.5, 60
                        )  # Max 60 seconds

                    time.sleep(poll_interval)
                else:
                    # For other states, use shorter polling
                    time.sleep(5)

            except BatchErrorException as e:
                if e.response.status_code == 404:
                    # Task might be deleted, wait a bit and retry
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

    def _process_successful_task(
        self, job_id: str, task_id: str, task: Any
    ) -> dict[str, Any]:
        """Process successful task and download results.

        Args:
            job_id: Job identifier
            task_id: Task identifier
            task: Task object

        Returns:
            Dict[str, Any]: Task results with files
        """
        result_files = {}
        try:
            # Get task files
            files = self.batch_client.file.list_from_task(job_id, task_id)
            for file in files:
                if file.name in ["stdout.txt", "stderr.txt", "result.json"]:
                    with self._temp_file_context() as tmp_file:
                        self.batch_client.file.get_from_task(
                            job_id, task_id, file.name, tmp_file
                        )
                        with open(tmp_file) as f:
                            result_files[file.name] = f.read()
        except Exception:
            # File download failed, continue with empty results
            pass

        return {
            "status": "completed",
            "exit_code": task.execution_info.exit_code,
            "files": result_files,
        }

    def _process_failed_task(self, task: Any) -> dict[str, Any]:
        """Process failed task and extract error information.

        Args:
            task: Task object

        Returns:
            Dict[str, Any]: Failure information
        """
        failure_reason = "Task failed"

        # Try to extract more detailed error information
        if hasattr(task, "execution_info") and task.execution_info:
            if (
                hasattr(task.execution_info, "failure_info")
                and task.execution_info.failure_info
            ):
                failure_reason = str(task.execution_info.failure_info)

        return {
            "status": "failed",
            "exit_code": (
                task.execution_info.exit_code if task.execution_info else 1
            ),
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

def download_file(blob_url, local_path):
    """Download file with retry logic."""
    for attempt in range(3):
        try:
            subprocess.run(['az', 'storage', 'blob', 'download',
                          '--account-name', os.environ['STORAGE_ACCOUNT_NAME'],
                          '--account-key', os.environ['STORAGE_ACCOUNT_KEY'],
                          '--container-name', os.environ['STORAGE_CONTAINER'],
                          '--name', blob_url, '--file', local_path],
                         check=True, capture_output=True, timeout=300)
            return True
        except subprocess.CalledProcessError:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)

# Install ddeutil-workflow with retry
install_package('ddeutil-workflow')

# Download files with retry
download_file(os.environ['JOB_CONFIG_BLOB'], 'job_config.json')
download_file(os.environ['PARAMS_BLOB'], 'params.json')
download_file(os.environ['SCRIPT_BLOB'], 'task_script.py')

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

# Upload result to Azure Storage with retry
job_id = '{run_id}'
container = os.environ['STORAGE_CONTAINER']

# Upload result file with retry
download_file('result.json', f'jobs/{{job_id}}/result.json')

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
        """Execute job on Azure Batch with optimized performance.

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
                run_id=run_id or gen_id("azure-batch"),
                extras={},
            )

        # Generate run ID if not provided
        if not run_id:
            run_id = gen_id(job.id or "azure-batch", unique=True)

        trace = get_trace(run_id, extras=job.extras)
        trace.info(f"[AZURE_BATCH]: Starting job execution: {job.id}")

        try:
            # Create pool if not exists
            pool_id = self.pool_config.pool_id
            trace.info(f"[AZURE_BATCH]: Ensuring pool exists: {pool_id}")
            self._create_optimized_pool(pool_id)

            # Create job
            job_id = f"workflow-job-{run_id}"
            trace.info(f"[AZURE_BATCH]: Creating job: {job_id}")
            self._create_job(job_id, pool_id)

            # Create optimized task script
            script_path = self._create_optimized_task_script(
                job, params, run_id
            )

            # Upload files efficiently
            job_config_blob = f"{run_id}/job_config.json"
            params_blob = f"{run_id}/params.json"
            script_blob = f"{run_id}/task_script.py"

            # Upload files efficiently
            trace.info("[AZURE_BATCH]: Uploading files to storage")

            with self._temp_file_context(suffix=".json") as job_config_path:
                with open(job_config_path, "w") as f:
                    json.dump(job.model_dump(), f)
                self._upload_file_to_storage(job_config_path, job_config_blob)

            with self._temp_file_context(suffix=".json") as params_path:
                with open(params_path, "w") as f:
                    json.dump(params, f)
                self._upload_file_to_storage(params_path, params_blob)

            self._upload_file_to_storage(script_path, script_blob)

            # Create resource files
            resource_files = [
                ResourceFile(
                    file_path="job_config.json",
                    blob_source=self._upload_file_to_storage(
                        job_config_path, job_config_blob
                    ),
                ),
                ResourceFile(
                    file_path="params.json",
                    blob_source=self._upload_file_to_storage(
                        params_path, params_blob
                    ),
                ),
                ResourceFile(
                    file_path="task_script.py",
                    blob_source=self._upload_file_to_storage(
                        script_path, script_blob
                    ),
                ),
            ]

            # Create task with optimized settings
            task_id = f"workflow-task-{run_id}"
            command_line = "python3 task_script.py"

            # Set environment variables for the task
            environment_settings = {
                "STORAGE_ACCOUNT_NAME": self.storage_account_name,
                "STORAGE_ACCOUNT_KEY": self.storage_account_key,
                "STORAGE_CONTAINER": self.storage_container,
                "JOB_CONFIG_BLOB": job_config_blob,
                "PARAMS_BLOB": params_blob,
                "SCRIPT_BLOB": script_blob,
            }

            trace.info(f"[AZURE_BATCH]: Creating task: {task_id}")
            self._create_task(
                job_id=job_id,
                task_id=task_id,
                command_line=command_line,
                resource_files=resource_files,
                environment_settings=environment_settings,
            )

            # Wait for task completion
            trace.info("[AZURE_BATCH]: Waiting for task completion")
            task_result = self._wait_for_task_completion(job_id, task_id)

            # Process results
            if task_result["status"] == "completed":
                result_data = {}
                if "result.json" in task_result.get("files", {}):
                    try:
                        result_data = json.loads(
                            task_result["files"]["result.json"]
                        )
                    except (json.JSONDecodeError, KeyError):
                        result_data = {"status": SUCCESS}

                trace.info("[AZURE_BATCH]: Task completed successfully")
                return Result(
                    status=SUCCESS,
                    context=result_data,
                    run_id=run_id,
                    extras=job.extras or {},
                )
            else:
                error_msg = (
                    f"Task failed: {task_result.get('status', 'unknown')}"
                )
                if task_result.get("failure_reason"):
                    error_msg += f" - {task_result['failure_reason']}"

                trace.error(f"[AZURE_BATCH]: {error_msg}")
                return Result(
                    status=FAILED,
                    context={"errors": {"message": error_msg}},
                    run_id=run_id,
                    extras=job.extras or {},
                )

        except Exception as e:
            trace.error(f"[AZURE_BATCH]: Execution failed: {str(e)}")
            return Result(
                status=FAILED,
                context={"errors": {"message": str(e)}},
                run_id=run_id,
                extras=job.extras or {},
            )

    def cleanup(self, job_id: Optional[str] = None) -> None:
        """Clean up Azure Batch resources efficiently.

        Args:
            job_id: Job ID to clean up (if None, cleans up all workflow jobs)
        """
        try:
            if job_id:
                # Delete specific job
                self.batch_client.job.delete(job_id)
            else:
                # Delete all workflow jobs efficiently
                jobs = self.batch_client.job.list()
                workflow_jobs = [
                    job for job in jobs if job.id.startswith("workflow-job-")
                ]

                # Delete jobs in parallel (simplified approach)
                for job in workflow_jobs:
                    try:
                        self.batch_client.job.delete(job.id)
                    except BatchErrorException:
                        # Job might already be deleted
                        pass
        except Exception:
            pass


def azure_batch_execute(
    job: Job,
    params: DictData,
    *,
    run_id: Optional[str] = None,
    event: Optional[Any] = None,
) -> Result:
    """Azure Batch job execution function with optimized performance.

    This function creates an Azure Batch provider and executes the job
    on Azure Batch compute nodes. It handles the complete lifecycle
    including pool creation, job submission, and result retrieval.

    Args:
        job: Job to execute
        params: Job parameters
        run_id: Execution run ID
        event: Event for cancellation

    Returns:
        Result: Execution result
    """
    # Extract Azure Batch configuration from job
    batch_args = job.runs_on.args

    provider = AzureBatchProvider(
        batch_account_name=batch_args.batch_account_name,
        batch_account_key=batch_args.batch_account_key.get_secret_value(),
        batch_account_url=batch_args.batch_account_url,
        storage_account_name=batch_args.storage_account_name,
        storage_account_key=batch_args.storage_account_key.get_secret_value(),
    )

    try:
        return provider.execute_job(job, params, run_id=run_id, event=event)
    finally:
        # Clean up resources
        if run_id:
            provider.cleanup(f"workflow-job-{run_id}")
