# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Container Provider Module.

This module provides container-based execution for workflow jobs, enabling
workflow execution inside Docker containers on any self-hosted server.

The Container provider enables running workflow jobs in isolated container
environments, providing consistent execution environments across different
operating systems and infrastructure.

Key Features:
    - Multi-OS container support (Ubuntu, Windows, Linux)
    - Self-hosted server compatibility
    - Isolated execution environments
    - File volume mounting and sharing
    - Result collection and error handling
    - Resource cleanup and management

Classes:
    ContainerProvider: Main provider for container operations
    ContainerConfig: Configuration for container execution
    VolumeConfig: Configuration for volume mounting
    NetworkConfig: Configuration for container networking

Config Example:

    ```yaml
    jobs:
    my-job:
        runs-on:
        type: "container"
        with:
            image: "ubuntu:20.04"
            container_name: "workflow-{run_id}"
            volumes:
                - source: "/host/data"
                  target: "/container/data"
                  mode: "rw"
            environment:
                PYTHONPATH: "/app"
            resources:
                memory: "2g"
                cpu: "2"
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
from typing import Any, Optional, Union

try:
    import docker

    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

from pydantic import BaseModel, Field

from ...__types import DictData
from ...job import Job
from ...result import FAILED, SUCCESS, Result
from ...traces import get_trace
from ...utils import gen_id


class VolumeConfig(BaseModel):
    """Container volume configuration."""

    source: str = Field(description="Host path to mount")
    target: str = Field(description="Container path to mount to")
    mode: str = Field(default="rw", description="Mount mode (ro/rw)")


class NetworkConfig(BaseModel):
    """Container network configuration."""

    network_name: Optional[str] = Field(
        default=None, description="Network name"
    )
    network_mode: str = Field(default="bridge", description="Network mode")
    ports: Optional[dict[str, str]] = Field(
        default=None, description="Port mappings"
    )


class ResourceConfig(BaseModel):
    """Container resource configuration."""

    memory: Optional[str] = Field(
        default=None, description="Memory limit (e.g., '2g')"
    )
    cpu: Optional[Union[str, float]] = Field(
        default=None, description="CPU limit"
    )
    cpuset_cpus: Optional[str] = Field(default=None, description="CPU set")
    memswap_limit: Optional[str] = Field(
        default=None, description="Memory swap limit"
    )


class ContainerConfig(BaseModel):
    """Container execution configuration."""

    image: str = Field(description="Docker image to use")
    container_name: Optional[str] = Field(
        default=None, description="Container name"
    )
    volumes: Optional[list[VolumeConfig]] = Field(
        default=None, description="Volume mounts"
    )
    environment: Optional[dict[str, str]] = Field(
        default=None, description="Environment variables"
    )
    network: Optional[NetworkConfig] = Field(
        default=None, description="Network configuration"
    )
    resources: Optional[ResourceConfig] = Field(
        default=None, description="Resource limits"
    )
    working_dir: Optional[str] = Field(
        default="/app", description="Working directory"
    )
    user: Optional[str] = Field(default=None, description="User to run as")
    command: Optional[str] = Field(
        default=None, description="Override default command"
    )
    timeout: int = Field(
        default=3600, description="Execution timeout in seconds"
    )
    remove: bool = Field(
        default=True, description="Remove container after execution"
    )


class ContainerProvider:
    """Container provider for workflow job execution.

    This provider handles the complete lifecycle of container operations
    including container creation, job execution, result collection, and
    cleanup. It supports multiple operating systems and provides isolated
    execution environments.

    Attributes:
        docker_client: Docker client for container operations
        config: Container configuration
        base_volumes: Base volume mounts for workflow files

    Example:
        ```python
        provider = ContainerProvider(
            image="ubuntu:20.04",
            volumes=[
                VolumeConfig(source="/host/data", target="/container/data")
            ],
            environment={"PYTHONPATH": "/app"}
        )

        result = provider.execute_job(job, params, run_id="job-123")
        ```
    """

    def __init__(
        self,
        image: str,
        container_name: Optional[str] = None,
        volumes: Optional[list[VolumeConfig]] = None,
        environment: Optional[dict[str, str]] = None,
        network: Optional[NetworkConfig] = None,
        resources: Optional[ResourceConfig] = None,
        working_dir: str = "/app",
        user: Optional[str] = None,
        command: Optional[str] = None,
        timeout: int = 3600,
        remove: bool = True,
        docker_host: Optional[str] = None,
    ):
        """Initialize Container provider.

        Args:
            image: Docker image to use
            container_name: Container name
            volumes: Volume mounts
            environment: Environment variables
            network: Network configuration
            resources: Resource limits
            working_dir: Working directory
            user: User to run as
            command: Override default command
            timeout: Execution timeout
            remove: Remove container after execution
            docker_host: Docker host URL
        """
        if not DOCKER_AVAILABLE:
            raise ImportError(
                "Docker dependencies not available. "
                "Install with: pip install docker"
            )

        self.config = ContainerConfig(
            image=image,
            container_name=container_name,
            volumes=volumes or [],
            environment=environment or {},
            network=network,
            resources=resources,
            working_dir=working_dir,
            user=user,
            command=command,
            timeout=timeout,
            remove=remove,
        )

        # Initialize Docker client
        self.docker_client = docker.from_env(base_url=docker_host)

        # Base volumes for workflow files
        self.base_volumes = []

    def _create_workflow_volume(self, run_id: str) -> str:
        """Create temporary volume for workflow files.

        Args:
            run_id: Execution run ID

        Returns:
            str: Volume name
        """
        volume_name = f"workflow-{run_id}"
        try:
            self.docker_client.volumes.get(volume_name)
        except docker.errors.NotFound:
            self.docker_client.volumes.create(name=volume_name)
        return volume_name

    def _prepare_container_volumes(self, run_id: str) -> list[dict[str, str]]:
        """Prepare container volume mounts.

        Args:
            run_id: Execution run ID

        Returns:
            List[Dict[str, str]]: Volume mount configurations
        """
        volumes = []

        # Add workflow volume
        workflow_volume = self._create_workflow_volume(run_id)
        volumes.append(
            {"type": "volume", "source": workflow_volume, "target": "/workflow"}
        )

        # Add configured volumes
        for volume in self.config.volumes or []:
            volumes.append(
                {
                    "type": "bind",
                    "source": volume.source,
                    "target": volume.target,
                    "read_only": volume.mode == "ro",
                }
            )

        return volumes

    def _prepare_environment(
        self, run_id: str, job: Job, params: DictData
    ) -> dict[str, str]:
        """Prepare container environment variables.

        Args:
            run_id: Execution run ID
            job: Job to execute
            params: Job parameters

        Returns:
            Dict[str, str]: Environment variables
        """
        env = self.config.environment.copy()

        # Add workflow-specific environment
        env.update(
            {
                "WORKFLOW_RUN_ID": run_id,
                "WORKFLOW_JOB_ID": job.id or "unknown",
                "PYTHONPATH": "/workflow:/app",
                "WORKFLOW_WORKING_DIR": "/workflow",
            }
        )

        return env

    def _create_task_script(
        self, job: Job, params: DictData, run_id: str
    ) -> str:
        """Create Python script for task execution.

        Args:
            job: Job to execute
            params: Job parameters
            run_id: Execution run ID

        Returns:
            str: Script content
        """
        script_content = f"""
import json
import sys
import os
from pathlib import Path

# Add workflow directory to Python path
sys.path.insert(0, '/workflow')

from ddeutil.workflow.job import local_execute
from ddeutil.workflow import Job

# Change to workflow directory
os.chdir('/workflow')

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

# Exit with appropriate code
sys.exit(0 if result.status == 'success' else 1)
"""
        return script_content

    def _upload_files_to_volume(
        self, volume_name: str, job: Job, params: DictData, run_id: str
    ) -> None:
        """Upload files to container volume.

        Args:
            volume_name: Volume name
            job: Job to execute
            params: Job parameters
            run_id: Execution run ID
        """
        # Create temporary container to write files
        temp_container = self.docker_client.containers.run(
            image="alpine:latest",
            command="sh -c 'apk add --no-cache python3 && python3 -c \"import json; print('ready')\"'",
            volumes={volume_name: {"bind": "/workflow", "mode": "rw"}},
            detach=True,
            remove=True,
        )

        try:
            # Wait for container to be ready
            temp_container.wait()

            # Create task script
            script_content = self._create_task_script(job, params, run_id)

            # Write files to volume
            exec_result = temp_container.exec_run(
                cmd="sh -c 'cat > /workflow/task_script.py'", stdin=True
            )
            exec_result[1].write(script_content.encode())

            # Write job configuration
            job_config = json.dumps(job.model_dump(), indent=2)
            exec_result = temp_container.exec_run(
                cmd="sh -c 'cat > /workflow/job_config.json'", stdin=True
            )
            exec_result[1].write(job_config.encode())

            # Write parameters
            params_config = json.dumps(params, indent=2)
            exec_result = temp_container.exec_run(
                cmd="sh -c 'cat > /workflow/params.json'", stdin=True
            )
            exec_result[1].write(params_config.encode())

        finally:
            temp_container.stop()
            temp_container.remove()

    def _get_container_command(self) -> list[str]:
        """Get container command to execute.

        Returns:
            List[str]: Command to execute
        """
        if self.config.command:
            return ["sh", "-c", self.config.command]

        # Default command to install ddeutil-workflow and run task
        return [
            "sh",
            "-c",
            "pip3 install ddeutil-workflow && python3 /workflow/task_script.py",
        ]

    def _wait_for_container_completion(
        self, container, timeout: int
    ) -> dict[str, Any]:
        """Wait for container completion and return results.

        Args:
            container: Docker container
            timeout: Timeout in seconds

        Returns:
            Dict[str, Any]: Container results
        """
        try:
            # Wait for container to finish
            result = container.wait(timeout=timeout)

            # Get container logs
            logs = container.logs().decode("utf-8")

            # Get result file if it exists
            result_data = {}
            try:
                result_file = container.exec_run("cat /workflow/result.json")
                if result_file[0] == 0:
                    result_data = json.loads(result_file[1].decode("utf-8"))
            except Exception:
                pass

            return {
                "status": (
                    "completed" if result["StatusCode"] == 0 else "failed"
                ),
                "exit_code": result["StatusCode"],
                "logs": logs,
                "result_data": result_data,
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "logs": container.logs().decode("utf-8") if container else "",
            }

    def execute_job(
        self,
        job: Job,
        params: DictData,
        *,
        run_id: Optional[str] = None,
        event: Optional[Any] = None,
    ) -> Result:
        """Execute job in container.

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
                run_id=run_id or gen_id("container"),
            )

        # Generate run ID if not provided
        if not run_id:
            run_id = gen_id(job.id or "container", unique=True)

        trace = get_trace(run_id, extras=job.extras)
        trace.info(f"[CONTAINER]: Starting job execution: {job.id}")

        container = None
        volume_name = None

        try:
            # Create workflow volume
            volume_name = self._create_workflow_volume(run_id)
            trace.info(f"[CONTAINER]: Created workflow volume: {volume_name}")

            # Upload files to volume
            trace.info("[CONTAINER]: Uploading files to volume")
            self._upload_files_to_volume(volume_name, job, params, run_id)

            # Prepare container configuration
            container_name = self.config.container_name or f"workflow-{run_id}"
            volumes = self._prepare_container_volumes(run_id)
            environment = self._prepare_environment(run_id, job, params)
            command = self._get_container_command()

            # Prepare host config
            host_config = self.docker_client.api.create_host_config(
                volumes=volumes,
                mem_limit=(
                    self.config.resources.memory
                    if self.config.resources
                    else None
                ),
                cpu_period=100000,
                cpu_quota=(
                    int(float(self.config.resources.cpu) * 100000)
                    if self.config.resources and self.config.resources.cpu
                    else None
                ),
                cpuset_cpus=(
                    self.config.resources.cpuset_cpus
                    if self.config.resources
                    else None
                ),
                memswap_limit=(
                    self.config.resources.memswap_limit
                    if self.config.resources
                    else None
                ),
                network_mode=(
                    self.config.network.network_mode
                    if self.config.network
                    else None
                ),
                port_bindings=(
                    self.config.network.ports if self.config.network else None
                ),
                user=self.config.user,
            )

            # Create and start container
            trace.info(f"[CONTAINER]: Creating container: {container_name}")
            container = self.docker_client.containers.run(
                image=self.config.image,
                name=container_name,
                command=command,
                environment=environment,
                working_dir=self.config.working_dir,
                host_config=host_config,
                detach=True,
                remove=self.config.remove,
            )

            # Wait for completion
            trace.info("[CONTAINER]: Waiting for container completion")
            result = self._wait_for_container_completion(
                container, self.config.timeout
            )

            # Process results
            if result["status"] == "completed":
                trace.info("[CONTAINER]: Container completed successfully")
                return Result(
                    status=SUCCESS,
                    context=result.get("result_data", {}),
                    run_id=run_id,
                    extras=job.extras,
                )
            else:
                error_msg = (
                    f"Container failed: {result.get('error', 'unknown error')}"
                )
                trace.error(f"[CONTAINER]: {error_msg}")
                return Result(
                    status=FAILED,
                    context={
                        "errors": {"message": error_msg},
                        "logs": result.get("logs", ""),
                    },
                    run_id=run_id,
                    extras=job.extras,
                )

        except Exception as e:
            trace.error(f"[CONTAINER]: Execution failed: {str(e)}")
            return Result(
                status=FAILED,
                context={"errors": {"message": str(e)}},
                run_id=run_id,
                extras=job.extras,
            )

        finally:
            # Cleanup
            if container and not self.config.remove:
                try:
                    container.stop()
                    container.remove()
                except Exception:
                    pass

    def cleanup(self, run_id: Optional[str] = None) -> None:
        """Clean up container resources.

        Args:
            run_id: Run ID to clean up (if None, cleans up all workflow resources)
        """
        try:
            if run_id:
                # Clean up specific run
                volume_name = f"workflow-{run_id}"
                try:
                    volume = self.docker_client.volumes.get(volume_name)
                    volume.remove()
                except Exception:
                    pass

                # Clean up container if it exists
                container_name = f"workflow-{run_id}"
                try:
                    container = self.docker_client.containers.get(
                        container_name
                    )
                    container.stop()
                    container.remove()
                except Exception:
                    pass
            else:
                # Clean up all workflow resources
                volumes = self.docker_client.volumes.list()
                for volume in volumes:
                    if volume.name.startswith("workflow-"):
                        volume.remove()

                containers = self.docker_client.containers.list(all=True)
                for container in containers:
                    if container.name.startswith("workflow-"):
                        container.stop()
                        container.remove()

        except Exception:
            pass


def container_execute(
    job: Job,
    params: DictData,
    *,
    run_id: Optional[str] = None,
    event: Optional[Any] = None,
) -> Result:
    """Container job execution function.

    This function creates a Container provider and executes the job
    inside a Docker container. It handles the complete lifecycle
    including container creation, job execution, and cleanup.

    Args:
        job: Job to execute
        params: Job parameters
        run_id: Execution run ID
        event: Event for cancellation

    Returns:
        Result: Execution result
    """
    # Extract container configuration from job
    container_args = job.runs_on.args

    provider = ContainerProvider(
        image=container_args.image,
        container_name=container_args.container_name,
        volumes=container_args.volumes,
        environment=container_args.environment,
        network=container_args.network,
        resources=container_args.resources,
        working_dir=container_args.working_dir,
        user=container_args.user,
        command=container_args.command,
        timeout=container_args.timeout,
        remove=container_args.remove,
        docker_host=container_args.docker_host,
    )

    try:
        return provider.execute_job(job, params, run_id=run_id, event=event)
    finally:
        # Clean up resources
        if run_id:
            provider.cleanup(run_id)
