"""
DDEUtil Workflow Orchestration System

A comprehensive workflow orchestration platform with advanced features including:
- Plugin/pack system for extensibility
- Event-driven triggers and sensors
- BPMN/DMN support for visual workflows
- Advanced scheduling with cron and intervals
- Data lineage and asset tracking
- Observability and UI dashboards
- Dynamic pipeline generation
- Multi-backend execution
- Security and RBAC
- Graph visualization
- Case management
- Signals and hooks

Inspired by: Apache Airflow, Prefect, Dagster, StackStorm, SpiffWorkflow, Tracecat
"""

import asyncio
import logging

logger = logging.getLogger(__name__)

# Core workflow components
# Dynamic pipeline generation - temporarily disabled due to syntax error
# from .dynamic import (
#     PipelineGenerator,
#     PipelineTemplate,
#     DynamicWorkflow,
#     PipelineValidator,
#     ConfigurationManager,
#     VisualEditor,
#     pipeline_generator,
# )
# Multi-backend execution
from .backends import (
    BackendManager,
    BatchBackend,
    CloudBackend,
    ContainerBackend,
    ExecutionBackend,
    LocalBackend,
    ServerlessBackend,
    backend_manager,
)

# BPMN/DMN support
from .bpmn import (
    BPMNExporter,
    BPMNParser,
    DMNParser,
    bpmn_to_workflow,
    workflow_to_bpmn,
)

# Case management
from .case_management import (
    SLA,
    Case,
    CaseActivity,
    CaseComment,
    CaseManager,
    CasePriority,
    CaseStatus,
    CaseType,
    EscalationLevel,
    EscalationRule,
    add_comment,
    assign_case,
    case_manager,
    close_case,
    create_case,
    escalate_case,
    get_case,
    get_sla_status,
    resolve_case,
    search_cases,
    update_case,
)

# Data lineage and asset tracking
from .lineage import (
    Asset,
    AssetDependency,
    AssetKey,
    AssetMaterialization,
    LineageTracker,
    lineage_tracker,
)

# Observability and UI
from .observability import (
    AlertManager,
    AuditLogger,
    DashboardServer,
    HealthMonitor,
    MetricsCollector,
    PerformanceAnalyzer,
    audit_logger,
    dashboard_server,
    metrics_collector,
)

# Plugin system
from .plugins import (
    PLUGIN_REGISTRY,
    load_plugins,
)

# Advanced scheduling
from .scheduler import (
    AdvancedScheduler,
    CronSchedule,
    EventSchedule,
    IntervalSchedule,
    ManualSchedule,
    ScheduleValidator,
    advanced_scheduler,
)

# Security and RBAC
from .security import (
    AuditEvent,
    AuthenticationProvider,
    LocalAuthProvider,
    Permission,
    RBACManager,
    ResourceType,
    Role,
    SecretsManager,
    SecurityManager,
    User,
    log_action,
    require_auth,
    require_permission,
    security_manager,
    setup_security,
)
from .security import (
    AuditLogger as SecurityAuditLogger,
)

# Signals and hooks
from .signals import (
    EventBus,
    Hook,
    HookDecorators,
    HookHandler,
    HookManager,
    HookType,
    Signal,
    SignalDecorators,
    SignalHandler,
    SignalManager,
    SignalType,
    WorkflowLifecycleHooks,
    add_signal_listener,
    emit_signal,
    emit_signal_async,
    event_bus,
    execute_hooks,
    execute_hooks_sync,
    hook_decorators,
    hook_manager,
    lifecycle_hooks,
    publish_event,
    register_hook,
    remove_signal_listener,
    signal_decorators,
    signal_manager,
    subscribe_to_event,
)
from .stages import (
    BaseAsyncStage,
    BaseRetryStage,
    BaseStage,
    BashStage,
    CallStage,
    CaseStage,
    DockerStage,
    EmptyStage,
    FailStage,
    ForEachStage,
    GetVariableStage,
    HttpStage,
    ParallelStage,
    PassStage,
    PyStage,
    RaiseStage,
    SetVariableStage,
    SucceedStage,
    TransformStage,
    TriggerStage,
    TryCatchFinallyStage,
    UntilStage,
    VirtualPyStage,
    WaitStage,
)

# Event-driven triggers and sensors
from .triggers import (
    BaseTrigger,
    CustomTrigger,
    FileWatcherTrigger,
    TimeTrigger,
    TriggerRegistry,
    WebhookTrigger,
    trigger_registry,
)

# Graph visualization
from .visualization import (
    DependencyVisualizer,
    GraphEdge,
    GraphExporter,
    GraphLayout,
    GraphNode,
    GraphRenderer,
    GraphType,
    MatplotlibRenderer,
    NodeType,
    PlotlyRenderer,
    TimelineVisualizer,
    WorkflowVisualizer,
    dependency_visualizer,
    export_graph,
    timeline_visualizer,
    visualize_dependencies,
    visualize_timeline,
    visualize_workflow,
    workflow_visualizer,
)

