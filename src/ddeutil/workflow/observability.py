# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Observability and UI Dashboard System.

This module provides comprehensive observability for workflows, including
audit trails, metrics collection, monitoring, and web-based UI dashboards.
Inspired by Apache Airflow, Prefect, and Dagster monitoring capabilities.

Features:
- Audit trail and logging
- Metrics collection and monitoring
- Web-based UI dashboard
- Real-time status monitoring
- Manual trigger interface
- Performance analytics
- Health checks and alerts

Classes:
    MetricsCollector: Collect and store metrics
    AuditLogger: Audit trail logging
    DashboardServer: Web-based dashboard
    HealthMonitor: System health monitoring
    PerformanceAnalyzer: Performance analytics
    AlertManager: Alert and notification system

Example:
    ```python
    from ddeutil.workflow.observability import DashboardServer, MetricsCollector

    # Start metrics collection
    metrics = MetricsCollector()
    metrics.start()

    # Start dashboard server
    dashboard = DashboardServer(port=8080)
    dashboard.start()
    ```
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Union

# Optional web framework imports
try:
    import uvicorn
    from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse

    WEB_FRAMEWORK_AVAILABLE = True
except ImportError:
    WEB_FRAMEWORK_AVAILABLE = False
    FastAPI = None
    uvicorn = None


logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Metric type enumeration."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class AlertLevel(Enum):
    """Alert level enumeration."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Metric:
    """Metric data point."""

    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    labels: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditEvent:
    """Audit event record."""

    event_type: str
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    user: Optional[str] = None
    workflow_name: Optional[str] = None
    run_id: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass
class Alert:
    """Alert definition."""

    id: str
    name: str
    level: AlertLevel
    message: str
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """Collect and store metrics."""

    def __init__(self, storage_path: Optional[Union[str, Path]] = None):
        self.metrics: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=10000)
        )
        self.storage_path = (
            Path(storage_path) if storage_path else Path("./metrics_data")
        )
        self.storage_path.mkdir(exist_ok=True)
        self.running = False
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start metrics collection."""
        self.running = True
        logger.info("Metrics collector started")

    def stop(self) -> None:
        """Stop metrics collection."""
        self.running = False
        logger.info("Metrics collector stopped")

    def record_metric(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.GAUGE,
        labels: Optional[dict[str, str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record a metric."""
        metric = Metric(
            name=name,
            value=value,
            metric_type=metric_type,
            labels=labels or {},
            metadata=metadata or {},
        )

        with self._lock:
            self.metrics[name].append(metric)

        logger.debug(f"Recorded metric: {name}={value}")

    def increment_counter(
        self, name: str, value: float = 1.0, **kwargs
    ) -> None:
        """Increment a counter metric."""
        self.record_metric(name, value, MetricType.COUNTER, **kwargs)

    def set_gauge(self, name: str, value: float, **kwargs) -> None:
        """Set a gauge metric."""
        self.record_metric(name, value, MetricType.GAUGE, **kwargs)

    def record_timer(self, name: str, duration: float, **kwargs) -> None:
        """Record a timer metric."""
        self.record_metric(name, duration, MetricType.TIMER, **kwargs)

    def get_metrics(
        self,
        name: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> list[Metric]:
        """Get metrics."""
        with self._lock:
            if name:
                metrics = list(self.metrics.get(name, []))
            else:
                metrics = []
                for metric_list in self.metrics.values():
                    metrics.extend(metric_list)

        # Filter by time
        if since:
            metrics = [m for m in metrics if m.timestamp >= since]

        # Sort by timestamp
        metrics.sort(key=lambda x: x.timestamp)

        # Apply limit
        if limit:
            metrics = metrics[-limit:]

        return metrics

    def get_metric_summary(
        self, name: str, window_minutes: int = 60
    ) -> dict[str, Any]:
        """Get metric summary for a time window."""
        since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        metrics = self.get_metrics(name=name, since=since)

        if not metrics:
            return {"count": 0, "min": 0, "max": 0, "avg": 0, "sum": 0}

        values = [m.value for m in metrics]
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "sum": sum(values),
        }

    def save_metrics(self) -> None:
        """Save metrics to storage."""
        with self._lock:
            data = {}
            for name, metric_list in self.metrics.items():
                data[name] = [
                    {
                        "name": m.name,
                        "value": m.value,
                        "metric_type": m.metric_type.value,
                        "timestamp": m.timestamp.isoformat(),
                        "labels": m.labels,
                        "metadata": m.metadata,
                    }
                    for m in metric_list
                ]

        with open(self.storage_path / "metrics.json", "w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"Saved metrics to {self.storage_path}")


class AuditLogger:
    """Audit trail logging."""

    def __init__(self, storage_path: Optional[Union[str, Path]] = None):
        self.events: list[AuditEvent] = []
        self.storage_path = (
            Path(storage_path) if storage_path else Path("./audit_data")
        )
        self.storage_path.mkdir(exist_ok=True)
        self._lock = threading.Lock()

    def log_event(
        self,
        event_type: str,
        user: Optional[str] = None,
        workflow_name: Optional[str] = None,
        run_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Log an audit event."""
        event = AuditEvent(
            event_type=event_type,
            user=user,
            workflow_name=workflow_name,
            run_id=run_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        with self._lock:
            self.events.append(event)

        logger.info(f"Audit event: {event_type} - {workflow_name or 'system'}")

    def get_events(
        self,
        event_type: Optional[str] = None,
        workflow_name: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> list[AuditEvent]:
        """Get audit events."""
        with self._lock:
            events = list(self.events)

        # Filter by event type
        if event_type:
            events = [e for e in events if e.event_type == event_type]

        # Filter by workflow
        if workflow_name:
            events = [e for e in events if e.workflow_name == workflow_name]

        # Filter by time
        if since:
            events = [e for e in events if e.timestamp >= since]

        # Sort by timestamp (newest first)
        events.sort(key=lambda x: x.timestamp, reverse=True)

        # Apply limit
        if limit:
            events = events[:limit]

        return events

    def save_audit_data(self) -> None:
        """Save audit data to storage."""
        with self._lock:
            data = [
                {
                    "event_type": e.event_type,
                    "timestamp": e.timestamp.isoformat(),
                    "user": e.user,
                    "workflow_name": e.workflow_name,
                    "run_id": e.run_id,
                    "details": e.details,
                    "ip_address": e.ip_address,
                    "user_agent": e.user_agent,
                }
                for e in self.events
            ]

        with open(self.storage_path / "audit_events.json", "w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"Saved audit data to {self.storage_path}")


class HealthMonitor:
    """System health monitoring."""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self.health_checks: dict[str, callable] = {}
        self.running = False
        self._lock = threading.Lock()

    def add_health_check(self, name: str, check_func: callable) -> None:
        """Add a health check."""
        self.health_checks[name] = check_func

    def start(self) -> None:
        """Start health monitoring."""
        self.running = True
        logger.info("Health monitor started")

    def stop(self) -> None:
        """Stop health monitoring."""
        self.running = False
        logger.info("Health monitor stopped")

    def run_health_checks(self) -> dict[str, dict[str, Any]]:
        """Run all health checks."""
        results = {}

        for name, check_func in self.health_checks.items():
            try:
                result = check_func()
                results[name] = {
                    "status": "healthy" if result else "unhealthy",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "details": result,
                }
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error": str(e),
                }

        return results


class AlertManager:
    """Alert and notification system."""

    def __init__(self):
        self.alerts: list[Alert] = []
        self.alert_rules: dict[str, callable] = {}
        self._lock = threading.Lock()

    def add_alert_rule(self, name: str, rule_func: callable) -> None:
        """Add an alert rule."""
        self.alert_rules[name] = rule_func

    def create_alert(
        self,
        name: str,
        level: AlertLevel,
        message: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Alert:
        """Create a new alert."""
        alert = Alert(
            id=f"{int(time.time())}_{name}",
            name=name,
            level=level,
            message=message,
            metadata=metadata or {},
        )

        with self._lock:
            self.alerts.append(alert)

        logger.warning(f"Alert created: {level.value} - {message}")
        return alert

    def acknowledge_alert(self, alert_id: str, user: str) -> bool:
        """Acknowledge an alert."""
        with self._lock:
            for alert in self.alerts:
                if alert.id == alert_id and not alert.acknowledged:
                    alert.acknowledged = True
                    alert.acknowledged_by = user
                    alert.acknowledged_at = datetime.now(timezone.utc)
                    return True
        return False

    def get_active_alerts(self) -> list[Alert]:
        """Get active (unacknowledged) alerts."""
        with self._lock:
            return [a for a in self.alerts if not a.acknowledged]

    def get_alerts(
        self,
        level: Optional[AlertLevel] = None,
        acknowledged: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> list[Alert]:
        """Get alerts with filters."""
        with self._lock:
            alerts = list(self.alerts)

        # Filter by level
        if level:
            alerts = [a for a in alerts if a.level == level]

        # Filter by acknowledged status
        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]

        # Sort by timestamp (newest first)
        alerts.sort(key=lambda x: x.timestamp, reverse=True)

        # Apply limit
        if limit:
            alerts = alerts[:limit]

        return alerts


class PerformanceAnalyzer:
    """Performance analytics."""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector

    def analyze_workflow_performance(
        self, workflow_name: str, window_hours: int = 24
    ) -> dict[str, Any]:
        """Analyze workflow performance."""
        since = datetime.now(timezone.utc) - timedelta(hours=window_hours)

        # Get execution metrics
        execution_metrics = self.metrics.get_metrics(
            name=f"workflow.{workflow_name}.execution_time", since=since
        )

        # Get success/failure metrics
        success_metrics = self.metrics.get_metrics(
            name=f"workflow.{workflow_name}.success", since=since
        )

        failure_metrics = self.metrics.get_metrics(
            name=f"workflow.{workflow_name}.failure", since=since
        )

        # Calculate statistics
        execution_times = [m.value for m in execution_metrics]
        total_runs = len(success_metrics) + len(failure_metrics)
        success_rate = (
            len(success_metrics) / total_runs if total_runs > 0 else 0
        )

        return {
            "workflow_name": workflow_name,
            "window_hours": window_hours,
            "total_runs": total_runs,
            "success_rate": success_rate,
            "avg_execution_time": (
                sum(execution_times) / len(execution_times)
                if execution_times
                else 0
            ),
            "min_execution_time": (
                min(execution_times) if execution_times else 0
            ),
            "max_execution_time": (
                max(execution_times) if execution_times else 0
            ),
            "success_count": len(success_metrics),
            "failure_count": len(failure_metrics),
        }

    def get_system_performance_summary(self) -> dict[str, Any]:
        """Get system-wide performance summary."""
        # Get system metrics
        cpu_usage = self.metrics.get_metric_summary("system.cpu_usage", 60)
        memory_usage = self.metrics.get_metric_summary(
            "system.memory_usage", 60
        )
        active_workflows = self.metrics.get_metric_summary(
            "system.active_workflows", 60
        )

        return {
            "cpu_usage": cpu_usage,
            "memory_usage": memory_usage,
            "active_workflows": active_workflows,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class DashboardServer:
    """Web-based dashboard server."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        if not WEB_FRAMEWORK_AVAILABLE:
            raise ImportError(
                "FastAPI and uvicorn are required for dashboard server"
            )

        self.host = host
        self.port = port
        self.app = FastAPI(title="Workflow Dashboard", version="1.0.0")
        self.websocket_connections: list[WebSocket] = []
        self.metrics_collector: Optional[MetricsCollector] = None
        self.audit_logger: Optional[AuditLogger] = None
        self.alert_manager: Optional[AlertManager] = None

        self._setup_routes()

    def _setup_routes(self) -> None:
        """Setup API routes."""

        @self.app.get("/")
        async def dashboard_home():
            """Dashboard home page."""
            return HTMLResponse(self._get_dashboard_html())

        @self.app.get("/api/metrics")
        async def get_metrics(
            name: Optional[str] = None, limit: Optional[int] = 100
        ):
            """Get metrics API."""
            if not self.metrics_collector:
                raise HTTPException(
                    status_code=503, detail="Metrics collector not available"
                )

            metrics = self.metrics_collector.get_metrics(name=name, limit=limit)
            return [self._metric_to_dict(m) for m in metrics]

        @self.app.get("/api/audit")
        async def get_audit_events(limit: Optional[int] = 100):
            """Get audit events API."""
            if not self.audit_logger:
                raise HTTPException(
                    status_code=503, detail="Audit logger not available"
                )

            events = self.audit_logger.get_events(limit=limit)
            return [self._audit_event_to_dict(e) for e in events]

        @self.app.get("/api/alerts")
        async def get_alerts():
            """Get alerts API."""
            if not self.alert_manager:
                raise HTTPException(
                    status_code=503, detail="Alert manager not available"
                )

            alerts = self.alert_manager.get_active_alerts()
            return [self._alert_to_dict(a) for a in alerts]

        @self.app.post("/api/workflows/{workflow_name}/trigger")
        async def trigger_workflow(workflow_name: str):
            """Trigger workflow manually."""
            try:
                # This would integrate with the workflow system
                # For now, just log the event
                if self.audit_logger:
                    self.audit_logger.log_event(
                        "workflow_triggered",
                        workflow_name=workflow_name,
                        details={"triggered_by": "dashboard"},
                    )

                return {"status": "triggered", "workflow": workflow_name}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await websocket.accept()
            self.websocket_connections.append(websocket)

            try:
                while True:
                    # Send periodic updates
                    await asyncio.sleep(5)
                    if self.metrics_collector:
                        summary = self.metrics_collector.get_metric_summary(
                            "system.active_workflows", 5
                        )
                        await websocket.send_text(
                            json.dumps(
                                {"type": "metrics_update", "data": summary}
                            )
                        )
            except WebSocketDisconnect:
                self.websocket_connections.remove(websocket)

    def _metric_to_dict(self, metric: Metric) -> dict[str, Any]:
        """Convert metric to dictionary."""
        return {
            "name": metric.name,
            "value": metric.value,
            "metric_type": metric.metric_type.value,
            "timestamp": metric.timestamp.isoformat(),
            "labels": metric.labels,
            "metadata": metric.metadata,
        }

    def _audit_event_to_dict(self, event: AuditEvent) -> dict[str, Any]:
        """Convert audit event to dictionary."""
        return {
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "user": event.user,
            "workflow_name": event.workflow_name,
            "run_id": event.run_id,
            "details": event.details,
            "ip_address": event.ip_address,
            "user_agent": event.user_agent,
        }

    def _alert_to_dict(self, alert: Alert) -> dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "id": alert.id,
            "name": alert.name,
            "level": alert.level.value,
            "message": alert.message,
            "timestamp": alert.timestamp.isoformat(),
            "acknowledged": alert.acknowledged,
            "acknowledged_by": alert.acknowledged_by,
            "acknowledged_at": (
                alert.acknowledged_at.isoformat()
                if alert.acknowledged_at
                else None
            ),
            "metadata": alert.metadata,
        }

    def _get_dashboard_html(self) -> str:
        """Get dashboard HTML."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Workflow Dashboard</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .metric-card { border: 1px solid #ddd; padding: 15px; margin: 10px; border-radius: 5px; }
                .alert { background-color: #ffebee; border-left: 4px solid #f44336; padding: 10px; margin: 10px; }
                .success { background-color: #e8f5e8; border-left: 4px solid #4caf50; padding: 10px; margin: 10px; }
            </style>
        </head>
        <body>
            <h1>Workflow Dashboard</h1>
            <div id="metrics"></div>
            <div id="alerts"></div>
            <div id="audit"></div>
            <script>
                // Simple dashboard JavaScript
                async function loadMetrics() {
                    const response = await fetch('/api/metrics');
                    const metrics = await response.json();
                    document.getElementById('metrics').innerHTML =
                        '<h2>Metrics</h2>' +
                        metrics.map(m => `<div class="metric-card">${m.name}: ${m.value}</div>`).join('');
                }

                async function loadAlerts() {
                    const response = await fetch('/api/alerts');
                    const alerts = await response.json();
                    document.getElementById('alerts').innerHTML =
                        '<h2>Alerts</h2>' +
                        alerts.map(a => `<div class="alert">${a.level}: ${a.message}</div>`).join('');
                }

                // Load data every 30 seconds
                loadMetrics();
                loadAlerts();
                setInterval(loadMetrics, 30000);
                setInterval(loadAlerts, 30000);
            </script>
        </body>
        </html>
        """

    def start(self) -> None:
        """Start the dashboard server."""
        uvicorn.run(self.app, host=self.host, port=self.port)

    def set_components(
        self,
        metrics_collector: Optional[MetricsCollector] = None,
        audit_logger: Optional[AuditLogger] = None,
        alert_manager: Optional[AlertManager] = None,
    ) -> None:
        """Set dashboard components."""
        self.metrics_collector = metrics_collector
        self.audit_logger = audit_logger
        self.alert_manager = alert_manager


# Global instances
metrics_collector = MetricsCollector()
audit_logger = AuditLogger()
alert_manager = AlertManager()
health_monitor = HealthMonitor(metrics_collector)
performance_analyzer = PerformanceAnalyzer(metrics_collector)

# Initialize dashboard if web framework is available
if WEB_FRAMEWORK_AVAILABLE:
    dashboard_server = DashboardServer()
    dashboard_server.set_components(
        metrics_collector, audit_logger, alert_manager
    )
else:
    dashboard_server = None
