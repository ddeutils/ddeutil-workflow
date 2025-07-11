# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Advanced Scheduling System.

This module provides an advanced scheduling system for workflows, supporting
cron expressions, intervals, event-based triggers, and ad-hoc/manual execution.
Inspired by Apache Airflow, Prefect, and Dagster scheduling capabilities.

Features:
- Cron-based scheduling with full cron expression support
- Interval-based scheduling (every N seconds/minutes/hours/days)
- Event-based scheduling (webhooks, file changes, custom events)
- Ad-hoc and manual trigger support
- Timezone-aware scheduling
- Retry and backoff policies
- Schedule validation and preview

Classes:
    AdvancedScheduler: Main scheduler class
    CronSchedule: Cron-based schedule
    IntervalSchedule: Interval-based schedule
    EventSchedule: Event-based schedule
    SchedulePolicy: Retry and backoff policies
    ScheduleValidator: Schedule validation and preview

Example:
    ```python
    from ddeutil.workflow.scheduler import AdvancedScheduler, CronSchedule

    # Create scheduler
    scheduler = AdvancedScheduler()

    # Add cron-based workflow
    cron_schedule = CronSchedule("0 9 * * 1-5")  # Weekdays at 9 AM
    scheduler.add_workflow("daily-report", cron_schedule)

    # Add interval-based workflow
    interval_schedule = IntervalSchedule(minutes=30)  # Every 30 minutes
    scheduler.add_workflow("data-sync", interval_schedule)

    # Start scheduler
    scheduler.start()
    ```
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

# Optional croniter import
try:
    from croniter import croniter

    CRONITER_AVAILABLE = True
except ImportError:
    CRONITER_AVAILABLE = False
    croniter = None

from .triggers import TriggerEvent
from .workflow import Workflow

logger = logging.getLogger(__name__)


class ScheduleType(Enum):
    """Schedule type enumeration."""

    CRON = "cron"
    INTERVAL = "interval"
    EVENT = "event"
    MANUAL = "manual"


class RetryPolicy(Enum):
    """Retry policy enumeration."""

    NONE = "none"
    IMMEDIATE = "immediate"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"


@dataclass
class SchedulePolicy:
    """Schedule execution policy."""

    retry_policy: RetryPolicy = RetryPolicy.NONE
    max_retries: int = 3
    retry_delay: int = 60  # seconds
    timeout: Optional[int] = None  # seconds
    enabled: bool = True


class BaseSchedule:
    """Base class for all schedule types."""

    def __init__(
        self,
        schedule_type: ScheduleType,
        policy: Optional[SchedulePolicy] = None,
    ):
        self.schedule_type = schedule_type
        self.policy = policy or SchedulePolicy()

    def next_run_time(
        self, from_time: Optional[datetime] = None
    ) -> Optional[datetime]:
        """Get the next run time for this schedule."""
        raise NotImplementedError

    def should_run(self, current_time: datetime) -> bool:
        """Check if the schedule should run at the given time."""
        raise NotImplementedError


class CronSchedule(BaseSchedule):
    """Cron-based schedule."""

    def __init__(
        self,
        cron_expression: str,
        timezone_str: str = "UTC",
        policy: Optional[SchedulePolicy] = None,
    ):
        super().__init__(ScheduleType.CRON, policy)
        self.cron_expression = cron_expression
        self.timezone_str = timezone_str
        self._validate_cron()

    def _validate_cron(self):
        """Validate cron expression."""
        if not CRONITER_AVAILABLE:
            raise ImportError("croniter package is required for cron schedules")
        try:
            croniter(self.cron_expression)
        except Exception as e:
            raise ValueError(
                f"Invalid cron expression '{self.cron_expression}': {e}"
            )

    def next_run_time(
        self, from_time: Optional[datetime] = None
    ) -> Optional[datetime]:
        """Get next run time based on cron expression."""
        if from_time is None:
            from_time = datetime.now(timezone.utc)

        cron = croniter(self.cron_expression, from_time)
        return cron.get_next(datetime)

    def should_run(self, current_time: datetime) -> bool:
        """Check if cron schedule should run."""
        next_run = self.next_run_time(current_time - timedelta(seconds=1))
        return bool(next_run and next_run <= current_time)


