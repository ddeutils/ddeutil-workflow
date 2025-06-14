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

# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from .__cron import CronJob, CronRunner
from .__types import DictData, DictStr, Matrix, Re, TupleStr
from .audits import (
    Audit,
    AuditModel,
    FileAudit,
    get_audit,
)
from .conf import *
from .errors import *
from .event import *
from .job import *
from .params import *
from .result import (
    CANCEL,
    FAILED,
    SKIP,
    SUCCESS,
    WAIT,
    Result,
    Status,
)
from .reusables import *
from .stages import *
from .traces import (
    ConsoleTrace,
    FileTrace,
    Trace,
    TraceData,
    TraceMeta,
    TraceModel,
    get_trace,
)
from .utils import *
from .workflow import *
