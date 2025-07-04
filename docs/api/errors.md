# Exceptions

The Exceptions module provides a comprehensive error handling system for the workflow package. All exception classes inherit from `BaseError`, providing a unified error handling interface.

## Overview

The exception system provides:

- **Hierarchical error types**: Specific exceptions for different modules
- **Context preservation**: Rich error information with context
- **Unified handling**: Common base class for all workflow errors
- **Debugging support**: Detailed error messages and stack traces

## Base Exception

### BaseError

Base exception class for all workflow-related errors.

!!! example "Base Error Usage"

    ```python
    from ddeutil.workflow.errors import BaseError

    try:
        # Workflow operations
        workflow.execute(params)
    except BaseError as e:
        print(f"Workflow error: {e}")
        print(f"Error type: {type(e).__name__}")
    ```

## Module-Specific Exceptions

### UtilError

Utility exception class raised from the `utils` and `reusables` modules.

!!! example "Utility Error"

    ```python
    from ddeutil.workflow.errors import UtilError

    try:
        # Template processing
        result = str2template("${{ invalid.template }}", params)
    except UtilError as e:
        print(f"Template error: {e}")
    ```

**Common Causes:**
- Invalid template syntax
- Missing template variables
- Filter function errors
- Parameter validation failures

### ResultError

Result exception class raised from the `results` module.

!!! example "Result Error"

    ```python
    from ddeutil.workflow.errors import ResultError

    try:
        # Result operations
        result.validate()
    except ResultError as e:
        print(f"Result validation error: {e}")
    ```

**Common Causes:**
- Invalid result status
- Missing required result fields
- Result serialization errors

### StageError

Stage execution exception class raised during stage processing.

!!! example "Stage Error"

    ```python
    from ddeutil.workflow.errors import StageError

    try:
        # Stage execution
        stage.execute(params)
    except StageError as e:
        print(f"Stage execution failed: {e}")
        print(f"Stage: {e.stage_name}")
        print(f"Error details: {e.details}")
    ```

**Common Causes:**
- Stage execution failures
- Invalid stage configuration
- Stage timeout errors
- Resource allocation failures

### JobError

Job execution exception class raised during job processing.

!!! example "Job Error"

    ```python
    from ddeutil.workflow.errors import JobError

    try:
        # Job execution
        job.execute(params)
    except JobError as e:
        print(f"Job execution failed: {e}")
        print(f"Job ID: {e.job_id}")
        print(f"Failed stages: {e.failed_stages}")
    ```

**Common Causes:**
- Job dependency failures
- Matrix strategy errors
- Job timeout errors
- Stage orchestration failures

### WorkflowError

Workflow execution exception class raised during workflow processing.

!!! example "Workflow Error"

    ```python
    from ddeutil.workflow.errors import WorkflowError

    try:
        # Workflow execution
        workflow.execute(params)
    except WorkflowError as e:
        print(f"Workflow execution failed: {e}")
        print(f"Workflow: {e.workflow_name}")
        print(f"Failed jobs: {e.failed_jobs}")
    ```

**Common Causes:**
- Workflow configuration errors
- Job orchestration failures
- Parameter validation errors
- Workflow timeout errors

### ParamError

Parameter validation exception class raised during parameter processing.

!!! example "Parameter Error"

    ```python
    from ddeutil.workflow.errors import ParamError

    try:
        # Parameter validation
        params.validate()
    except ParamError as e:
        print(f"Parameter validation failed: {e}")
        print(f"Invalid parameter: {e.param_name}")
        print(f"Validation error: {e.validation_error}")
    ```

**Common Causes:**
- Missing required parameters
- Invalid parameter types
- Parameter constraint violations
- Template resolution errors

### ScheduleException

Schedule-related exception class raised during scheduling operations.

!!! example "Schedule Error"

    ```python
    from ddeutil.workflow.errors import ScheduleException

    try:
        # Schedule operations
        schedule.generate_next()
    except ScheduleException as e:
        print(f"Schedule error: {e}")
        print(f"Schedule: {e.schedule_name}")
        print(f"Error type: {e.error_type}")
    ```

**Common Causes:**
- Invalid cron expressions
- Schedule parsing errors
- Timezone conversion errors
- Schedule conflict errors

## Error Handling Patterns

### Generic Error Handling

```python
from ddeutil.workflow.errors import BaseError

def safe_workflow_execution(workflow, params):
    """Execute workflow with comprehensive error handling."""
    try:
        result = workflow.execute(params)
        return result
    except BaseError as e:
        # Log the error
        logger.error(f"Workflow execution failed: {e}")

        # Handle specific error types
        if isinstance(e, ParamError):
            logger.error(f"Parameter error: {e.param_name}")
            # Retry with default parameters
            return retry_with_defaults(workflow)
        elif isinstance(e, StageError):
            logger.error(f"Stage error: {e.stage_name}")
            # Skip failed stage
            return skip_failed_stage(workflow, e.stage_name)
        elif isinstance(e, WorkflowError):
            logger.error(f"Workflow error: {e.workflow_name}")
            # Abort workflow
            return abort_workflow(workflow)

        # Re-raise unknown errors
        raise
```