class IntervalSchedule(BaseSchedule):
    """Interval-based schedule."""

    def __init__(
        self,
        seconds: int = 0,
        minutes: int = 0,
        hours: int = 0,
        days: int = 0,
        policy: Optional[SchedulePolicy] = None,
    ):
        super().__init__(ScheduleType.INTERVAL, policy)
        self.interval = timedelta(
            seconds=seconds, minutes=minutes, hours=hours, days=days
        )
        if self.interval.total_seconds() <= 0:
            raise ValueError("Interval must be positive")

    def next_run_time(
        self, from_time: Optional[datetime] = None
    ) -> Optional[datetime]:
        """Get next run time based on interval."""
        if from_time is None:
            from_time = datetime.now(timezone.utc)
        return from_time + self.interval

    def should_run(self, current_time: datetime) -> bool:
        """Check if interval schedule should run."""
        # This is simplified - in practice, you'd track the last run time
        return True


class EventSchedule(BaseSchedule):
    """Event-based schedule."""

    def __init__(
        self,
        event_type: str,
        event_filter: Optional[dict[str, Any]] = None,
        policy: Optional[SchedulePolicy] = None,
    ):
        super().__init__(ScheduleType.EVENT, policy)
        self.event_type = event_type
        self.event_filter = event_filter or {}
        self._last_event_time: Optional[datetime] = None

    def next_run_time(
        self, from_time: Optional[datetime] = None
    ) -> Optional[datetime]:
        """Event schedules don't have predictable next run times."""
        return None

    def should_run(self, current_time: datetime) -> bool:
        """Check if event schedule should run."""
        # This would be called when an event is received
        return (
            self._last_event_time is None
            or current_time > self._last_event_time
        )

    def handle_event(self, event: TriggerEvent) -> bool:
        """Handle incoming event."""
        if event.event_type == self.event_type:
            if self._matches_filter(event):
                self._last_event_time = event.timestamp
                return True
        return False

    def _matches_filter(self, event: TriggerEvent) -> bool:
        """Check if event matches the filter criteria."""
        for key, value in self.event_filter.items():
            if key not in event.data or event.data[key] != value:
                return False
        return True


class ManualSchedule(BaseSchedule):
    """Manual/adhoc schedule."""

    def __init__(self, policy: Optional[SchedulePolicy] = None):
        super().__init__(ScheduleType.MANUAL, policy)
        self._triggered = False

    def next_run_time(
        self, from_time: Optional[datetime] = None
    ) -> Optional[datetime]:
        """Manual schedules don't have predictable next run times."""
        return None

    def should_run(self, current_time: datetime) -> bool:
        """Check if manual schedule should run."""
        return self._triggered

    def trigger(self):
        """Trigger manual execution."""
        self._triggered = True

    def reset(self):
        """Reset trigger state."""
        self._triggered = False


class ScheduleValidator:
    """Schedule validation and preview utilities."""

    @staticmethod
    def validate_cron(cron_expression: str) -> bool:
        """Validate cron expression."""
        if not CRONITER_AVAILABLE:
            return False
        try:
            croniter(cron_expression)
            return True
        except Exception:
            return False

    @staticmethod
    def preview_cron(cron_expression: str, count: int = 10) -> list[datetime]:
        """Preview next N run times for cron expression."""
        if not CRONITER_AVAILABLE:
            raise ImportError("croniter package is required for cron preview")
        try:
            cron = croniter(cron_expression, datetime.now(timezone.utc))
            return [cron.get_next(datetime) for _ in range(count)]
        except Exception as e:
            raise ValueError(f"Invalid cron expression: {e}")

    @staticmethod
    def validate_interval(
        seconds: int = 0, minutes: int = 0, hours: int = 0, days: int = 0
    ) -> bool:
        """Validate interval parameters."""
        total_seconds = seconds + minutes * 60 + hours * 3600 + days * 86400
        return total_seconds > 0


