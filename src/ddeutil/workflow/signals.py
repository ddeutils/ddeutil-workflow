"""
Signals and Hooks System for Workflow Orchestration

This module provides comprehensive signals and hooks features including:
- Custom event handling
- Workflow lifecycle hooks
- Signal processing
- Extensibility points
- Plugin integration hooks
- Event-driven architecture

Inspired by: Various workflow tools, Django signals, FastAPI events
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Signal types for workflow events"""

    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_CANCELLED = "workflow_cancelled"
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    STAGE_FAILED = "stage_failed"
    TRIGGER_ACTIVATED = "trigger_activated"
    SCHEDULE_TRIGGERED = "schedule_triggered"
    CASE_CREATED = "case_created"
    CASE_UPDATED = "case_updated"
    CASE_RESOLVED = "case_resolved"
    SECRET_ACCESSED = "secret_accessed"
    USER_AUTHENTICATED = "user_authenticated"
    PLUGIN_LOADED = "plugin_loaded"
    CUSTOM = "custom"


class HookType(Enum):
    """Hook types for extensibility"""

    PRE_WORKFLOW = "pre_workflow"
    POST_WORKFLOW = "post_workflow"
    PRE_JOB = "pre_job"
    POST_JOB = "post_job"
    PRE_STAGE = "pre_stage"
    POST_STAGE = "post_stage"
    PRE_TRIGGER = "pre_trigger"
    POST_TRIGGER = "post_trigger"
    PRE_SCHEDULE = "pre_schedule"
    POST_SCHEDULE = "post_schedule"
    PRE_CASE = "pre_case"
    POST_CASE = "post_case"
    PRE_SECRET = "pre_secret"
    POST_SECRET = "post_secret"
    PRE_AUTH = "pre_auth"
    POST_AUTH = "post_auth"
    ERROR_HANDLER = "error_handler"
    CUSTOM = "custom"


@dataclass
class Signal:
    """Signal definition"""

    signal_type: SignalType
    source: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Hook:
    """Hook definition"""

    hook_type: HookType
    name: str
    handler: Callable
    priority: int = 0
    is_async: bool = False
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class SignalHandler(ABC):
    """Abstract signal handler"""

    @abstractmethod
    async def handle_signal(self, signal: Signal) -> bool:
        """Handle a signal"""
        pass

    @abstractmethod
    def can_handle(self, signal_type: SignalType) -> bool:
        """Check if handler can handle signal type"""
        pass


class HookHandler(ABC):
    """Abstract hook handler"""

    @abstractmethod
    async def execute_hook(
        self, hook_type: HookType, context: dict[str, Any]
    ) -> Any:
        """Execute hook"""
        pass

    @abstractmethod
    def can_handle(self, hook_type: HookType) -> bool:
        """Check if handler can handle hook type"""
        pass


