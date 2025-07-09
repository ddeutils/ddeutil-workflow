# Container Provider for ddeutil-workflow

This module provides container-based execution for workflow jobs, enabling workflow execution inside Docker containers on any self-hosted server.

## Features

- **Multi-OS Support**: Run jobs on Ubuntu, Windows, Linux, and other container images
- **Self-Hosted Compatibility**: Works on any server with Docker installed
- **Isolated Execution**: Each job runs in its own container environment
- **Volume Mounting**: Mount host directories and volumes for data sharing
- **Resource Management**: Configure CPU, memory, and other resource limits
- **Network Configuration**: Customize container networking
- **Result Collection**: Automatic result retrieval and error handling
- **Resource Cleanup**: Automatic cleanup of containers and volumes

## Installation

### Prerequisites

1. **Docker**: Docker must be installed and running on the host system
2. **Python**: Python 3.9+ with pip
3. **Network Access**: Internet access for pulling container images

### Install Dependencies

```bash
# Install with container dependencies
pip install ddeutil-workflow[docker]

# Or install Docker dependencies separately
pip install docker>=7.1.0
```

## Configuration

### Basic Configuration

```yaml
# workflow.yml
name: "container-example"
description: "Example workflow using container execution"

params:
  data_path:
    type: str
    default: "/host/data"

  output_path:
    type: str
    default: "/container/output"

jobs:
  data-processing:
    id: "data-processing"
    desc: "Process data using container execution"

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
      - name: "start"
        type: "empty"
        echo: "Starting container job"

      - name: "process-data"
        type: "py"
        run: |
          import pandas as pd
          import os

          # Load and process data
          data = pd.read_csv('/container/data/input.csv')
          result = data.groupby('category').sum()

          # Save results
          os.makedirs('/container/output', exist_ok=True)
          result.to_csv('/container/output/result.csv')

          # Update context
          result.context.update({
              "processed_rows": len(data),
              "output_file": "/container/output/result.csv"
          })

      - name: "complete"
        type: "empty"
        echo: "Container job completed"
```

### Advanced Configuration

#### Custom Volume Mounting

```yaml
jobs:
  advanced-container:
    runs-on:
      type: "container"
      with:
        image: "python:3.11-slim"
        volumes:
          - source: "/host/data"
            target: "/container/data"
            mode: "ro"  # Read-only
          - source: "/host/output"
            target: "/container/output"
            mode: "rw"  # Read-write
          - source: "/host/config"
            target: "/container/config"
            mode: "rw"
```

#### Resource Limits

```yaml
jobs:
  resource-limited:
    runs-on:
      type: "container"
      with:
        image: "ubuntu:20.04"
        resources:
          memory: "4g"
          cpu: "2.5"
          cpuset_cpus: "0,1"
          memswap_limit: "8g"
```

#### Network Configuration

```yaml
jobs:
  networked:
    runs-on:
      type: "container"
      with:
        image: "ubuntu:20.04"
        network:
          network_mode: "host"
          ports:
            "8080": "8080"
            "9000": "9000"
```

#### Custom Environment

```yaml
jobs:
  custom-env:
    runs-on:
      type: "container"
      with:
        image: "python:3.11-slim"
        environment:
          PYTHONPATH: "/app:/workflow"
          DATABASE_URL: "postgresql://user:pass@host:5432/db"
          API_KEY: "${API_KEY}"
          DEBUG: "true"
        working_dir: "/app"
        user: "1000:1000"
```

## Usage Examples

### Data Processing Pipeline

```yaml
jobs:
  data-pipeline:
    strategy:
      matrix:
        dataset: ["sales", "inventory", "users"]
      max_parallel: 2

    runs-on:
      type: "container"
      with:
        image: "python:3.11-slim"
        volumes:
          - source: "/data/{{ matrix.dataset }}"
            target: "/container/data"
            mode: "ro"
          - source: "/output/{{ matrix.dataset }}"
            target: "/container/output"
            mode: "rw"
        environment:
          DATASET: "{{ matrix.dataset }}"

    stages:
      - name: "process"
        type: "py"
        run: |
          import pandas as pd
          import os

          dataset = os.environ['DATASET']
          data = pd.read_csv(f'/container/data/{dataset}.csv')

          # Processing logic here
          processed = data.groupby('category').agg({
              'value': ['sum', 'mean', 'count']
          })

          # Save results
          output_dir = f'/container/output/{dataset}'
          os.makedirs(output_dir, exist_ok=True)
          processed.to_csv(f'{output_dir}/processed.csv')

          result.context.update({
              "dataset": dataset,
              "rows_processed": len(data),
              "output_file": f'{output_dir}/processed.csv'
          })
```

