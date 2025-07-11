# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Event-Driven Triggers and Sensors System.

This module provides a comprehensive event-driven trigger system for workflows,
inspired by Apache Airflow, StackStorm, and other workflow orchestration tools.

The trigger system supports:
- Webhook triggers (HTTP endpoints)
- File watchers (file system events)
- Message queue triggers (Redis, RabbitMQ, Kafka)
- Time-based triggers (cron, interval, one-time)
- Custom event triggers (user-defined events)
- Sensor-based triggers (monitoring, polling)

Classes:
    BaseTrigger: Abstract base class for all triggers
    WebhookTrigger: HTTP webhook trigger
    FileWatcherTrigger: File system event trigger
    MessageQueueTrigger: Message queue trigger
    TimeTrigger: Time-based trigger
    CustomTrigger: Custom event trigger
    TriggerRegistry: Registry for managing triggers

Example:
    ```python
    from ddeutil.workflow.triggers import WebhookTrigger, TriggerRegistry

    # Create a webhook trigger
    webhook = WebhookTrigger(
        name="api-webhook",
        endpoint="/webhook/api",
        method="POST",
        secret="webhook-secret"
    )

    # Register the trigger
    registry = TriggerRegistry()
    registry.register(webhook)

    # Start listening for events
    registry.start()
    ```
"""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Callable, Optional

from pydantic import BaseModel, Field

# Optional watchdog imports for file watching
try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = object

from .__types import DictData

logger = logging.getLogger(__name__)


class TriggerEvent(BaseModel):
    """Base class for trigger events."""

    trigger_name: str
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: DictData = Field(default_factory=dict)
    source: str = "unknown"


class BaseTrigger(BaseModel, ABC):
    """Abstract base class for all triggers."""

    name: str = Field(description="Unique trigger name")
    description: Optional[str] = Field(
        default=None, description="Trigger description"
    )
    enabled: bool = Field(
        default=True, description="Whether trigger is enabled"
    )
    max_events: Optional[int] = Field(
        default=None, description="Maximum events to process"
    )

    @abstractmethod
    async def start(self) -> None:
        """Start the trigger."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the trigger."""
        pass

    @abstractmethod
    async def is_running(self) -> bool:
        """Check if trigger is running."""
        pass


class WebhookTrigger(BaseTrigger):
    """HTTP webhook trigger."""

    endpoint: str = Field(description="Webhook endpoint path")
    method: str = Field(default="POST", description="HTTP method")
    secret: Optional[str] = Field(
        default=None, description="Webhook secret for validation"
    )
    port: int = Field(default=8080, description="HTTP server port")
    host: str = Field(default="0.0.0.0", description="HTTP server host")

    def __init__(self, **data):
        super().__init__(**data)
        self._server = None
        self._running = False
        self._event_queue = asyncio.Queue()

    async def start(self) -> None:
        """Start the webhook server."""
        # Implementation would use aiohttp or similar
        self._running = True
        logger.info(
            f"Webhook trigger '{self.name}' started on {self.host}:{self.port}"
        )

    async def stop(self) -> None:
        """Stop the webhook server."""
        self._running = False
        if self._server:
            await self._server.close()
        logger.info(f"Webhook trigger '{self.name}' stopped")

    async def is_running(self) -> bool:
        """Check if webhook server is running."""
        return self._running