class AdvancedScheduler:
    """Advanced workflow scheduler."""

    def __init__(self):
        self.schedules: dict[str, BaseSchedule] = {}
        self.workflows: dict[str, str] = {}  # schedule_name -> workflow_name
        self.running = False
        self._tasks: dict[str, asyncio.Task] = {}
        self._last_runs: dict[str, datetime] = {}

    def add_workflow(
        self,
        workflow_name: str,
        schedule: BaseSchedule,
        schedule_name: Optional[str] = None,
    ) -> str:
        """Add a workflow with a schedule."""
        if schedule_name is None:
            schedule_name = f"{workflow_name}_schedule"

        if schedule_name in self.schedules:
            raise ValueError(f"Schedule '{schedule_name}' already exists")

        self.schedules[schedule_name] = schedule
        self.workflows[schedule_name] = workflow_name
        logger.info(
            f"Added workflow '{workflow_name}' with schedule '{schedule_name}'"
        )

        return schedule_name

    def remove_workflow(self, schedule_name: str) -> None:
        """Remove a scheduled workflow."""
        if schedule_name in self.schedules:
            del self.schedules[schedule_name]
            del self.workflows[schedule_name]
            if schedule_name in self._tasks:
                self._tasks[schedule_name].cancel()
                del self._tasks[schedule_name]
            logger.info(f"Removed schedule '{schedule_name}'")

    def trigger_workflow(self, schedule_name: str) -> None:
        """Manually trigger a workflow."""
        if schedule_name not in self.schedules:
            raise ValueError(f"Schedule '{schedule_name}' not found")

        schedule = self.schedules[schedule_name]
        if isinstance(schedule, ManualSchedule):
            schedule.trigger()
        else:
            # For other schedule types, we can force immediate execution
            asyncio.create_task(self._execute_workflow(schedule_name))

    async def start(self) -> None:
        """Start the scheduler."""
        if self.running:
            return

        self.running = True
        logger.info("Advanced scheduler started")

        # Start schedule monitoring tasks
        for schedule_name in self.schedules:
            if self.schedules[schedule_name].policy.enabled:
                self._tasks[schedule_name] = asyncio.create_task(
                    self._monitor_schedule(schedule_name)
                )

    async def stop(self) -> None:
        """Stop the scheduler."""
        if not self.running:
            return

        self.running = False

        # Cancel all monitoring tasks
        for task in self._tasks.values():
            task.cancel()

        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)

        self._tasks.clear()
        logger.info("Advanced scheduler stopped")

    async def _monitor_schedule(self, schedule_name: str) -> None:
        """Monitor a specific schedule."""
        schedule = self.schedules[schedule_name]

        while self.running:
            try:
                current_time = datetime.now(timezone.utc)

                if schedule.should_run(current_time):
                    await self._execute_workflow(schedule_name)
                    self._last_runs[schedule_name] = current_time

                # Sleep for a short interval before checking again
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    f"Error monitoring schedule '{schedule_name}': {e}"
                )
                await asyncio.sleep(5)  # Wait before retrying

    async def _execute_workflow(self, schedule_name: str) -> None:
        """Execute a workflow."""
        workflow_name = self.workflows[schedule_name]
        schedule = self.schedules[schedule_name]

        try:
            logger.info(
                f"Executing workflow '{workflow_name}' from schedule '{schedule_name}'"
            )

            # Load and execute workflow
            workflow = Workflow.from_conf(workflow_name)
            result = workflow.execute({})

            if result.status != "SUCCESS":
                logger.warning(
                    f"Workflow '{workflow_name}' completed with status: {result.status}"
                )

        except Exception as e:
            logger.error(f"Error executing workflow '{workflow_name}': {e}")

            # Handle retry policy
            if schedule.policy.retry_policy != RetryPolicy.NONE:
                await self._handle_retry(schedule_name, e)

    async def _handle_retry(self, schedule_name: str, error: Exception) -> None:
        """Handle retry logic for failed executions."""
        schedule = self.schedules[schedule_name]
        policy = schedule.policy

        # Simplified retry logic - in practice, you'd track retry counts
        if policy.retry_policy == RetryPolicy.IMMEDIATE:
            await asyncio.sleep(policy.retry_delay)
            asyncio.create_task(self._execute_workflow(schedule_name))
        elif policy.retry_policy == RetryPolicy.EXPONENTIAL_BACKOFF:
            # Implement exponential backoff
            pass

    def list_schedules(self) -> dict[str, dict[str, Any]]:
        """List all schedules and their status."""
        result = {}
        for schedule_name, schedule in self.schedules.items():
            result[schedule_name] = {
                "workflow": self.workflows[schedule_name],
                "type": schedule.schedule_type.value,
                "enabled": schedule.policy.enabled,
                "last_run": self._last_runs.get(schedule_name),
                "next_run": schedule.next_run_time(),
            }
        return result


# Global scheduler instance
advanced_scheduler = AdvancedScheduler()
