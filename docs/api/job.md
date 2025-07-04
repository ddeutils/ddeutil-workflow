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

## Quick Start

```python
from ddeutil.workflow import Job, EmptyStage, PyStage, BashStage

# Create a simple job
job = Job(
    id="data-processing",
    desc="Process daily data files",
    stages=[
        EmptyStage(name="Start", echo="Processing started"),
        PyStage(
            name="Process Data",
            run="result = process_data(input_file)",
            vars={"input_file": "/data/input.csv"}
        ),
        EmptyStage(name="Complete", echo="Processing finished")
    ]
)

# Execute the job
result = job.execute({
    'input_file': '/data/input.csv',
    'output_file': '/data/output.csv'
})

print(f"Job status: {result.status}")
```

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
processing_job = Job(
    id="process",
    needs=["setup"],
    trigger_rule=Rule.ALL_SUCCESS,
    condition="${{ params.enable_processing == true }}",
    stages=[
        PyStage(
            name="Process Data",
            run="process_data()"
        )
    ]
)

# Cleanup job that runs regardless of previous job status
cleanup_job = Job(
    id="cleanup",
    needs=["setup", "process"],
    trigger_rule=Rule.ALL_DONE,
    stages=[
        BashStage(name="Cleanup", bash="rm -rf /tmp/workspace")
    ]
)
```

### Advanced Matrix Strategies

#### Complex Matrix with Exclusions

```python
from ddeutil.workflow import Job, Strategy

job = Job(
    id="comprehensive-testing",
    strategy=Strategy(
        matrix={
            'python_version': ['3.9', '3.10', '3.11'],
            'platform': ['linux', 'windows', 'macos'],
            'database': ['postgresql', 'mysql', 'sqlite']
        },
        include=[
            # Additional specific combinations
            {
                'python_version': '3.12',
                'platform': 'linux',
                'database': 'postgresql'
            }
        ],
        exclude=[
            # Exclude incompatible combinations
            {'platform': 'windows', 'database': 'sqlite'},
            {'platform': 'macos', 'python_version': '3.9'}
        ],
        max_parallel=5,
        fail_fast=False
    ),
    stages=[
        PyStage(
            name="Test ${{ matrix.python_version }} on ${{ matrix.platform }} with ${{ matrix.database }}",
            run="""
import sys
print(f"Python: {sys.version}")
print(f"Platform: {sys.platform}")
print(f"Database: {params.database}")
run_tests()
"""
        )
    ]
)
```

#### Dynamic Matrix Generation

```python
from ddeutil.workflow import Job, Strategy, PyStage

job = Job(
    id="dynamic-matrix",
    stages=[
        PyStage(
            name="Generate Matrix",
            run="""
# Generate matrix based on available resources
available_regions = get_available_regions()
available_instances = get_available_instances()

matrix_data = {
    'region': available_regions,
    'instance_type': available_instances
}

result.outputs = {"matrix": matrix_data}
"""
        )
    ],
    strategy=Strategy(
        matrix="${{ fromJson(needs.generate-matrix.outputs.matrix) }}",
        max_parallel=3
    )
)
```

### Job Orchestration Patterns

#### Fan-Out/Fan-In Pattern

```python
from ddeutil.workflow import Job, Rule

# Split job
split_job = Job(
    id="split-data",
    stages=[
        PyStage(
            name="Split Data",
            run="""
partitions = split_large_dataset()
result.outputs = {"partitions": partitions}
"""
        )
    ]
)

# Process partitions in parallel
process_job = Job(
    id="process-partitions",
    needs=["split-data"],
    strategy=Strategy(
        matrix={
            'partition': "${{ fromJson(needs.split-data.outputs.partitions) }}"
        },
        max_parallel=4
    ),
    stages=[
        PyStage(
            name="Process Partition ${{ matrix.partition }}",
            run="process_partition(${{ matrix.partition }})"
        )
    ]
)

# Merge results
merge_job = Job(
    id="merge-results",
    needs=["process-partitions"],
    trigger_rule=Rule.ALL_SUCCESS,
    stages=[
        PyStage(
            name="Merge Results",
            run="merge_all_partition_results()"
        )
    ]
)
```

#### Circuit Breaker Pattern

```python
from ddeutil.workflow import Job, Rule

# Health check job
health_job = Job(
    id="health-check",
    stages=[
        PyStage(
            name="Check System Health",
            run="""
health_status = check_system_health()
if not health_status.is_healthy:
    raise Exception("System unhealthy")
"""
        )
    ]
)

# Main processing job
main_job = Job(
    id="main-process",
    needs=["health-check"],
    trigger_rule=Rule.ALL_SUCCESS,
    stages=[
        PyStage(
            name="Main Processing",
            run="process_data()"
        )
    ]
)

