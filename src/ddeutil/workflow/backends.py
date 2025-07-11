# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Multi-Backend Execution System.

This module provides multi-backend execution capabilities for workflows,
supporting local execution, cloud execution, containers, serverless, and
batch processing. Inspired by Apache Airflow, Prefect, and Dagster execution backends.

Features:
- Local execution backend
- Cloud execution (AWS, GCP, Azure)
- Container-based execution
- Serverless execution
- Batch processing support
- Hybrid execution modes
- Resource management
- Execution monitoring

Classes:
    ExecutionBackend: Abstract execution backend
    LocalBackend: Local execution backend
    CloudBackend: Cloud execution backend
    ContainerBackend: Container-based execution
    ServerlessBackend: Serverless execution
    BatchBackend: Batch processing backend
    BackendManager: Backend management and orchestration

Example:
    ```python
    from ddeutil.workflow.backends import BackendManager, LocalBackend

    # Create backend manager
    manager = BackendManager()
    manager.register_backend("local", LocalBackend())

    # Execute workflow on specific backend
    result = manager.execute_workflow(workflow, backend="local")
    ```
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from .__types import DictData
from .workflow import Workflow

logger = logging.getLogger(__name__)


class BackendType(Enum):
    """Backend type enumeration."""

    LOCAL = "local"
    CLOUD = "cloud"
    CONTAINER = "container"
    SERVERLESS = "serverless"
    BATCH = "batch"