# Version information
__version__ = "2.0.0"
__author__ = "DDEUtil Team"
__description__ = (
    "Advanced workflow orchestration platform with enterprise features"
)

# Package exports
__all__ = [
    # Core components
    "BaseStage",
    "BaseAsyncStage",
    "BaseRetryStage",
    "EmptyStage",
    "BashStage",
    "PyStage",
    "CallStage",
    "TriggerStage",
    "ParallelStage",
    "ForEachStage",
    "UntilStage",
    "CaseStage",
    "RaiseStage",
    "DockerStage",
    "VirtualPyStage",
    "TryCatchFinallyStage",
    "WaitStage",
    "HttpStage",
    "SetVariableStage",
    "GetVariableStage",
    "PassStage",
    "SucceedStage",
    "FailStage",
    "TransformStage",
    # Plugin system
    "load_plugins",
    "PLUGIN_REGISTRY",
    # Triggers and sensors
    "BaseTrigger",
    "WebhookTrigger",
    "FileWatcherTrigger",
    "TimeTrigger",
    "CustomTrigger",
    "TriggerRegistry",
    "trigger_registry",
    # BPMN/DMN
    "BPMNParser",
    "BPMNExporter",
    "DMNParser",
    "workflow_to_bpmn",
    "bpmn_to_workflow",
    # Scheduling
    "AdvancedScheduler",
    "CronSchedule",
    "IntervalSchedule",
    "EventSchedule",
    "ManualSchedule",
    "ScheduleValidator",
    "advanced_scheduler",
    # Lineage
    "LineageTracker",
    "Asset",
    "AssetKey",
    "AssetMaterialization",
    "AssetDependency",
    "lineage_tracker",
    # Observability
    "MetricsCollector",
    "AuditLogger",
    "DashboardServer",
    "HealthMonitor",
    "PerformanceAnalyzer",
    "AlertManager",
    "metrics_collector",
    "audit_logger",
    "dashboard_server",
    # Backends
    "ExecutionBackend",
    "LocalBackend",
    "CloudBackend",
    "ContainerBackend",
    "ServerlessBackend",
    "BatchBackend",
    "BackendManager",
    "backend_manager",
    # Security
    "Permission",
    "ResourceType",
    "Role",
    "User",
    "AuditEvent",
    "AuthenticationProvider",
    "LocalAuthProvider",
    "SecretsManager",
    "RBACManager",
    "SecurityAuditLogger",
    "SecurityManager",
    "security_manager",
    "require_auth",
    "require_permission",
    "log_action",
    "setup_security",
    # Visualization
    "GraphType",
    "NodeType",
    "GraphNode",
    "GraphEdge",
    "GraphLayout",
    "GraphRenderer",
    "MatplotlibRenderer",
    "PlotlyRenderer",
    "WorkflowVisualizer",
    "DependencyVisualizer",
    "TimelineVisualizer",
    "GraphExporter",
    "workflow_visualizer",
    "dependency_visualizer",
    "timeline_visualizer",
    "visualize_workflow",
    "visualize_dependencies",
    "visualize_timeline",
    "export_graph",
    # Case management
    "CaseStatus",
    "CasePriority",
    "CaseType",
    "EscalationLevel",
    "SLA",
    "Case",
    "CaseComment",
    "CaseActivity",
    "EscalationRule",
    "CaseManager",
    "case_manager",
    "create_case",
    "get_case",
    "update_case",
    "assign_case",
    "add_comment",
    "search_cases",
    "escalate_case",
    "resolve_case",
    "close_case",
    "get_sla_status",
    # Signals and hooks
    "SignalType",
    "HookType",
    "Signal",
    "Hook",
    "SignalHandler",
    "HookHandler",
    "SignalManager",
    "HookManager",
    "WorkflowLifecycleHooks",
    "SignalDecorators",
    "HookDecorators",
    "EventBus",
    "signal_manager",
    "hook_manager",
    "lifecycle_hooks",
    "signal_decorators",
    "hook_decorators",
    "event_bus",
    "emit_signal",
    "emit_signal_async",
    "add_signal_listener",
    "remove_signal_listener",
    "execute_hooks",
    "execute_hooks_sync",
    "register_hook",
    "publish_event",
    "subscribe_to_event",
    # Version info
    "__version__",
    "__author__",
    "__description__",
]


# Initialize core systems
def initialize_workflow_system():
    """Initialize the workflow orchestration system"""
    # Load plugins
    load_plugins()

    # Start trigger registry
    asyncio.create_task(trigger_registry.start())

    # Start advanced scheduler
    asyncio.create_task(advanced_scheduler.start())

    # Start metrics collection
    metrics_collector.start()

    # Start dashboard server (if FastAPI available)
    try:
        if dashboard_server:
            dashboard_server.start()
    except Exception as e:
        logger.warning(f"Dashboard server not started: {e}")

    # Initialize security system
    asyncio.create_task(setup_security())

    logger.info("Workflow orchestration system initialized successfully")


# Auto-initialize on import (optional)
# initialize_workflow_system()