# Fallback job
fallback_job = Job(
    id="fallback",
    needs=["health-check"],
    trigger_rule=Rule.ALL_FAILED,
    stages=[
        PyStage(
            name="Fallback Processing",
            run="fallback_processing()"
        )
    ]
)
```

#### Retry with Exponential Backoff

```python
from ddeutil.workflow import Job, PyStage

job = Job(
    id="retry-with-backoff",
    stages=[
        PyStage(
            name="Retry Operation",
            retry=5,
            run="""
import time

attempt = context.get('attempt', 1)
delay = 2 ** (attempt - 1)  # Exponential backoff: 1, 2, 4, 8, 16 seconds
time.sleep(delay)

# Attempt the operation
result = risky_operation()
if not result.success:
    raise Exception(f"Operation failed on attempt {attempt}")
"""
        )
    ]
)
```

### Multi-Environment Deployment

#### Environment-Specific Jobs

```python
from ddeutil.workflow import Job, Strategy

deploy_job = Job(
    id="deploy",
    strategy=Strategy(
        matrix={
            'environment': ['dev', 'staging', 'prod']
        }
    ),
    stages=[
        PyStage(
            name="Deploy to ${{ matrix.environment }}",
            run="""
env = matrix['environment']
config = get_environment_config(env)

if env == 'prod':
    # Additional safety checks for production
    validate_production_deployment()
    notify_team("Production deployment starting")

deploy_application(config)
"""
        )
    ]
)
```

#### Docker-Based Execution

```python
from ddeutil.workflow import Job, OnDocker, DockerArgs

docker_job = Job(
    id="docker-process",
    runs_on=OnDocker(
        args=DockerArgs(
            image="python:3.11-slim",
            env={
                "PYTHONPATH": "/app",
                "DATABASE_URL": "${{ params.database_url }}"
            },
            volume={
                "/local/data": "/app/data",
                "/local/output": "/app/output"
            }
        )
    ),
    stages=[
        PyStage(
            name="Docker Processing",
            run="""
import os
print(f"Running in container: {os.uname()}")
print(f"Data directory: {os.listdir('/app/data')}")

# Process data
process_data('/app/data', '/app/output')
"""
        )
    ]
)
```

### Conditional Job Execution

#### Parameter-Based Conditions

```python
from ddeutil.workflow import Job

job = Job(
    id="conditional-job",
    condition="${{ params.environment == 'production' && params.enable_feature == true }}",
    stages=[
        PyStage(
            name="Production Feature",
            run="enable_production_feature()"
        )
    ]
)
```

#### Time-Based Conditions

```python
from ddeutil.workflow import Job

job = Job(
    id="time-based-job",
    condition="${{ datetime.now().hour >= 9 && datetime.now().hour <= 17 }}",
    stages=[
        PyStage(
            name="Business Hours Task",
            run="business_hours_task()"
        )
    ]
)
```

#### Dependency-Based Conditions

```python
from ddeutil.workflow import Job

job = Job(
    id="dependent-job",
    needs=["predecessor-job"],
    condition="${{ needs.predecessor-job.result == 'success' }}",
    stages=[
        PyStage(
            name="Dependent Task",
            run="dependent_task()"
        )
    ]
)
```

## Job Lifecycle Management

### Job State Transitions

```python
from ddeutil.workflow import Job, SUCCESS, FAILED, SKIP, WAIT

def monitor_job_lifecycle(job: Job, params: dict):
    """Monitor job execution lifecycle."""

    # Check if job should be skipped
    if job.is_skipped(params):
        print(f"Job {job.id} will be skipped")
        return SKIP

    # Check dependencies
    dependency_status = job.check_needs(previous_job_results)
    if dependency_status == WAIT:
        print(f"Job {job.id} waiting for dependencies")
        return WAIT

    # Execute job
    try:
        result = job.execute(params)
        print(f"Job {job.id} completed with status: {result.status}")
        return result.status
    except Exception as e:
        print(f"Job {job.id} failed: {e}")
        return FAILED
```

### Job Result Aggregation

```python
from ddeutil.workflow import Job, Result

def aggregate_job_results(jobs: dict[str, Job], results: dict[str, Result]) -> dict:
    """Aggregate results from multiple jobs."""

    aggregated = {
        'total_jobs': len(jobs),
        'successful_jobs': 0,
        'failed_jobs': 0,
        'skipped_jobs': 0,
        'job_details': {}
    }

    for job_id, result in results.items():
        aggregated['job_details'][job_id] = {
            'status': result.status,
            'execution_time': result.context.get('execution_time'),
            'outputs': result.context.get('outputs', {})
        }

        if result.status == SUCCESS:
            aggregated['successful_jobs'] += 1
        elif result.status == FAILED:
            aggregated['failed_jobs'] += 1
        elif result.status == SKIP:
            aggregated['skipped_jobs'] += 1

    return aggregated
