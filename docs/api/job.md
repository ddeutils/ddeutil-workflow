# Job API Reference

The Job module provides execution containers for stage orchestration within workflows. Jobs manage stage lifecycle, dependency resolution, matrix strategies, and multi-environment execution.

## Overview

Jobs are the primary execution units within workflows, serving as containers for multiple stages that execute sequentially. They provide comprehensive support for:

- Stage execution orchestration and lifecycle management
- Matrix strategies for parameterized parallel execution
- Multi-environment deployment (local, self-hosted, Docker, Azure Batch)
- Dependency management through job needs
- Conditional execution based on dynamic expressions
- Output coordination between stages and jobs

## Classes

### Job

Job execution container for stage orchestration.

The Job model represents a logical unit of work containing multiple stages that execute sequentially. Jobs support matrix strategies for parameterized execution, dependency management, conditional execution, and multi-environment deployment.

#### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `id` | `str \| None` | `None` | Unique job identifier within workflow |
| `desc` | `str \| None` | `None` | Job description in markdown format |
| `runs_on` | `RunsOnModel` | `OnLocal()` | Execution environment configuration |
| `condition` | `str \| None` | `None` | Conditional execution expression |
| `stages` | `list[Stage]` | `[]` | Ordered list of stages to execute |
| `trigger_rule` | `Rule` | `ALL_SUCCESS` | Rule for handling job dependencies |
| `needs` | `list[str]` | `[]` | List of prerequisite job IDs |
| `strategy` | `Strategy` | `Strategy()` | Matrix strategy for parameterized execution |
| `extras` | `dict` | `{}` | Additional configuration parameters |

#### Methods

##### `execute(params, *, run_id=None, parent_run_id=None, event=None)`

Execute the job with all its stages.

**Parameters:**
- `params` (dict): Parameter values for job execution
- `run_id` (str, optional): Unique identifier for this execution run
- `parent_run_id` (str, optional): Parent workflow run identifier
- `event` (Event, optional): Threading event for cancellation control

**Returns:**
- `Result`: Job execution result with status and output data

##### `check_needs(jobs)`

Check if job dependencies are satisfied.

**Parameters:**
- `jobs` (dict): Dictionary of job results by job ID

**Returns:**
- `Status`: Dependency check result (SUCCESS, SKIP, or WAIT)

##### `is_skipped(params)`

Check if job should be skipped based on condition.

**Parameters:**
- `params` (dict): Current parameter context

**Returns:**
- `bool`: True if job should be skipped

### Strategy

Matrix strategy model for parameterized job execution.

The Strategy model generates combinations of matrix values to enable parallel execution of jobs with different parameter sets. It supports cross-product generation, inclusion of specific combinations, and exclusion of unwanted combinations.

#### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `fail_fast` | `bool` | `False` | Cancel remaining executions on first failure |
| `max_parallel` | `int` | `1` | Maximum concurrent executions (1-9) |
| `matrix` | `dict` | `{}` | Base matrix values for cross-product generation |
| `include` | `list[dict]` | `[]` | Additional specific combinations to include |
| `exclude` | `list[dict]` | `[]` | Specific combinations to exclude from results |

#### Methods

##### `make()`

Generate list of parameter combinations from matrix.

**Returns:**
- `list[dict]`: List of parameter dictionaries for execution

##### `is_set()`

Check if strategy matrix is configured.

**Returns:**
- `bool`: True if matrix has been defined

### Rule

Trigger rules for job dependency evaluation.

#### Values

- `ALL_SUCCESS`: All prerequisite jobs must succeed
- `ALL_FAILED`: All prerequisite jobs must fail
- `ALL_DONE`: All prerequisite jobs must complete (success or failure)
- `ONE_SUCCESS`: At least one prerequisite job must succeed
- `ONE_FAILED`: At least one prerequisite job must fail
- `NONE_FAILED`: No prerequisite jobs should fail
- `NONE_SKIPPED`: No prerequisite jobs should be skipped

