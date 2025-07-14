# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""DDE Workflow - Lightweight Workflow Orchestration Package.

This package provides a comprehensive workflow orchestration system with YAML template
support. It enables developers to create, manage, and execute complex workflows with
minimal configuration.

Key Features:
    - YAML-based workflow configuration
    - Job and stage execution management
    - Scheduling with cron-like syntax
    - Parallel and sequential execution support
    - Comprehensive error handling and logging
    - Extensible stage types (Bash, Python, Docker, etc.)
    - Matrix strategy for parameterized workflows
    - Audit and tracing capabilities

Main Classes:
    Workflow: Core workflow orchestration class
    Job: Execution unit containing stages
    Stage: Individual task execution unit
    CronJob: Scheduled workflow execution
    Audit: Execution tracking and logging
    Result: Execution status and output management

Example:
    Basic workflow usage:

    ```python
    from ddeutil.workflow import Workflow

    # Load workflow from configuration
    workflow = Workflow.from_conf('my-workflow')

    # Execute with parameters
    result = workflow.execute({'param1': 'value1'})

    if result.status == 'SUCCESS':
        print("Workflow completed successfully")
    ```

Note:
    This package requires Python 3.9+ and supports both synchronous and
    asynchronous execution patterns.
"""
from .__cron import CronRunner
from .__types import DictData, DictStr, Matrix, Re, TupleStr
from .audits import (
    Audit,
    FileAudit,
    get_audit_model,
)
from .conf import *
from .errors import (
    BaseError,
    JobCancelError,
    JobError,
    JobSkipError,
    ResultError,
    StageCancelError,
    StageError,
    StageSkipError,
    UtilError,
    WorkflowCancelError,
    WorkflowError,
    WorkflowTimeoutError,
    to_dict,
)
from .event import (
    Cron,
    CronJob,
    CronJobYear,
    Crontab,
    CrontabValue,
    CrontabYear,
    Event,
    Interval,
)
from .job import (
    Job,
    OnAzBatch,
    OnDocker,
    OnLocal,
    OnSelfHosted,
    Rule,
    RunsOnModel,
    Strategy,
    docker_execution,
    local_execute,
    local_execute_strategy,
    self_hosted_execute,
)
from .params import (
    ArrayParam,
    DateParam,
    DatetimeParam,
    DecimalParam,
    FloatParam,
    IntParam,
    MapParam,
    Param,
    StrParam,
)
from .result import (
    CANCEL,
    FAILED,
    SKIP,
    SUCCESS,
    WAIT,
    Result,
    Status,
    get_status_from_error,
)
from .reusables import *
from .stages import (
    BashStage,
    CallStage,
    CaseStage,
    DockerStage,
    EmptyStage,
    ForEachStage,
    ParallelStage,
    PyStage,
    RaiseStage,
    Stage,
    TriggerStage,
    UntilStage,
    VirtualPyStage,
)
from .traces import (
    TraceManager,
    get_trace,
)
from .utils import *
from .workflow import (
    EVENT,
    FORCE,
    NORMAL,
    RERUN,
    ReleaseType,
    Workflow,
)