```

## Performance Optimization

### Parallel Execution Strategies

```python
from ddeutil.workflow import Job, Strategy

# Optimize for CPU-bound tasks
cpu_intensive_job = Job(
    id="cpu-intensive",
    strategy=Strategy(
        matrix={'task_id': range(100)},
        max_parallel=os.cpu_count()  # Use all CPU cores
    )
)

# Optimize for I/O-bound tasks
io_intensive_job = Job(
    id="io-intensive",
    strategy=Strategy(
        matrix={'file_id': range(50)},
        max_parallel=20  # Higher parallelism for I/O
    )
)

# Resource-aware execution
resource_aware_job = Job(
    id="resource-aware",
    strategy=Strategy(
        matrix={'region': ['us-east', 'us-west', 'eu-west']},
        max_parallel=min(3, available_resources)  # Limit based on resources
    )
)
```

### Caching and Optimization

```python
from ddeutil.workflow import Job, PyStage

cached_job = Job(
    id="cached-computation",
    stages=[
        PyStage(
            name="Check Cache",
            run="""
cache_key = generate_cache_key(params)
if cache_exists(cache_key):
    result = load_from_cache(cache_key)
    print("Using cached result")
else:
    result = expensive_computation()
    save_to_cache(cache_key, result)
    print("Computed and cached result")
"""
        )
    ]
)
```

## Error Handling and Recovery

### Comprehensive Error Handling

```python
from ddeutil.workflow import Job, PyStage, Rule

robust_job = Job(
    id="robust-processing",
    stages=[
        PyStage(
            name="Primary Processing",
            retry=3,
            run="""
try:
    result = primary_processing()
except Exception as e:
    logger.error(f"Primary processing failed: {e}")
    raise
"""
        )
    ]
)

# Fallback job
fallback_job = Job(
    id="fallback-processing",
    needs=["robust-processing"],
    trigger_rule=Rule.ALL_FAILED,
    stages=[
        PyStage(
            name="Fallback Processing",
            run="fallback_processing()"
        )
    ]
)

# Cleanup job
cleanup_job = Job(
    id="cleanup",
    needs=["robust-processing", "fallback-processing"],
    trigger_rule=Rule.ALL_DONE,
    stages=[
        PyStage(
            name="Cleanup",
            run="cleanup_resources()"
        )
    ]
)
```

### Graceful Degradation

```python
from ddeutil.workflow import Job, PyStage

degraded_job = Job(
    id="graceful-degradation",
    stages=[
        PyStage(
            name="Check System Resources",
            run="""
resources = check_system_resources()
if resources.memory < 1024:  # Less than 1GB
    print("Low memory detected, using degraded mode")
    params['degraded_mode'] = True
"""
        ),
        PyStage(
            name="Adaptive Processing",
            run="""
if params.get('degraded_mode'):
    process_with_limited_resources()
else:
    process_with_full_resources()
"""
        )
    ]
)
```

## Monitoring and Observability

### Job Metrics Collection

```python
from ddeutil.workflow import Job, PyStage
import time

monitored_job = Job(
    id="monitored-job",
    stages=[
        PyStage(
            name="Collect Metrics",
            run="""
import time
import psutil

start_time = time.time()
start_memory = psutil.virtual_memory().used

# Your processing logic here
process_data()

end_time = time.time()
end_memory = psutil.virtual_memory().used

metrics = {
    'execution_time': end_time - start_time,
    'memory_usage': end_memory - start_memory,
    'cpu_usage': psutil.cpu_percent()
}

result.outputs = {"metrics": metrics}
"""
        )
    ]
)
```

### Job Health Checks

```python
from ddeutil.workflow import Job, PyStage