### RunsOn

Execution environment enumeration.

#### Values

- `LOCAL`: Execute on local machine
- `SELF_HOSTED`: Execute on remote self-hosted runner
- `DOCKER`: Execute in Docker container
- `AZ_BATCH`: Execute on Azure Batch

### Execution Environment Models

#### OnLocal

Local execution environment.

```python
runs_on = OnLocal()  # Default local execution
```

#### OnSelfHosted

Self-hosted remote execution environment.

**Configuration:**
```python
runs_on = OnSelfHosted(
    args=SelfHostedArgs(
        host="https://runner.example.com",
        token="your-api-token"
    )
)
```

#### OnDocker

Docker container execution environment.

**Configuration:**
```python
runs_on = OnDocker(
    args=DockerArgs(
        image="python:3.11-slim",
        env={"ENV": "production"},
        volume={"/local/path": "/container/path"}
    )
)
```

#### OnAzBatch

Azure Batch execution environment.

**Configuration:**
```python
runs_on = OnAzBatch(
    args=AzBatchArgs(
        batch_account_name="mybatch",
        batch_account_key="key",
        batch_account_url="https://mybatch.region.batch.azure.com",
        storage_account_name="mystorage",
        storage_account_key="storagekey"
    )
)
```

## Usage Examples

### Basic Job Configuration

```python
from ddeutil.workflow import Job, EmptyStage, PyStage

job = Job(
    id="data-processing",
    desc="Process daily data files",
    stages=[
        EmptyStage(name="Start", echo="Processing started"),
        PyStage(
            name="Process",
            run="result = process_data(input_file)",
            vars={"input_file": "/data/input.csv"}
        ),
        EmptyStage(name="Complete", echo="Processing finished")
    ]
)
```

### Job with Matrix Strategy

```python
from ddeutil.workflow import Job, Strategy, BashStage

job = Job(
    id="multi-env-deploy",
    strategy=Strategy(
        matrix={
            'environment': ['dev', 'staging', 'prod'],
            'region': ['us-east', 'eu-west']
        },
        max_parallel=3,
        fail_fast=True,
        exclude=[{'environment': 'dev', 'region': 'eu-west'}]
    ),
    stages=[
        BashStage(
            name="Deploy to ${{ matrix.environment }}-${{ matrix.region }}",
            bash="kubectl apply -f deploy.yaml",
            env={
                'ENVIRONMENT': '${{ matrix.environment }}',
                'REGION': '${{ matrix.region }}'
            }
        )
    ]
)
```

### Job with Dependencies and Conditional Execution

```python
from ddeutil.workflow import Job, Rule

# Setup job
setup_job = Job(
    id="setup",
    stages=[
        BashStage(name="Create directories", bash="mkdir -p /tmp/workspace")
    ]
)

# Processing job that depends on setup
process_job = Job(
    id="process-data",
    needs=["setup"],
    condition="${{ params.enable_processing }} == true",
    trigger_rule=Rule.ALL_SUCCESS,
    stages=[
        PyStage(
            name="Process data",
            run="process_data_files()",
            vars={"workspace": "/tmp/workspace"}
        )
    ]
)

# Cleanup job that runs regardless of processing success
cleanup_job = Job(
    id="cleanup",
    needs=["process-data"],
    trigger_rule=Rule.ALL_DONE,  # Run even if process-data fails
    stages=[
        BashStage(name="Cleanup", bash="rm -rf /tmp/workspace")
    ]
)
```

### Docker Execution Environment

```python
from ddeutil.workflow import Job, OnDocker, DockerArgs, PyStage

job = Job(
    id="containerized-job",
    runs_on=OnDocker(
        args=DockerArgs(
            image="python:3.11-slim",
            env={
                "PYTHONPATH": "/app",
                "DATA_PATH": "/data"
            },
            volume={
                "/host/data": "/data",
                "/host/app": "/app"
            }
        )
    ),
    stages=[
        PyStage(
            name="Install dependencies",
            run="subprocess.run(['pip', 'install', '-r', '/app/requirements.txt'])"
        ),
        PyStage(
            name="Run analysis",
            run="import analysis; analysis.run('/data/input.csv')"
        )
    ]
)
```