class SignalManager:
    """Signal management system"""

    def __init__(self):
        self.handlers: dict[SignalType, list[SignalHandler]] = {}
        self.listeners: dict[SignalType, list[Callable]] = {}
        self.signal_history: list[Signal] = []
        self.max_history = 1000
        self.is_enabled = True

    def register_handler(self, signal_type: SignalType, handler: SignalHandler):
        """Register signal handler"""
        if signal_type not in self.handlers:
            self.handlers[signal_type] = []
        self.handlers[signal_type].append(handler)
        logger.info(f"Registered signal handler for {signal_type.value}")

    def unregister_handler(
        self, signal_type: SignalType, handler: SignalHandler
    ):
        """Unregister signal handler"""
        if signal_type in self.handlers:
            if handler in self.handlers[signal_type]:
                self.handlers[signal_type].remove(handler)
                logger.info(
                    f"Unregistered signal handler for {signal_type.value}"
                )

    def add_listener(self, signal_type: SignalType, listener: Callable):
        """Add signal listener"""
        if signal_type not in self.listeners:
            self.listeners[signal_type] = []
        self.listeners[signal_type].append(listener)
        logger.info(f"Added signal listener for {signal_type.value}")

    def remove_listener(self, signal_type: SignalType, listener: Callable):
        """Remove signal listener"""
        if signal_type in self.listeners:
            if listener in self.listeners[signal_type]:
                self.listeners[signal_type].remove(listener)
                logger.info(f"Removed signal listener for {signal_type.value}")

    async def emit_signal(self, signal: Signal) -> bool:
        """Emit a signal"""
        if not self.is_enabled:
            return False

        # Add to history
        self.signal_history.append(signal)
        if len(self.signal_history) > self.max_history:
            self.signal_history.pop(0)

        logger.debug(
            f"Emitting signal: {signal.signal_type.value} from {signal.source}"
        )

        # Notify handlers
        handlers = self.handlers.get(signal.signal_type, [])
        for handler in handlers:
            if handler.can_handle(signal.signal_type):
                try:
                    await handler.handle_signal(signal)
                except Exception as e:
                    logger.error(f"Error in signal handler: {e}")

        # Notify listeners
        listeners = self.listeners.get(signal.signal_type, [])
        for listener in listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(signal)
                else:
                    listener(signal)
            except Exception as e:
                logger.error(f"Error in signal listener: {e}")

        return True

    def emit_signal_sync(self, signal: Signal) -> bool:
        """Emit a signal synchronously"""
        if not self.is_enabled:
            return False

        # Add to history
        self.signal_history.append(signal)
        if len(self.signal_history) > self.max_history:
            self.signal_history.pop(0)

        logger.debug(
            f"Emitting signal: {signal.signal_type.value} from {signal.source}"
        )

        # Notify handlers (sync)
        handlers = self.handlers.get(signal.signal_type, [])
        for handler in handlers:
            if handler.can_handle(signal.signal_type):
                try:
                    # Run async handlers in event loop
                    if asyncio.iscoroutinefunction(handler.handle_signal):
                        asyncio.create_task(handler.handle_signal(signal))
                    else:
                        handler.handle_signal(signal)
                except Exception as e:
                    logger.error(f"Error in signal handler: {e}")

        # Notify listeners (sync)
        listeners = self.listeners.get(signal.signal_type, [])
        for listener in listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    asyncio.create_task(listener(signal))
                else:
                    listener(signal)
            except Exception as e:
                logger.error(f"Error in signal listener: {e}")

        return True

    def get_signal_history(
        self, signal_type: Optional[SignalType] = None, limit: int = 100
    ) -> list[Signal]:
        """Get signal history"""
        history = self.signal_history
        if signal_type:
            history = [s for s in history if s.signal_type == signal_type]
        return history[-limit:]

    def clear_history(self):
        """Clear signal history"""
        self.signal_history.clear()