### Specific Error Handling

```python
from ddeutil.workflow.errors import (
    UtilError, ResultError, StageError, JobError,
    WorkflowError, ParamError, ScheduleException
)

def handle_workflow_errors(func):
    """Decorator for handling workflow-specific errors."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ParamError as e:
            logger.error(f"Parameter validation failed: {e}")
            # Return default result
            return create_default_result()
        except StageError as e:
            logger.error(f"Stage execution failed: {e}")
            # Mark stage as failed and continue
            return mark_stage_failed(e.stage_name)
        except JobError as e:
            logger.error(f"Job execution failed: {e}")
            # Retry job with exponential backoff
            return retry_job_with_backoff(e.job_id)
        except WorkflowError as e:
            logger.error(f"Workflow execution failed: {e}")
            # Abort entire workflow
            return abort_workflow_execution()
        except ScheduleException as e:
            logger.error(f"Schedule error: {e}")
            # Use fallback schedule
            return use_fallback_schedule()
        except (UtilError, ResultError) as e:
            logger.error(f"System error: {e}")
            # System-level error, re-raise
            raise
    return wrapper
```

### Error Recovery Strategies

```python
from ddeutil.workflow.errors import BaseError

class WorkflowErrorHandler:
    """Error handler with recovery strategies."""

    def handle_error(self, error: BaseError, context: dict):
        """Handle workflow errors with appropriate recovery strategies."""

        if isinstance(error, ParamError):
            return self.handle_param_error(error, context)
        elif isinstance(error, StageError):
            return self.handle_stage_error(error, context)
        elif isinstance(error, JobError):
            return self.handle_job_error(error, context)
        elif isinstance(error, WorkflowError):
            return self.handle_workflow_error(error, context)
        else:
            return self.handle_unknown_error(error, context)

    def handle_param_error(self, error: ParamError, context: dict):
        """Handle parameter errors with default values."""
        logger.warning(f"Using default values for parameter: {error.param_name}")
        return context.get('default_params', {})

    def handle_stage_error(self, error: StageError, context: dict):
        """Handle stage errors with retry logic."""
        retry_count = context.get('retry_count', 0)
        if retry_count < 3:
            logger.info(f"Retrying stage {error.stage_name}")
            return {'retry': True, 'stage': error.stage_name}
        else:
            logger.error(f"Stage {error.stage_name} failed after 3 retries")
            return {'skip': True, 'stage': error.stage_name}

    def handle_job_error(self, error: JobError, context: dict):
        """Handle job errors with dependency resolution."""
        logger.error(f"Job {error.job_id} failed")
        return {'abort_job': True, 'job_id': error.job_id}

    def handle_workflow_error(self, error: WorkflowError, context: dict):
        """Handle workflow errors with graceful shutdown."""
        logger.error(f"Workflow {error.workflow_name} failed")
        return {'abort_workflow': True, 'workflow': error.workflow_name}

    def handle_unknown_error(self, error: BaseError, context: dict):
        """Handle unknown errors with logging."""
        logger.error(f"Unknown error: {error}")
        return {'unknown_error': True, 'error': str(error)}
```

## Error Context and Debugging

### Error Information

All workflow exceptions provide rich context information:

```python
try:
    workflow.execute(params)
except BaseError as e:
    print(f"Error message: {e}")
    print(f"Error type: {type(e).__name__}")
    print(f"Error context: {getattr(e, 'context', {})}")
    print(f"Stack trace: {e.__traceback__}")
```

### Debugging Support

```python
import logging
from ddeutil.workflow.errors import BaseError

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

def debug_workflow_execution(workflow, params):
    """Execute workflow with debug information."""
    try:
        result = workflow.execute(params)
        return result
    except BaseError as e:
        # Log detailed error information
        logger.debug(f"Error details: {e}")
        logger.debug(f"Error context: {getattr(e, 'context', {})}")
        logger.debug(f"Error attributes: {dir(e)}")

        # Re-raise for further handling
        raise
```

## Best Practices

### 1. Error Handling Strategy

- Always catch `BaseError` for workflow operations
- Use specific exception types for targeted handling
- Implement appropriate recovery strategies
- Log errors with sufficient context

### 2. Error Recovery

- Implement retry logic for transient failures
- Use fallback values for parameter errors
- Skip failed stages when appropriate
- Gracefully handle workflow aborts

### 3. Error Logging

- Log errors with appropriate levels
- Include context information in log messages
- Use structured logging for error analysis
- Preserve stack traces for debugging

### 4. Error Propagation

- Re-raise system-level errors
- Transform errors when appropriate
- Provide meaningful error messages
- Maintain error context through layers

### 5. Testing Error Scenarios

- Test error handling paths
- Verify recovery strategies
- Validate error messages
- Test error propagation