### Machine Learning Training

```yaml
jobs:
  ml-training:
    runs-on:
      type: "container"
      with:
        image: "tensorflow/tensorflow:2.13.0-gpu"
        volumes:
          - source: "/ml/data"
            target: "/container/data"
            mode: "ro"
          - source: "/ml/models"
            target: "/container/models"
            mode: "rw"
        resources:
          memory: "8g"
          cpu: "4"
        environment:
          CUDA_VISIBLE_DEVICES: "0"

    stages:
      - name: "train"
        type: "py"
        run: |
          import tensorflow as tf
          import numpy as np

          # Load data
          data = np.load('/container/data/training.npy')
          labels = np.load('/container/data/labels.npy')

          # Create model
          model = tf.keras.Sequential([
              tf.keras.layers.Dense(128, activation='relu'),
              tf.keras.layers.Dropout(0.2),
              tf.keras.layers.Dense(64, activation='relu'),
              tf.keras.layers.Dense(10, activation='softmax')
          ])

          model.compile(
              optimizer='adam',
              loss='sparse_categorical_crossentropy',
              metrics=['accuracy']
          )

          # Train model
          history = model.fit(
              data, labels,
              epochs=10,
              validation_split=0.2,
              batch_size=32
          )

          # Save model
          model.save('/container/models/trained_model.h5')

          result.context.update({
              "final_accuracy": history.history['accuracy'][-1],
              "model_path": "/container/models/trained_model.h5"
          })
```

### Web Application Testing

```yaml
jobs:
  web-testing:
    runs-on:
      type: "container"
      with:
        image: "node:18-alpine"
        volumes:
          - source: "/app"
            target: "/container/app"
            mode: "rw"
        network:
          network_mode: "bridge"
          ports:
            "3000": "3000"
        environment:
          NODE_ENV: "test"

    stages:
      - name: "install"
        type: "bash"
        run: |
          cd /container/app
          npm install

      - name: "test"
        type: "bash"
        run: |
          cd /container/app
          npm test

      - name: "build"
        type: "bash"
        run: |
          cd /container/app
          npm run build
```

## Architecture

### Execution Flow

1. **Container Creation**: Creates a Docker container with the specified image
2. **Volume Setup**: Mounts configured volumes and creates workflow volume
3. **File Upload**: Uploads job configuration and parameters to container
4. **Environment Setup**: Configures environment variables and working directory
5. **Job Execution**: Runs the workflow job inside the container
6. **Result Collection**: Retrieves execution results and logs
7. **Cleanup**: Removes container and volumes (if configured)

### Volume Management

The provider uses Docker volumes for file management:

- **Workflow Volume**: Temporary volume for job configuration and results
- **Host Volumes**: Mounted host directories for data sharing
- **Named Volumes**: Persistent volumes for data storage

### Container Lifecycle

1. **Preparation**: Create volumes and upload files
2. **Execution**: Start container and run job
3. **Monitoring**: Wait for completion and collect results
4. **Cleanup**: Remove resources and clean up

## Best Practices

### 1. Image Selection

- Use official base images (ubuntu, python, node, etc.)
- Choose minimal images for faster startup
- Consider multi-stage builds for custom images
- Use specific version tags for reproducibility

### 2. Resource Management

- Set appropriate memory and CPU limits
- Monitor resource usage during execution
- Use resource limits to prevent system overload
- Consider using cgroups for fine-grained control

### 3. Volume Configuration

- Use read-only mounts for input data
- Use read-write mounts for output data
- Consider using named volumes for persistence
- Avoid mounting sensitive host directories

### 4. Security

- Run containers as non-root users when possible
- Use minimal base images
- Avoid mounting sensitive host directories
- Consider using Docker security options

### 5. Performance

- Use appropriate base images for your workload
- Configure resource limits based on requirements
- Use volume mounts for data sharing
- Consider using multi-stage builds

## Troubleshooting

### Common Issues

#### 1. Container Startup Failures

**Symptoms**: Container fails to start or exits immediately