## YAML Configuration

### Basic Job Definition

```yaml
jobs:
  data-ingestion:
    desc: "Ingest data from external sources"
    runs-on:
      type: local
    stages:
      - name: "Download dataset"
        bash: |
          curl -o /tmp/data.csv "${{ params.data_url }}"

      - name: "Validate data"
        run: |
          import pandas as pd
          df = pd.read_csv('/tmp/data.csv')
          assert len(df) > 0, "Dataset is empty"
          print(f"Loaded {len(df)} records")
```

### Job with Matrix Strategy

```yaml
jobs:
  test-matrix:
    desc: "Run tests across multiple configurations"
    strategy:
      fail-fast: false
      max-parallel: 3
      matrix:
        python: ["3.9", "3.10", "3.11"]
        os: ["ubuntu-latest", "windows-latest"]
      include:
        - python: "3.12"
          os: "ubuntu-latest"
      exclude:
        - python: "3.9"
          os: "windows-latest"

    runs-on:
      type: docker
      with:
        image: "python:${{ matrix.python }}-slim"

    stages:
      - name: "Install dependencies"
        bash: pip install -r requirements.txt

      - name: "Run tests"
        bash: pytest tests/ -v
```

### Job Dependencies and Triggers

```yaml
jobs:
  build:
    stages:
      - name: "Build application"
        bash: make build

  test:
    needs: [build]
    trigger-rule: all_success
    stages:
      - name: "Run unit tests"
        bash: make test

      - name: "Run integration tests"
        bash: make integration-test

  deploy:
    needs: [test]
    condition: "${{ params.environment }} == 'production'"
    stages:
      - name: "Deploy to production"
        bash: make deploy

  cleanup:
    needs: [build, test, deploy]
    trigger-rule: all_done  # Always run cleanup
    stages:
      - name: "Clean build artifacts"
        bash: make clean
```

### Multi-Environment Execution

```yaml
jobs:
  local-job:
    runs-on:
      type: local
    stages:
      - name: "Local processing"
        run: process_locally()

  docker-job:
    runs-on:
      type: docker
      with:
        image: "python:3.11-alpine"
        env:
          ENVIRONMENT: "container"
        volume:
          "/host/data": "/app/data"
    stages:
      - name: "Container processing"
        run: process_in_container()

  remote-job:
    runs-on:
      type: self_hosted
      with:
        host: "https://runner.company.com"
        token: "${{ secrets.RUNNER_TOKEN }}"
    stages:
      - name: "Remote processing"
        bash: ./remote_script.sh
```

## Best Practices

### 1. Job Design

- Keep jobs focused on a single logical unit of work
- Use meaningful job IDs and descriptions
- Group related stages within jobs appropriately

### 2. Dependency Management

- Define clear job dependencies using the `needs` field
- Choose appropriate trigger rules for different scenarios
- Consider using `all_done` for cleanup jobs

### 3. Matrix Strategies

- Use matrix strategies for testing across multiple configurations
- Set appropriate `max_parallel` limits based on available resources
- Use `fail_fast: true` for quick feedback in development

### 4. Environment Configuration

- Choose the right execution environment for each job's requirements
- Use local execution for simple jobs
- Containerize jobs that need specific dependencies
- Use self-hosted runners for specialized hardware requirements

### 5. Error Handling

- Implement proper error handling within stages
- Use conditional execution to handle different scenarios
- Monitor job execution results and implement appropriate alerting

### 6. Resource Management

- Set reasonable timeouts for long-running jobs
- Control parallelism to avoid overwhelming systems
- Clean up resources in dedicated cleanup jobs