health_check_job = Job(
    id="health-check",
    stages=[
        PyStage(
            name="System Health Check",
            run="""
health_status = {
    'database': check_database_health(),
    'api': check_api_health(),
    'storage': check_storage_health(),
    'network': check_network_health()
}

all_healthy = all(health_status.values())
if not all_healthy:
    unhealthy_services = [k for k, v in health_status.items() if not v]
    raise Exception(f"Unhealthy services: {unhealthy_services}")

result.outputs = {"health_status": health_status}
"""
        )
    ]
)
```

## Best Practices

### 1. Job Design

- **Single responsibility**: Each job should have a clear, focused purpose
- **Idempotency**: Jobs should be safe to retry without side effects
- **Modularity**: Break complex jobs into smaller, manageable stages
- **Reusability**: Design jobs to be reusable across different workflows

### 2. Matrix Strategies

- **Resource awareness**: Set `max_parallel` based on available resources
- **Failure handling**: Use `fail_fast` appropriately for your use case
- **Exclusion logic**: Carefully design exclusion rules to avoid conflicts
- **Performance**: Balance parallelism with resource constraints

### 3. Dependencies

- **Clear dependencies**: Explicitly define job dependencies
- **Trigger rules**: Choose appropriate trigger rules for your use case
- **Circular dependencies**: Avoid circular dependency patterns
- **Failure propagation**: Understand how failures propagate through dependencies

### 4. Error Handling

- **Retry logic**: Implement appropriate retry strategies
- **Fallback mechanisms**: Provide fallback options for critical jobs
- **Graceful degradation**: Handle resource constraints gracefully
- **Monitoring**: Monitor job execution and failure patterns

### 5. Performance

- **Parallelization**: Use matrix strategies for parallel execution
- **Resource optimization**: Optimize resource usage based on job type
- **Caching**: Implement caching for expensive operations
- **Monitoring**: Track performance metrics and optimize accordingly

### 6. Security

- **Input validation**: Validate all inputs to jobs
- **Access control**: Implement proper access controls
- **Secret management**: Handle secrets securely
- **Audit logging**: Enable audit logging for compliance

## Troubleshooting

### Common Issues

#### Job Dependencies Not Met

```python
# Problem: Job waiting indefinitely for dependencies
job_results = {
    'job-a': Result(status=SUCCESS),
    'job-b': Result(status=FAILED)
}

# Check dependency status
for job_id, job in workflow.jobs.items():
    if job.needs:
        status = job.check_needs(job_results)
        print(f"Job {job_id} dependency status: {status}")
```

#### Matrix Strategy Issues

```python
# Problem: Matrix combinations not generating as expected
strategy = Strategy(
    matrix={
        'env': ['dev', 'prod'],
        'region': ['us-east', 'eu-west']
    },
    exclude=[{'env': 'dev', 'region': 'eu-west'}]
)

# Generate and inspect combinations
combinations = strategy.make()
print(f"Generated {len(combinations)} combinations:")
for combo in combinations:
    print(f"  {combo}")
```

#### Resource Exhaustion

```python
# Problem: Too many parallel executions causing resource issues
# Solution: Monitor and adjust max_parallel
import psutil

available_memory = psutil.virtual_memory().available
available_cpu = psutil.cpu_count()

# Adjust max_parallel based on available resources
max_parallel = min(
    available_cpu,
    available_memory // (1024 * 1024 * 512),  # 512MB per job
    10  # Maximum limit
)

job = Job(
    id="resource-aware",
    strategy=Strategy(
        matrix={'task_id': range(100)},
        max_parallel=max_parallel
    )
)
```

#### Conditional Execution Issues

```python
# Problem: Job not executing when expected
# Solution: Debug condition evaluation
job = Job(
    id="conditional-job",
    condition="${{ params.environment == 'production' }}"
)

# Test condition evaluation
test_params = {'environment': 'production'}
is_skipped = job.is_skipped(test_params)
print(f"Job would be skipped: {is_skipped}")

# Check parameter values
print(f"Environment parameter: {test_params.get('environment')}")
```

### Debugging Tips

1. **Enable verbose logging**: Set log level to DEBUG for detailed execution information
2. **Check job dependencies**: Verify that all required jobs have completed successfully
3. **Validate matrix combinations**: Inspect generated matrix combinations for correctness
4. **Monitor resource usage**: Track CPU, memory, and I/O usage during execution
5. **Test incrementally**: Test individual stages before running full jobs
6. **Use conditional execution**: Add debug stages that only run in development

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKFLOW_CORE_JOB_TIMEOUT` | `3600` | Default job timeout in seconds |
| `WORKFLOW_CORE_MAX_PARALLEL` | `2` | Default max parallel executions |
| `WORKFLOW_CORE_RETRY_DELAY` | `5` | Default retry delay in seconds |
| `WORKFLOW_CORE_RETRY_ATTEMPTS` | `3` | Default retry attempts |

### Job Configuration Schema

```yaml
job-name:
  id: "unique-job-id"
  desc: "Job description"
  runs-on:
    type: "local" | "self-hosted" | "docker" | "az-batch"
    # Additional environment-specific configuration
  condition: "${{ expression }}"
  needs: ["job1", "job2"]
  trigger-rule: "all_success" | "all_failed" | "all_done" | "one_success" | "one_failed" | "none_failed" | "none_skipped"
  strategy:
    matrix:
      key1: [value1, value2]
      key2: [value3, value4]
    include:
      - key1: value5
        key2: value6
    exclude:
      - key1: value1
        key2: value3
    max-parallel: 3
    fail-fast: false
  stages:
    - name: "Stage Name"
      # Stage-specific configuration
```