**Solutions**:
- Check Docker daemon is running
- Verify image exists and is accessible
- Check resource limits are appropriate
- Review container logs for errors

```bash
# Check Docker daemon
docker info

# Check image exists
docker images

# Check container logs
docker logs <container_name>
```

#### 2. Volume Mount Issues

**Symptoms**: Files not accessible in container

**Solutions**:
- Verify host paths exist and are accessible
- Check volume mount permissions
- Ensure correct mount modes (ro/rw)

```bash
# Check volume mounts
docker inspect <container_name> | grep -A 10 "Mounts"

# Test volume access
docker run --rm -v /host/path:/container/path ubuntu ls /container/path
```

#### 3. Resource Limit Issues

**Symptoms**: Container killed or performance issues

**Solutions**:
- Increase memory limits
- Adjust CPU limits
- Monitor resource usage
- Check system resources

```bash
# Check container resource usage
docker stats <container_name>

# Check system resources
free -h
nproc
```

#### 4. Network Issues

**Symptoms**: Container cannot access network resources

**Solutions**:
- Check network mode configuration
- Verify port mappings
- Check firewall settings
- Test network connectivity

```bash
# Check container network
docker inspect <container_name> | grep -A 10 "NetworkSettings"

# Test network connectivity
docker run --rm ubuntu ping google.com
```

### Debug Information

Enable debug logging:

```python
import logging
logging.getLogger('ddeutil.workflow.plugins.providers.container').setLevel(logging.DEBUG)
```

### Error Codes

| Error Code | Description | Solution |
|------------|-------------|----------|
| 125 | Container not found | Check container exists |
| 126 | Container not running | Check container status |
| 127 | Command not found | Check command exists |
| 128 | Permission denied | Check permissions |
| 139 | Container killed | Check resource limits |

## Examples

### Multi-Platform Testing

```yaml
jobs:
  cross-platform-test:
    strategy:
      matrix:
        platform: ["ubuntu:20.04", "ubuntu:22.04", "python:3.9", "python:3.11"]
      max_parallel: 4

    runs-on:
      type: "container"
      with:
        image: "{{ matrix.platform }}"
        volumes:
          - source: "/test/code"
            target: "/container/code"
            mode: "ro"
        environment:
          PLATFORM: "{{ matrix.platform }}"

    stages:
      - name: "test"
        type: "py"
        run: |
          import sys
          import platform

          print(f"Testing on {platform.platform()}")
          print(f"Python version: {sys.version}")

          # Run tests
          import subprocess
          result = subprocess.run(['python', '-m', 'pytest', '/container/code'])

          result.context.update({
              "platform": platform.platform(),
              "python_version": sys.version,
              "test_exit_code": result.returncode
          })
```

### Database Operations

```yaml
jobs:
  database-migration:
    runs-on:
      type: "container"
      with:
        image: "postgres:15"
        volumes:
          - source: "/db/migrations"
            target: "/container/migrations"
            mode: "ro"
        network:
          network_mode: "host"
        environment:
          POSTGRES_PASSWORD: "${DB_PASSWORD}"
          POSTGRES_DB: "myapp"

    stages:
      - name: "migrate"
        type: "bash"
        run: |
          # Wait for database to be ready
          until pg_isready -h localhost -p 5432; do
            sleep 1
          done

          # Run migrations
          psql -h localhost -U postgres -d myapp -f /container/migrations/001_initial.sql
          psql -h localhost -U postgres -d myapp -f /container/migrations/002_add_users.sql
```

## API Reference

### ContainerProvider

Main provider class for container operations.

#### Methods

- `execute_job(job, params, run_id=None, event=None)`: Execute a job in container
- `cleanup(run_id=None)`: Clean up container resources
- `_create_workflow_volume(run_id)`: Create temporary volume for workflow files
- `_prepare_container_volumes(run_id)`: Prepare container volume mounts
- `_prepare_environment(run_id, job, params)`: Prepare container environment

### Configuration Classes

- `ContainerConfig`: Container execution configuration
- `VolumeConfig`: Volume mount configuration
- `NetworkConfig`: Network configuration
- `ResourceConfig`: Resource limits configuration

### Functions

- `container_execute(job, params, run_id=None, event=None)`: Main execution function

## Dependencies

- `docker>=7.1.0`: Docker Python SDK
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