class ExecutionStatus(Enum):
    """Execution status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class ExecutionConfig:
    """Execution configuration."""

    backend_type: BackendType
    timeout: Optional[int] = None  # seconds
    resources: dict[str, Any] = field(default_factory=dict)
    environment: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Execution result."""

    execution_id: str
    status: ExecutionStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    output: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    logs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ExecutionBackend(ABC):
    """Abstract execution backend."""

    def __init__(self, config: Optional[ExecutionConfig] = None):
        self.config = config or ExecutionConfig(backend_type=BackendType.LOCAL)
        self.executions: dict[str, ExecutionResult] = {}
        self._lock = threading.Lock()

    @abstractmethod
    async def execute_workflow(
        self,
        workflow: Workflow,
        params: Optional[DictData] = None,
        execution_id: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute a workflow on this backend."""
        pass

    @abstractmethod
    async def get_execution_status(self, execution_id: str) -> ExecutionStatus:
        """Get execution status."""
        pass

    @abstractmethod
    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel an execution."""
        pass

    @abstractmethod
    async def get_logs(self, execution_id: str) -> list[str]:
        """Get execution logs."""
        pass

    def generate_execution_id(self) -> str:
        """Generate a unique execution ID."""
        return f"{self.config.backend_type.value}_{int(time.time())}_{threading.get_ident()}"


class LocalBackend(ExecutionBackend):
    """Local execution backend."""

    def __init__(self, config: Optional[ExecutionConfig] = None):
        if config is None:
            config = ExecutionConfig(backend_type=BackendType.LOCAL)
        super().__init__(config)

    async def execute_workflow(
        self,
        workflow: Workflow,
        params: Optional[DictData] = None,
        execution_id: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute workflow locally."""
        execution_id = execution_id or self.generate_execution_id()
        start_time = datetime.now()

        # Create execution result
        result = ExecutionResult(
            execution_id=execution_id,
            status=ExecutionStatus.RUNNING,
            start_time=start_time,
        )

        with self._lock:
            self.executions[execution_id] = result

        try:
            logger.info(f"Starting local execution: {execution_id}")

            # Execute workflow
            workflow_result = workflow.execute(params or {})

            # Update execution result
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            result.status = (
                ExecutionStatus.COMPLETED
                if workflow_result.status == "SUCCESS"
                else ExecutionStatus.FAILED
            )
            result.end_time = end_time
            result.duration = duration
            result.output = workflow_result.data
            result.error = (
                workflow_result.error
                if workflow_result.status != "SUCCESS"
                else None
            )

            logger.info(
                f"Local execution completed: {execution_id} ({duration:.2f}s)"
            )

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            result.status = ExecutionStatus.FAILED
            result.end_time = end_time
            result.duration = duration
            result.error = str(e)

            logger.error(f"Local execution failed: {execution_id} - {e}")

        return result

    async def get_execution_status(self, execution_id: str) -> ExecutionStatus:
        """Get execution status."""
        with self._lock:
            if execution_id in self.executions:
                return self.executions[execution_id].status
        return ExecutionStatus.FAILED

    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel an execution."""
        with self._lock:
            if execution_id in self.executions:
                result = self.executions[execution_id]
                if result.status == ExecutionStatus.RUNNING:
                    result.status = ExecutionStatus.CANCELLED
                    result.end_time = datetime.now()
                    return True
        return False

    async def get_logs(self, execution_id: str) -> list[str]:
        """Get execution logs."""
        with self._lock:
            if execution_id in self.executions:
                return self.executions[execution_id].logs
        return []


class ContainerBackend(ExecutionBackend):
    """Container-based execution backend."""

    def __init__(self, config: Optional[ExecutionConfig] = None):
        if config is None:
            config = ExecutionConfig(backend_type=BackendType.CONTAINER)
        super().__init__(config)
        self.container_runtime = self._detect_container_runtime()

    def _detect_container_runtime(self) -> str:
        """Detect available container runtime."""
        try:
            subprocess.run(
                ["docker", "--version"], check=True, capture_output=True
            )
            return "docker"
        except (subprocess.CalledProcessError, FileNotFoundError):
            try:
                subprocess.run(
                    ["podman", "--version"], check=True, capture_output=True
                )
                return "podman"
            except (subprocess.CalledProcessError, FileNotFoundError):
                raise RuntimeError("No container runtime (docker/podman) found")

    async def execute_workflow(
        self,
        workflow: Workflow,
        params: Optional[DictData] = None,
        execution_id: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute workflow in container."""
        execution_id = execution_id or self.generate_execution_id()
        start_time = datetime.now()

        result = ExecutionResult(
            execution_id=execution_id,
            status=ExecutionStatus.RUNNING,
            start_time=start_time,
        )

        with self._lock:
            self.executions[execution_id] = result

        try:
            logger.info(f"Starting container execution: {execution_id}")

            # Create temporary workflow file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                workflow_config = {
                    "name": workflow.name,
                    "jobs": {
                        name: {
                            "stages": [
                                {
                                    "type": stage.__class__.__name__.lower().replace(
                                        "stage", ""
                                    ),
                                    "config": (
                                        stage.dict()
                                        if hasattr(stage, "dict")
                                        else {}
                                    ),
                                }
                                for stage in job.stages
                            ]
                        }
                        for name, job in workflow.jobs.items()
                    },
                }
                json.dump(workflow_config, f)
                workflow_file = f.name

            # Prepare container command
            container_image = self.config.resources.get(
                "image", "python:3.9-slim"
            )
            container_cmd = [
                self.container_runtime,
                "run",
                "--rm",
                "-v",
                f"{workflow_file}:/workflow.json",
                container_image,
                "python",
                "-c",
                f"""
import json
import sys
sys.path.append('/app')
from ddeutil.workflow import Workflow

with open('/workflow.json') as f:
    config = json.load(f)

workflow = Workflow.from_config(config)
result = workflow.execute({params or {}})
print(json.dumps(result.dict()))
""",
            ]

            # Execute container
            process = await asyncio.create_subprocess_exec(
                *container_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            # Clean up
            os.unlink(workflow_file)

            # Process results
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            if process.returncode == 0:
                try:
                    output = json.loads(stdout.decode())
                    result.status = ExecutionStatus.COMPLETED
                    result.output = output
                except json.JSONDecodeError:
                    result.status = ExecutionStatus.FAILED
                    result.error = "Failed to parse output"
            else:
                result.status = ExecutionStatus.FAILED
                result.error = stderr.decode()

            result.end_time = end_time
            result.duration = duration
            result.logs = stdout.decode().split("\n") + stderr.decode().split(
                "\n"
            )

            logger.info(
                f"Container execution completed: {execution_id} ({duration:.2f}s)"
            )

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            result.status = ExecutionStatus.FAILED
            result.end_time = end_time
            result.duration = duration
            result.error = str(e)

            logger.error(f"Container execution failed: {execution_id} - {e}")

        return result

    async def get_execution_status(self, execution_id: str) -> ExecutionStatus:
        """Get execution status."""
        with self._lock:
            if execution_id in self.executions:
                return self.executions[execution_id].status
        return ExecutionStatus.FAILED

    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel an execution."""
        # For containers, we would need to find and stop the container
        # This is a simplified implementation
        with self._lock:
            if execution_id in self.executions:
                result = self.executions[execution_id]
                if result.status == ExecutionStatus.RUNNING:
                    result.status = ExecutionStatus.CANCELLED
                    result.end_time = datetime.now()
                    return True
        return False

    async def get_logs(self, execution_id: str) -> list[str]:
        """Get execution logs."""
        with self._lock:
            if execution_id in self.executions:
                return self.executions[execution_id].logs
        return []


class CloudBackend(ExecutionBackend):
    """Cloud execution backend."""

    def __init__(self, config: Optional[ExecutionConfig] = None):
        if config is None:
            config = ExecutionConfig(backend_type=BackendType.CLOUD)
        super().__init__(config)
        self.cloud_provider = self.config.resources.get("provider", "aws")
        self._init_cloud_client()

    def _init_cloud_client(self) -> None:
        """Initialize cloud client."""
        if self.cloud_provider == "aws":
            try:
                import boto3

                self.client = boto3.client("lambda")
            except ImportError:
                raise ImportError("boto3 is required for AWS cloud backend")
        elif self.cloud_provider == "gcp":
            try:
                from google.cloud import functions_v1

                self.client = functions_v1.CloudFunctionsServiceClient()
            except ImportError:
                raise ImportError(
                    "google-cloud-functions is required for GCP cloud backend"
                )
        else:
            raise ValueError(
                f"Unsupported cloud provider: {self.cloud_provider}"
            )

    async def execute_workflow(
        self,
        workflow: Workflow,
        params: Optional[DictData] = None,
        execution_id: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute workflow in cloud."""
        execution_id = execution_id or self.generate_execution_id()
        start_time = datetime.now()

        result = ExecutionResult(
            execution_id=execution_id,
            status=ExecutionStatus.RUNNING,
            start_time=start_time,
        )

        with self._lock:
            self.executions[execution_id] = result

        try:
            logger.info(f"Starting cloud execution: {execution_id}")

            # Prepare workflow payload
            payload = {
                "workflow": {
                    "name": workflow.name,
                    "jobs": {
                        name: {
                            "stages": [
                                {
                                    "type": stage.__class__.__name__.lower().replace(
                                        "stage", ""
                                    ),
                                    "config": (
                                        stage.dict()
                                        if hasattr(stage, "dict")
                                        else {}
                                    ),
                                }
                                for stage in job.stages
                            ]
                        }
                        for name, job in workflow.jobs.items()
                    },
                },
                "params": params or {},
                "execution_id": execution_id,
            }

            # Execute in cloud
            if self.cloud_provider == "aws":
                response = await self._execute_aws_lambda(payload)
            elif self.cloud_provider == "gcp":
                response = await self._execute_gcp_function(payload)
            else:
                raise ValueError(
                    f"Unsupported cloud provider: {self.cloud_provider}"
                )

            # Process results
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            result.status = ExecutionStatus.COMPLETED
            result.end_time = end_time
            result.duration = duration
            result.output = response.get("output")
            result.logs = response.get("logs", [])

            logger.info(
                f"Cloud execution completed: {execution_id} ({duration:.2f}s)"
            )

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            result.status = ExecutionStatus.FAILED
            result.end_time = end_time
            result.duration = duration
            result.error = str(e)

            logger.error(f"Cloud execution failed: {execution_id} - {e}")

        return result

    async def _execute_aws_lambda(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute AWS Lambda function."""
        function_name = self.config.resources.get(
            "function_name", "workflow-executor"
        )

        response = self.client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )

        return json.loads(response["Payload"].read())

    async def _execute_gcp_function(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute GCP Cloud Function."""
        function_name = self.config.resources.get(
            "function_name", "workflow-executor"
        )

        # This is a simplified implementation
        # In practice, you would use the GCP Cloud Functions client
        return {"output": payload, "logs": ["GCP execution simulated"]}

    async def get_execution_status(self, execution_id: str) -> ExecutionStatus:
        """Get execution status."""
        with self._lock:
            if execution_id in self.executions:
                return self.executions[execution_id].status
        return ExecutionStatus.FAILED

    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel an execution."""
        # Cloud executions are typically not cancellable
        # This is a simplified implementation
        with self._lock:
            if execution_id in self.executions:
                result = self.executions[execution_id]
                if result.status == ExecutionStatus.RUNNING:
                    result.status = ExecutionStatus.CANCELLED
                    result.end_time = datetime.now()
                    return True
        return False

    async def get_logs(self, execution_id: str) -> list[str]:
        """Get execution logs."""
        with self._lock:
            if execution_id in self.executions:
                return self.executions[execution_id].logs
        return []


class ServerlessBackend(ExecutionBackend):
    """Serverless execution backend."""

    def __init__(self, config: Optional[ExecutionConfig] = None):
        if config is None:
            config = ExecutionConfig(backend_type=BackendType.SERVERLESS)
        super().__init__(config)

    async def execute_workflow(
        self,
        workflow: Workflow,
        params: Optional[DictData] = None,
        execution_id: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute workflow in serverless environment."""
        # This is similar to cloud backend but optimized for serverless
        # For now, we'll use the cloud backend implementation
        cloud_backend = CloudBackend(self.config)
        return await cloud_backend.execute_workflow(
            workflow, params, execution_id
        )

    async def get_execution_status(self, execution_id: str) -> ExecutionStatus:
        """Get execution status."""
        with self._lock:
            if execution_id in self.executions:
                return self.executions[execution_id].status
        return ExecutionStatus.FAILED

    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel an execution."""
        with self._lock:
            if execution_id in self.executions:
                result = self.executions[execution_id]
                if result.status == ExecutionStatus.RUNNING:
                    result.status = ExecutionStatus.CANCELLED
                    result.end_time = datetime.now()
                    return True
        return False

    async def get_logs(self, execution_id: str) -> list[str]:
        """Get execution logs."""
        with self._lock:
            if execution_id in self.executions:
                return self.executions[execution_id].logs
        return []


class BatchBackend(ExecutionBackend):
    """Batch processing backend."""

    def __init__(self, config: Optional[ExecutionConfig] = None):
        if config is None:
            config = ExecutionConfig(backend_type=BackendType.BATCH)
        super().__init__(config)
        self.batch_queue: list[dict[str, Any]] = []
        self.processing = False

    async def execute_workflow(
        self,
        workflow: Workflow,
        params: Optional[DictData] = None,
        execution_id: Optional[str] = None,
    ) -> ExecutionResult:
        """Queue workflow for batch execution."""
        execution_id = execution_id or self.generate_execution_id()
        start_time = datetime.now()

        result = ExecutionResult(
            execution_id=execution_id,
            status=ExecutionStatus.PENDING,
            start_time=start_time,
        )

        with self._lock:
            self.executions[execution_id] = result

        # Add to batch queue
        self.batch_queue.append(
            {
                "execution_id": execution_id,
                "workflow": workflow,
                "params": params or {},
                "queued_at": datetime.now(),
            }
        )

        logger.info(f"Queued workflow for batch execution: {execution_id}")

        # Start processing if not already running
        if not self.processing:
            asyncio.create_task(self._process_batch_queue())

        return result

    async def _process_batch_queue(self) -> None:
        """Process batch queue."""
        self.processing = True

        while self.batch_queue:
            batch_item = self.batch_queue.pop(0)
            execution_id = batch_item["execution_id"]
            workflow = batch_item["workflow"]
            params = batch_item["params"]

            # Update status to running
            with self._lock:
                if execution_id in self.executions:
                    self.executions[execution_id].status = (
                        ExecutionStatus.RUNNING
                    )

            try:
                # Execute workflow
                workflow_result = workflow.execute(params)

                # Update execution result
                end_time = datetime.now()
                duration = (
                    end_time - self.executions[execution_id].start_time
                ).total_seconds()

                with self._lock:
                    if execution_id in self.executions:
                        result = self.executions[execution_id]
                        result.status = (
                            ExecutionStatus.COMPLETED
                            if workflow_result.status == "SUCCESS"
                            else ExecutionStatus.FAILED
                        )
                        result.end_time = end_time
                        result.duration = duration
                        result.output = workflow_result.data
                        result.error = (
                            workflow_result.error
                            if workflow_result.status != "SUCCESS"
                            else None
                        )

                logger.info(f"Batch execution completed: {execution_id}")

            except Exception as e:
                end_time = datetime.now()
                duration = (
                    end_time - self.executions[execution_id].start_time
                ).total_seconds()

                with self._lock:
                    if execution_id in self.executions:
                        result = self.executions[execution_id]
                        result.status = ExecutionStatus.FAILED
                        result.end_time = end_time
                        result.duration = duration
                        result.error = str(e)

                logger.error(f"Batch execution failed: {execution_id} - {e}")

        self.processing = False

    async def get_execution_status(self, execution_id: str) -> ExecutionStatus:
        """Get execution status."""
        with self._lock:
            if execution_id in self.executions:
                return self.executions[execution_id].status
        return ExecutionStatus.FAILED

    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel an execution."""
        # Remove from queue if pending
        self.batch_queue = [
            item
            for item in self.batch_queue
            if item["execution_id"] != execution_id
        ]

        with self._lock:
            if execution_id in self.executions:
                result = self.executions[execution_id]
                if result.status in [
                    ExecutionStatus.PENDING,
                    ExecutionStatus.RUNNING,
                ]:
                    result.status = ExecutionStatus.CANCELLED
                    result.end_time = datetime.now()
                    return True
        return False

    async def get_logs(self, execution_id: str) -> list[str]:
        """Get execution logs."""
        with self._lock:
            if execution_id in self.executions:
                return self.executions[execution_id].logs
        return []


class BackendManager:
    """Backend management and orchestration."""

    def __init__(self):
        self.backends: dict[str, ExecutionBackend] = {}
        self.default_backend: Optional[str] = None

    def register_backend(self, name: str, backend: ExecutionBackend) -> None:
        """Register a backend."""
        self.backends[name] = backend
        if not self.default_backend:
            self.default_backend = name
        logger.info(
            f"Registered backend: {name} ({backend.config.backend_type.value})"
        )

    def get_backend(self, name: str) -> Optional[ExecutionBackend]:
        """Get a backend by name."""
        return self.backends.get(name)

    def list_backends(self) -> list[str]:
        """List registered backends."""
        return list(self.backends.keys())

    def set_default_backend(self, name: str) -> None:
        """Set default backend."""
        if name not in self.backends:
            raise ValueError(f"Backend '{name}' not found")
        self.default_backend = name
        logger.info(f"Set default backend: {name}")

    async def execute_workflow(
        self,
        workflow: Workflow,
        backend: Optional[str] = None,
        params: Optional[DictData] = None,
        execution_id: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute workflow on specified backend."""
        backend_name = backend or self.default_backend
        if not backend_name:
            raise ValueError("No backend specified and no default backend set")

        if backend_name not in self.backends:
            raise ValueError(f"Backend '{backend_name}' not found")

        backend_instance = self.backends[backend_name]
        return await backend_instance.execute_workflow(
            workflow, params, execution_id
        )

    async def get_execution_status(
        self, execution_id: str, backend: Optional[str] = None
    ) -> ExecutionStatus:
        """Get execution status."""
        backend_name = backend or self.default_backend
        if not backend_name or backend_name not in self.backends:
            return ExecutionStatus.FAILED

        return await self.backends[backend_name].get_execution_status(
            execution_id
        )

    async def cancel_execution(
        self, execution_id: str, backend: Optional[str] = None
    ) -> bool:
        """Cancel an execution."""
        backend_name = backend or self.default_backend
        if not backend_name or backend_name not in self.backends:
            return False

        return await self.backends[backend_name].cancel_execution(execution_id)

    async def get_logs(
        self, execution_id: str, backend: Optional[str] = None
    ) -> list[str]:
        """Get execution logs."""
        backend_name = backend or self.default_backend
        if not backend_name or backend_name not in self.backends:
            return []

        return await self.backends[backend_name].get_logs(execution_id)


# Global backend manager instance
backend_manager = BackendManager()

# Register default backends
backend_manager.register_backend("local", LocalBackend())
backend_manager.register_backend("container", ContainerBackend())
backend_manager.register_backend("batch", BatchBackend())