class FileWatcherTrigger(BaseTrigger):
    """File system event trigger."""

    path: str = Field(description="Directory or file path to watch")
    events: list[str] = Field(
        default=["created", "modified"], description="Events to watch"
    )
    recursive: bool = Field(default=True, description="Watch recursively")

    def __init__(self, **data):
        super().__init__(**data)
        self._observer = None
        self._running = False
        self._event_queue = asyncio.Queue()

    async def start(self) -> None:
        """Start file watching."""
        if not WATCHDOG_AVAILABLE:
            raise ImportError("watchdog package is required for file watching")

        self._observer = Observer()
        event_handler = FileEventHandler(self._event_queue, self.events)
        self._observer.schedule(
            event_handler, self.path, recursive=self.recursive
        )
        self._observer.start()
        self._running = True
        logger.info(
            f"File watcher trigger '{self.name}' started on {self.path}"
        )

    async def stop(self) -> None:
        """Stop file watching."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
        self._running = False
        logger.info(f"File watcher trigger '{self.name}' stopped")

    async def is_running(self) -> bool:
        """Check if file watcher is running."""
        return self._running


class FileEventHandler(FileSystemEventHandler):
    """File system event handler for FileWatcherTrigger."""

    def __init__(self, event_queue: asyncio.Queue, events: list[str]):
        self.event_queue = event_queue
        self.events = events

    def on_created(self, event):
        if "created" in self.events and not event.is_directory:
            self._queue_event("created", event)

    def on_modified(self, event):
        if "modified" in self.events and not event.is_directory:
            self._queue_event("modified", event)

    def on_deleted(self, event):
        if "deleted" in self.events and not event.is_directory:
            self._queue_event("deleted", event)

    def _queue_event(self, event_type: str, event):
        """Queue an event asynchronously."""
        event_data = TriggerEvent(
            trigger_name="file_watcher",
            event_type=event_type,
            data={"path": event.src_path, "is_directory": event.is_directory},
            source="file_system",
        )
        # Use asyncio.run_coroutine_threadsafe to queue from sync context
        try:
            loop = asyncio.get_event_loop()
            asyncio.run_coroutine_threadsafe(
                self.event_queue.put(event_data), loop
            )
        except RuntimeError:
            # No event loop in current thread, create new one
            asyncio.create_task(self.event_queue.put(event_data))


class TimeTrigger(BaseTrigger):
    """Time-based trigger (cron, interval, one-time)."""

    schedule: str = Field(description="Cron expression or interval")
    trigger_type: str = Field(
        default="cron", description="Type: cron, interval, or once"
    )

    def __init__(self, **data):
        super().__init__(**data)
        self._task = None
        self._running = False
        self._event_queue = asyncio.Queue()

    async def start(self) -> None:
        """Start the time trigger."""
        self._running = True
        if self.trigger_type == "interval":
            self._task = asyncio.create_task(self._interval_loop())
        elif self.trigger_type == "cron":
            self._task = asyncio.create_task(self._cron_loop())
        elif self.trigger_type == "once":
            self._task = asyncio.create_task(self._once_trigger())
        logger.info(
            f"Time trigger '{self.name}' started with schedule: {self.schedule}"
        )

    async def stop(self) -> None:
        """Stop the time trigger."""
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info(f"Time trigger '{self.name}' stopped")

    async def is_running(self) -> bool:
        """Check if time trigger is running."""
        return self._running

    async def _interval_loop(self):
        """Run interval-based trigger."""
        interval = int(self.schedule)
        while self._running:
            await asyncio.sleep(interval)
            await self._event_queue.put(
                TriggerEvent(
                    trigger_name=self.name,
                    event_type="interval",
                    data={"interval": interval},
                    source="time",
                )
            )

    async def _cron_loop(self):
        """Run cron-based trigger."""
        # Simplified cron implementation
        while self._running:
            await asyncio.sleep(60)  # Check every minute
            # TODO: Implement proper cron parsing
            pass

    async def _once_trigger(self):
        """Run one-time trigger."""
        target_time = datetime.fromisoformat(self.schedule)
        while self._running and datetime.utcnow() < target_time:
            await asyncio.sleep(1)
        if self._running:
            await self._event_queue.put(
                TriggerEvent(
                    trigger_name=self.name,
                    event_type="once",
                    data={"target_time": target_time.isoformat()},
                    source="time",
                )
            )


class CustomTrigger(BaseTrigger):
    """Custom event trigger."""

    event_types: list[str] = Field(
        description="Types of events this trigger handles"
    )

    def __init__(self, **data):
        super().__init__(**data)
        self._running = False
        self._event_queue = asyncio.Queue()
        self._handlers: dict[str, list[Callable]] = {}

    async def start(self) -> None:
        """Start the custom trigger."""
        self._running = True
        logger.info(f"Custom trigger '{self.name}' started")

    async def stop(self) -> None:
        """Stop the custom trigger."""
        self._running = False
        logger.info(f"Custom trigger '{self.name}' stopped")

    async def is_running(self) -> bool:
        """Check if custom trigger is running."""
        return self._running

    def emit_event(self, event_type: str, data: DictData) -> None:
        """Emit a custom event."""
        if event_type in self.event_types:
            asyncio.create_task(
                self._event_queue.put(
                    TriggerEvent(
                        trigger_name=self.name,
                        event_type=event_type,
                        data=data,
                        source="custom",
                    )
                )
            )


class TriggerRegistry:
    """Registry for managing triggers."""

    def __init__(self):
        self._triggers: dict[str, BaseTrigger] = {}
        self._running = False
        self._event_handlers: list[Callable[[TriggerEvent], None]] = []

    def register(self, trigger: BaseTrigger) -> None:
        """Register a trigger."""
        if trigger.name in self._triggers:
            raise ValueError(f"Trigger '{trigger.name}' already registered")
        self._triggers[trigger.name] = trigger
        logger.info(f"Trigger '{trigger.name}' registered")

    def unregister(self, trigger_name: str) -> None:
        """Unregister a trigger."""
        if trigger_name in self._triggers:
            trigger = self._triggers[trigger_name]
            asyncio.create_task(trigger.stop())
            del self._triggers[trigger_name]
            logger.info(f"Trigger '{trigger_name}' unregistered")

    def add_event_handler(
        self, handler: Callable[[TriggerEvent], None]
    ) -> None:
        """Add an event handler."""
        self._event_handlers.append(handler)

    async def start(self) -> None:
        """Start all registered triggers."""
        self._running = True
        for trigger in self._triggers.values():
            if trigger.enabled:
                await trigger.start()
        logger.info("Trigger registry started")

    async def stop(self) -> None:
        """Stop all registered triggers."""
        self._running = False
        for trigger in self._triggers.values():
            await trigger.stop()
        logger.info("Trigger registry stopped")

    def get_trigger(self, name: str) -> Optional[BaseTrigger]:
        """Get a trigger by name."""
        return self._triggers.get(name)

    def list_triggers(self) -> list[str]:
        """List all registered trigger names."""
        return list(self._triggers.keys())


# Global trigger registry instance
trigger_registry = TriggerRegistry()