class HookManager:
    """Hook management system"""

    def __init__(self):
        self.hooks: dict[HookType, list[Hook]] = {}
        self.handlers: dict[HookType, list[HookHandler]] = {}
        self.hook_history: list[dict[str, Any]] = []
        self.max_history = 1000
        self.is_enabled = True

    def register_hook(self, hook: Hook):
        """Register a hook"""
        if hook.hook_type not in self.hooks:
            self.hooks[hook.hook_type] = []

        # Insert hook in priority order
        hooks = self.hooks[hook.hook_type]
        for i, existing_hook in enumerate(hooks):
            if hook.priority > existing_hook.priority:
                hooks.insert(i, hook)
                break
        else:
            hooks.append(hook)

        logger.info(f"Registered hook: {hook.name} for {hook.hook_type.value}")

    def unregister_hook(self, hook_type: HookType, hook_name: str):
        """Unregister a hook"""
        if hook_type in self.hooks:
            hooks = self.hooks[hook_type]
            for i, hook in enumerate(hooks):
                if hook.name == hook_name:
                    hooks.pop(i)
                    logger.info(f"Unregistered hook: {hook_name}")
                    break

    def register_handler(self, hook_type: HookType, handler: HookHandler):
        """Register hook handler"""
        if hook_type not in self.handlers:
            self.handlers[hook_type] = []
        self.handlers[hook_type].append(handler)
        logger.info(f"Registered hook handler for {hook_type.value}")

    async def execute_hooks(
        self, hook_type: HookType, context: dict[str, Any]
    ) -> list[Any]:
        """Execute hooks for a specific type"""
        if not self.is_enabled:
            return []

        results = []
        hooks = self.hooks.get(hook_type, [])

        # Log hook execution
        execution_id = f"hook_{datetime.utcnow().timestamp()}"
        self.hook_history.append(
            {
                "id": execution_id,
                "hook_type": hook_type.value,
                "timestamp": datetime.utcnow().isoformat(),
                "context": context,
                "results": [],
            }
        )

        if len(self.hook_history) > self.max_history:
            self.hook_history.pop(0)

        logger.debug(f"Executing {len(hooks)} hooks for {hook_type.value}")

        for hook in hooks:
            if not hook.is_active:
                continue

            try:
                if hook.is_async:
                    result = await hook.handler(context)
                else:
                    result = hook.handler(context)

                results.append(
                    {"hook_name": hook.name, "result": result, "success": True}
                )

                logger.debug(f"Hook {hook.name} executed successfully")

            except Exception as e:
                error_result = {
                    "hook_name": hook.name,
                    "result": None,
                    "success": False,
                    "error": str(e),
                }
                results.append(error_result)
                logger.error(f"Error executing hook {hook.name}: {e}")

        # Update history with results
        if self.hook_history:
            self.hook_history[-1]["results"] = results

        return results

    def execute_hooks_sync(
        self, hook_type: HookType, context: dict[str, Any]
    ) -> list[Any]:
        """Execute hooks synchronously"""
        if not self.is_enabled:
            return []

        results = []
        hooks = self.hooks.get(hook_type, [])

        # Log hook execution
        execution_id = f"hook_{datetime.utcnow().timestamp()}"
        self.hook_history.append(
            {
                "id": execution_id,
                "hook_type": hook_type.value,
                "timestamp": datetime.utcnow().isoformat(),
                "context": context,
                "results": [],
            }
        )

        if len(self.hook_history) > self.max_history:
            self.hook_history.pop(0)

        logger.debug(f"Executing {len(hooks)} hooks for {hook_type.value}")

        for hook in hooks:
            if not hook.is_active:
                continue

            try:
                if hook.is_async:
                    # Run async hooks in event loop
                    asyncio.create_task(hook.handler(context))
                    result = None
                else:
                    result = hook.handler(context)

                results.append(
                    {"hook_name": hook.name, "result": result, "success": True}
                )

                logger.debug(f"Hook {hook.name} executed successfully")

            except Exception as e:
                error_result = {
                    "hook_name": hook.name,
                    "result": None,
                    "success": False,
                    "error": str(e),
                }
                results.append(error_result)
                logger.error(f"Error executing hook {hook.name}: {e}")

        # Update history with results
        if self.hook_history:
            self.hook_history[-1]["results"] = results

        return results

    def get_hook_history(
        self, hook_type: Optional[HookType] = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get hook execution history"""
        history = self.hook_history
        if hook_type:
            history = [h for h in history if h["hook_type"] == hook_type.value]
        return history[-limit:]

    def clear_history(self):
        """Clear hook history"""
        self.hook_history.clear()


class WorkflowLifecycleHooks:
    """Workflow lifecycle hook implementations"""

    def __init__(self, hook_manager: HookManager):
        self.hook_manager = hook_manager

    async def pre_workflow(
        self, workflow_id: str, workflow_data: dict[str, Any]
    ):
        """Pre-workflow hook"""
        context = {
            "workflow_id": workflow_id,
            "workflow_data": workflow_data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return await self.hook_manager.execute_hooks(
            HookType.PRE_WORKFLOW, context
        )

    async def post_workflow(self, workflow_id: str, result: Any, success: bool):
        """Post-workflow hook"""
        context = {
            "workflow_id": workflow_id,
            "result": result,
            "success": success,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return await self.hook_manager.execute_hooks(
            HookType.POST_WORKFLOW, context
        )

    async def pre_job(self, job_id: str, job_data: dict[str, Any]):
        """Pre-job hook"""
        context = {
            "job_id": job_id,
            "job_data": job_data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return await self.hook_manager.execute_hooks(HookType.PRE_JOB, context)

    async def post_job(self, job_id: str, result: Any, success: bool):
        """Post-job hook"""
        context = {
            "job_id": job_id,
            "result": result,
            "success": success,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return await self.hook_manager.execute_hooks(HookType.POST_JOB, context)

    async def pre_stage(self, stage_id: str, stage_data: dict[str, Any]):
        """Pre-stage hook"""
        context = {
            "stage_id": stage_id,
            "stage_data": stage_data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return await self.hook_manager.execute_hooks(
            HookType.PRE_STAGE, context
        )

    async def post_stage(self, stage_id: str, result: Any, success: bool):
        """Post-stage hook"""
        context = {
            "stage_id": stage_id,
            "result": result,
            "success": success,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return await self.hook_manager.execute_hooks(
            HookType.POST_STAGE, context
        )

    async def error_handler(self, error: Exception, context: dict[str, Any]):
        """Error handler hook"""
        error_context = {
            "error": str(error),
            "error_type": type(error).__name__,
            "context": context,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return await self.hook_manager.execute_hooks(
            HookType.ERROR_HANDLER, error_context
        )


class SignalDecorators:
    """Signal decorators for easy integration"""

    def __init__(self, signal_manager: SignalManager):
        self.signal_manager = signal_manager

    def on_signal(self, signal_type: SignalType):
        """Decorator to register signal listener"""

        def decorator(func):
            self.signal_manager.add_listener(signal_type, func)
            return func

        return decorator

    def on_workflow_started(self):
        """Decorator for workflow started events"""
        return self.on_signal(SignalType.WORKFLOW_STARTED)

    def on_workflow_completed(self):
        """Decorator for workflow completed events"""
        return self.on_signal(SignalType.WORKFLOW_COMPLETED)

    def on_workflow_failed(self):
        """Decorator for workflow failed events"""
        return self.on_signal(SignalType.WORKFLOW_FAILED)

    def on_job_started(self):
        """Decorator for job started events"""
        return self.on_signal(SignalType.JOB_STARTED)

    def on_job_completed(self):
        """Decorator for job completed events"""
        return self.on_signal(SignalType.JOB_COMPLETED)

    def on_stage_started(self):
        """Decorator for stage started events"""
        return self.on_signal(SignalType.STAGE_STARTED)

    def on_stage_completed(self):
        """Decorator for stage completed events"""
        return self.on_signal(SignalType.STAGE_COMPLETED)


class HookDecorators:
    """Hook decorators for easy integration"""

    def __init__(self, hook_manager: HookManager):
        self.hook_manager = hook_manager

    def hook(self, hook_type: HookType, priority: int = 0):
        """Decorator to register hook"""

        def decorator(func):
            is_async = asyncio.iscoroutinefunction(func)
            hook = Hook(
                hook_type=hook_type,
                name=func.__name__,
                handler=func,
                priority=priority,
                is_async=is_async,
            )
            self.hook_manager.register_hook(hook)
            return func

        return decorator

    def pre_workflow(self, priority: int = 0):
        """Decorator for pre-workflow hooks"""
        return self.hook(HookType.PRE_WORKFLOW, priority)

    def post_workflow(self, priority: int = 0):
        """Decorator for post-workflow hooks"""
        return self.hook(HookType.POST_WORKFLOW, priority)

    def pre_job(self, priority: int = 0):
        """Decorator for pre-job hooks"""
        return self.hook(HookType.PRE_JOB, priority)

    def post_job(self, priority: int = 0):
        """Decorator for post-job hooks"""
        return self.hook(HookType.POST_JOB, priority)

    def pre_stage(self, priority: int = 0):
        """Decorator for pre-stage hooks"""
        return self.hook(HookType.PRE_STAGE, priority)

    def post_stage(self, priority: int = 0):
        """Decorator for post-stage hooks"""
        return self.hook(HookType.POST_STAGE, priority)

    def error_handler(self, priority: int = 0):
        """Decorator for error handler hooks"""
        return self.hook(HookType.ERROR_HANDLER, priority)


class EventBus:
    """Event bus for custom events"""

    def __init__(self):
        self.subscribers: dict[str, list[Callable]] = {}
        self.event_history: list[dict[str, Any]] = []
        self.max_history = 1000

    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to event type"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
        logger.info(f"Subscribed to event: {event_type}")

    def unsubscribe(self, event_type: str, handler: Callable):
        """Unsubscribe from event type"""
        if event_type in self.subscribers:
            if handler in self.subscribers[event_type]:
                self.subscribers[event_type].remove(handler)
                logger.info(f"Unsubscribed from event: {event_type}")

    async def publish(self, event_type: str, data: dict[str, Any]):
        """Publish event"""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Add to history
        self.event_history.append(event)
        if len(self.event_history) > self.max_history:
            self.event_history.pop(0)

        # Notify subscribers
        subscribers = self.subscribers.get(event_type, [])
        for subscriber in subscribers:
            try:
                if asyncio.iscoroutinefunction(subscriber):
                    await subscriber(event)
                else:
                    subscriber(event)
            except Exception as e:
                logger.error(f"Error in event subscriber: {e}")

        logger.debug(f"Published event: {event_type}")


# Global instances
signal_manager = SignalManager()
hook_manager = HookManager()
lifecycle_hooks = WorkflowLifecycleHooks(hook_manager)
signal_decorators = SignalDecorators(signal_manager)
hook_decorators = HookDecorators(hook_manager)
event_bus = EventBus()


# Convenience functions
def emit_signal(
    signal_type: SignalType,
    source: str,
    data: dict[str, Any] = None,
    metadata: dict[str, Any] = None,
):
    """Emit a signal"""
    signal = Signal(
        signal_type=signal_type,
        source=source,
        data=data or {},
        metadata=metadata or {},
    )
    return signal_manager.emit_signal_sync(signal)


async def emit_signal_async(
    signal_type: SignalType,
    source: str,
    data: dict[str, Any] = None,
    metadata: dict[str, Any] = None,
):
    """Emit a signal asynchronously"""
    signal = Signal(
        signal_type=signal_type,
        source=source,
        data=data or {},
        metadata=metadata or {},
    )
    return await signal_manager.emit_signal(signal)


def add_signal_listener(signal_type: SignalType, listener: Callable):
    """Add signal listener"""
    signal_manager.add_listener(signal_type, listener)


def remove_signal_listener(signal_type: SignalType, listener: Callable):
    """Remove signal listener"""
    signal_manager.remove_listener(signal_type, listener)


async def execute_hooks(hook_type: HookType, context: dict[str, Any]):
    """Execute hooks"""
    return await hook_manager.execute_hooks(hook_type, context)


def execute_hooks_sync(hook_type: HookType, context: dict[str, Any]):
    """Execute hooks synchronously"""
    return hook_manager.execute_hooks_sync(hook_type, context)


def register_hook(
    hook_type: HookType, name: str, handler: Callable, priority: int = 0
):
    """Register a hook"""
    is_async = asyncio.iscoroutinefunction(handler)
    hook = Hook(
        hook_type=hook_type,
        name=name,
        handler=handler,
        priority=priority,
        is_async=is_async,
    )
    hook_manager.register_hook(hook)


async def publish_event(event_type: str, data: dict[str, Any]):
    """Publish custom event"""
    await event_bus.publish(event_type, data)


def subscribe_to_event(event_type: str, handler: Callable):
    """Subscribe to custom event"""
    event_bus.subscribe(event_type, handler)


# Example usage and built-in hooks
@signal_decorators.on_workflow_started()
def log_workflow_started(signal: Signal):
    """Log workflow started events"""
    logger.info(
        f"Workflow started: {signal.data.get('workflow_id')} from {signal.source}"
    )


@signal_decorators.on_workflow_completed()
def log_workflow_completed(signal: Signal):
    """Log workflow completed events"""
    logger.info(
        f"Workflow completed: {signal.data.get('workflow_id')} from {signal.source}"
    )


@hook_decorators.pre_workflow(priority=10)
def validate_workflow(context: dict[str, Any]):
    """Validate workflow before execution"""
    workflow_data = context.get("workflow_data", {})
    if not workflow_data.get("name"):
        raise ValueError("Workflow must have a name")
    logger.info(f"Workflow validation passed: {context.get('workflow_id')}")


@hook_decorators.post_workflow(priority=10)
def cleanup_workflow(context: dict[str, Any]):
    """Cleanup after workflow execution"""
    workflow_id = context.get("workflow_id")
    logger.info(f"Cleaning up workflow: {workflow_id}")


@hook_decorators.error_handler(priority=10)
def log_errors(context: dict[str, Any]):
    """Log errors from hooks"""
    error = context.get("error")
    error_type = context.get("error_type")
    logger.error(f"Hook error ({error_type}): {error}")


# Example custom event handlers
@subscribe_to_event("data_processed")
def handle_data_processed(event: dict[str, Any]):
    """Handle data processed events"""
    data = event.get("data", {})
    logger.info(f"Data processed: {data.get('record_count', 0)} records")


@subscribe_to_event("user_action")
def handle_user_action(event: dict[str, Any]):
    """Handle user action events"""
    data = event.get("data", {})
    logger.info(f"User action: {data.get('action')} by {data.get('user')}")


# Integration with existing systems
def integrate_with_workflow_engine(workflow_engine):
    """Integrate signals and hooks with workflow engine"""
    # This would be called during workflow engine initialization
    # to connect the signal and hook systems with the workflow execution

    # Example integration points:
    # - Workflow execution events
    # - Job execution events
    # - Stage execution events
    # - Error handling
    # - Performance monitoring

    logger.info("Signals and hooks integrated with workflow engine")


# Example usage
if __name__ == "__main__":
    # Example signal emission
    emit_signal(
        SignalType.WORKFLOW_STARTED,
        "workflow_engine",
        {"workflow_id": "test_workflow", "user": "admin"},
    )

    # Example hook execution
    asyncio.run(
        execute_hooks(
            HookType.PRE_WORKFLOW,
            {
                "workflow_id": "test_workflow",
                "workflow_data": {"name": "Test Workflow"},
            },
        )
    )

    # Example custom event
    asyncio.run(publish_event("custom_event", {"message": "Hello World"}))
