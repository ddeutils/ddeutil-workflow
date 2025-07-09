# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Event Scheduling Module for Workflow Orchestration.

This module provides event-driven scheduling capabilities for workflows, with
a primary focus on cron-based scheduling. It includes models for defining
when workflows should be triggered and executed.

The core event trigger is the Crontab model, which wraps cron functionality
in a Pydantic model for validation and easy integration with the workflow system.

Attributes:
    Interval: Type alias for scheduling intervals ('daily', 'weekly', 'monthly')

Classes:
    Crontab: Main cron-based event scheduler.
    CrontabYear: Enhanced cron scheduler with year constraints.
    ReleaseEvent: Release-based event triggers.
    FileEvent: File system monitoring triggers.
    WebhookEvent: API/webhook-based triggers.
    DatabaseEvent: Database change monitoring triggers.
    SensorEvent: Sensor-based event monitoring.

Example:
    >>> from ddeutil.workflow.event import Crontab
    >>> # NOTE: Create daily schedule at 9 AM
    >>> schedule = Crontab.model_validate(
    ...     {
    ...         "cronjob": "0 9 * * *",
    ...         "timezone": "America/New_York",
    ...     }
    ... )
    >>> # NOTE: Generate next run times
    >>> runner = schedule.generate(datetime.now())
    >>> next_run = runner.next
"""
from __future__ import annotations

from dataclasses import fields
from datetime import datetime
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo
from pydantic.functional_serializers import field_serializer
from pydantic.functional_validators import field_validator, model_validator
from pydantic_extra_types.timezone_name import TimeZoneName

from .__cron import WEEKDAYS, CronJob, CronJobYear, CronRunner, Options
from .__types import DictData

Interval = Literal["daily", "weekly", "monthly"]


def interval2crontab(
    interval: Interval,
    *,
    day: Optional[str] = None,
    time: str = "00:00",
) -> str:
    """Convert interval specification to cron expression.

    Args:
        interval: Scheduling interval ('daily', 'weekly', or 'monthly').
        day: Day of week for weekly intervals or monthly schedules. Defaults to
            Monday for weekly intervals.
        time: Time of day in 'HH:MM' format. Defaults to '00:00'.

    Returns:
        Generated crontab expression string.

    Examples:
        >>> interval2crontab(interval='daily', time='01:30')
        '1 30 * * *'
        >>> interval2crontab(interval='weekly', day='friday', time='18:30')
        '18 30 * * 5'
        >>> interval2crontab(interval='monthly', time='00:00')
        '0 0 1 * *'
        >>> interval2crontab(interval='monthly', day='tuesday', time='12:00')
        '12 0 1 * 2'
    """
    d: str = "*"
    if interval == "weekly":
        d = str(WEEKDAYS[(day or "monday")[:3].title()])
    elif interval == "monthly" and day:
        d = str(WEEKDAYS[day[:3].title()])

    h, m = tuple(
        i.lstrip("0") if i != "00" else "0" for i in time.split(":", maxsplit=1)
    )
    return f"{h} {m} {'1' if interval == 'monthly' else '*'} * {d}"


class BaseCrontab(BaseModel):
    """Base class for crontab-based scheduling models.

    Attributes:
        extras: Additional parameters to pass to the CronJob field.
        tz: Timezone string value (alias: timezone).
    """

    extras: DictData = Field(
        default_factory=dict,
        description=(
            "An extras parameters that want to pass to the CronJob field."
        ),
    )
    tz: TimeZoneName = Field(
        default="UTC",
        description="A timezone string value that will pass to ZoneInfo.",
        alias="timezone",
    )

    @model_validator(mode="before")
    def __prepare_values(cls, data: Any) -> Any:
        """Extract and rename timezone key in input data.

        Args:
            data: Input data dictionary for creating Crontab model.

        Returns:
            Modified data dictionary with standardized timezone key.
        """
        if isinstance(data, dict) and (tz := data.pop("tz", None)):
            data["timezone"] = tz
        return data


class CrontabValue(BaseCrontab):
    """Crontab model using interval-based specification.

    Attributes:
        interval: (Interval)
            A scheduling interval string ('daily', 'weekly', 'monthly').
        day: (str, default None)
            Day specification for weekly/monthly schedules.
        time: Time of day in 'HH:MM' format.
    """

    interval: Interval = Field(description="A scheduling interval string.")
    day: Optional[str] = Field(default=None)
    time: str = Field(
        default="00:00",
        pattern=r"\d{2}:\d{2}",
        description="A time of day that pass with format 'HH:MM'.",
    )

    @property
    def cronjob(self) -> CronJob:
        """Get CronJob object built from interval format.

        Returns:
            CronJob instance configured with interval-based schedule.
        """
        return CronJob(
            value=interval2crontab(self.interval, day=self.day, time=self.time)
        )

    def generate(self, start: Union[str, datetime]) -> CronRunner:
        """Generate CronRunner from initial datetime.

        Args:
            start: Starting datetime (string or datetime object).

        Returns:
            CronRunner instance for schedule generation.

        Raises:
            TypeError: If start parameter is neither string nor datetime.
        """
        if isinstance(start, str):
            return self.cronjob.schedule(
                date=datetime.fromisoformat(start), tz=self.tz
            )

        if isinstance(start, datetime):
            return self.cronjob.schedule(date=start, tz=self.tz)
        raise TypeError("start value should be str or datetime type.")

    def next(self, start: Union[str, datetime]) -> CronRunner:
        """Get next scheduled datetime after given start time.

        Args:
            start: Starting datetime for schedule generation.

        Returns:
            CronRunner instance positioned at next scheduled time.
        """
        runner: CronRunner = self.generate(start=start)

        # NOTE: ship the next date of runner object that create from start.
        _ = runner.next

        return runner


class Crontab(BaseCrontab):
    """Cron event model wrapping CronJob functionality.

    A Pydantic model that encapsulates crontab scheduling functionality with
    validation and datetime generation capabilities.

    Attributes:
        cronjob: CronJob instance for schedule validation and datetime generation.
        tz: Timezone string value (alias: timezone).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    cronjob: CronJob = Field(
        description=(
            "A Cronjob object that use for validate and generate datetime."
        ),
    )

    @model_validator(mode="before")
    def __prepare_values(cls, data: Any) -> Any:
        """Prepare input data by standardizing timezone key.

        Args:
            data: Input dictionary for model creation.

        Returns:
            Modified dictionary with standardized timezone key.
        """
        if isinstance(data, dict) and (tz := data.pop("tz", None)):
            data["timezone"] = tz
        return data

    @field_validator(
        "cronjob", mode="before", json_schema_input_type=Union[CronJob, str]
    )
    def __prepare_cronjob(
        cls, value: Union[str, CronJob], info: ValidationInfo
    ) -> CronJob:
        """Prepare and validate cronjob input.

        Args:
            value: Raw cronjob value (string or CronJob instance).
            info: Validation context containing extra parameters.

        Returns:
            Configured CronJob instance.
        """
        extras: DictData = info.data.get("extras", {})
        return (
            CronJob(
                value,
                option={
                    name: extras[name]
                    for name in (f.name for f in fields(Options))
                    if name in extras
                },
            )
            if isinstance(value, str)
            else value
        )

    @field_serializer("cronjob")
    def __serialize_cronjob(self, value: CronJob) -> str:
        """Serialize CronJob instance to string representation.

        Args:
            value: CronJob instance to serialize.

        Returns:
            String representation of the CronJob.
        """
        return str(value)

    def generate(self, start: Union[str, datetime]) -> CronRunner:
        """Generate schedule runner from start time.

        Args:
            start: Starting datetime (string or datetime object).

        Returns:
            CronRunner instance for schedule generation.

        Raises:
            TypeError: If start parameter is neither string nor datetime.
        """
        if isinstance(start, str):
            start: datetime = datetime.fromisoformat(start)
        elif not isinstance(start, datetime):
            raise TypeError("start value should be str or datetime type.")
        return self.cronjob.schedule(date=start, tz=self.tz)

    def next(self, start: Union[str, datetime]) -> CronRunner:
        """Get runner positioned at next scheduled time.

        Args:
            start: Starting datetime for schedule generation.

        Returns:
            CronRunner instance positioned at next scheduled time.
        """
        runner: CronRunner = self.generate(start=start)

        # NOTE: ship the next date of runner object that create from start.
        _ = runner.next

        return runner


class CrontabYear(Crontab):
    """Cron event model with enhanced year-based scheduling.

    Extends the base Crontab model to support year-specific scheduling,
    particularly useful for tools like AWS Glue.

    Attributes:
        cronjob: CronJobYear instance for year-aware schedule validation and generation.
    """

    cronjob: CronJobYear = Field(
        description=(
            "A Cronjob object that use for validate and generate datetime."
        ),
    )

    @field_validator(
        "cronjob",
        mode="before",
        json_schema_input_type=Union[CronJobYear, str],
    )
    def __prepare_cronjob(
        cls, value: Union[CronJobYear, str], info: ValidationInfo
    ) -> CronJobYear:
        """Prepare and validate year-aware cronjob input.

        Args:
            value: Raw cronjob value (string or CronJobYear instance).
            info: Validation context containing extra parameters.

        Returns:
            Configured CronJobYear instance with applied options.
        """
        extras: DictData = info.data.get("extras", {})
        return (
            CronJobYear(
                value,
                option={
                    name: extras[name]
                    for name in (f.name for f in fields(Options))
                    if name in extras
                },
            )
            if isinstance(value, str)
            else value
        )


class FileEvent(BaseModel):
    """File system event trigger from external services.

    Triggers workflows based on file system events detected by external services
    such as cloud storage providers (Azure Storage, AWS S3, Google Cloud Storage).

    Attributes:
        path: Directory or file path pattern to match.
        pattern: File pattern to match (e.g., "*.csv", "data_*.json").
        event_type: Type of file event to trigger on.
        source: External service that detects the file event.
        recursive: Whether to monitor subdirectories recursively.
        debounce_seconds: Debounce time to prevent multiple triggers.
    """

    path: str = Field(description="Directory or file path pattern to match.")
    pattern: str = Field(
        default="*",
        description="File pattern to match (e.g., '*.csv', 'data_*.json').",
    )
    event_type: Literal["created", "modified", "deleted", "any"] = Field(
        default="any",
        description="Type of file event to trigger on.",
    )
    source: str = Field(
        description="External service that detects the file event (e.g., 'azure-storage', 'aws-s3', 'google-cloud-storage').",
    )
    recursive: bool = Field(
        default=False,
        description="Whether to monitor subdirectories recursively.",
    )
    debounce_seconds: int = Field(
        default=30,
        ge=0,
        description="Debounce time in seconds to prevent multiple triggers.",
    )


class WebhookEvent(BaseModel):
    """API/webhook-based event trigger.

    Triggers workflows based on HTTP webhook calls from external systems.

    Attributes:
        endpoint: Webhook endpoint path (e.g., '/webhook/data-arrival').
        method: HTTP method to accept (GET, POST, PUT, etc.).
        secret: Optional secret for webhook authentication.
        headers: Required headers for webhook validation.
        timeout_seconds: Timeout for webhook processing.
    """

    endpoint: str = Field(description="Webhook endpoint path.")
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = Field(
        default="POST",
        description="HTTP method to accept.",
    )
    secret: Optional[str] = Field(
        default=None,
        description="Optional secret for webhook authentication.",
    )
    headers: DictData = Field(
        default_factory=dict,
        description="Required headers for webhook validation.",
    )
    timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Timeout for webhook processing in seconds.",
    )


class DatabaseEvent(BaseModel):
    """Database change event trigger from external services.

    Triggers workflows based on database changes detected by external services
    such as Change Data Capture (CDC) systems or database replication services.

    Attributes:
        connection_string: Database connection string for reference.
        table: Table name to monitor for changes.
        operation: Database operation to trigger on.
        source: External service that detects database changes.
        query: Custom SQL query pattern to match.
        check_interval_seconds: Interval for external service to check (0 for real-time).
    """

    connection_string: str = Field(
        description="Database connection string for reference."
    )
    table: Optional[str] = Field(
        default=None,
        description="Table name to monitor for changes.",
    )
    operation: Literal["insert", "update", "delete", "any"] = Field(
        default="any",
        description="Database operation to trigger on.",
    )
    source: str = Field(
        description="External service that detects database changes (e.g., 'debezium-cdc', 'database-replication').",
    )
    query: Optional[str] = Field(
        default=None,
        description="Custom SQL query pattern to match.",
    )
    check_interval_seconds: int = Field(
        default=0,
        ge=0,
        le=3600,
        description="Interval in seconds for external service to check (0 for real-time events).",
    )


class SensorEvent(BaseModel):
    """Sensor-based event trigger from monitoring systems.

    Triggers workflows based on sensor data, metrics, or system conditions
    detected by external monitoring systems (Prometheus, DataDog, etc.).

    Attributes:
        sensor_type: Type of sensor or metric to monitor.
        threshold: Threshold value to trigger on.
        operator: Comparison operator for threshold evaluation.
        source: External monitoring system that detects sensor events.
        check_interval_seconds: Interval for external system to check (0 for real-time).
        window_size: Time window for sensor value aggregation.
    """

    sensor_type: str = Field(description="Type of sensor or metric to monitor.")
    threshold: Union[int, float] = Field(
        description="Threshold value to trigger on.",
    )
    operator: Literal["gt", "gte", "lt", "lte", "eq", "ne"] = Field(
        default="gt",
        description="Comparison operator for threshold evaluation.",
    )
    source: str = Field(
        description="External monitoring system that detects sensor events (e.g., 'prometheus-alertmanager', 'datadog-monitoring').",
    )
    check_interval_seconds: int = Field(
        default=0,
        ge=0,
        le=3600,
        description="Interval in seconds for external system to check (0 for real-time events).",
    )
    window_size: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Time window in seconds for sensor value aggregation.",
    )


class PollingEvent(BaseModel):
    """Polling-based event trigger for systems without event capabilities.

    Triggers workflows based on periodic polling of resources when external
    event systems are not available or as fallback mechanisms.

    Attributes:
        resource_type: Type of resource to poll (file, database, api, etc.).
        resource_path: Path or identifier of the resource to poll.
        check_interval_seconds: Interval in seconds between polling checks.
        condition: Condition to evaluate for triggering (optional).
        timeout_seconds: Timeout for polling operations.
        max_retries: Maximum number of retries on failure.
    """

    resource_type: Literal["file", "database", "api", "queue", "custom"] = (
        Field(
            description="Type of resource to poll.",
        )
    )
    resource_path: str = Field(
        description="Path or identifier of the resource to poll.",
    )
    check_interval_seconds: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Interval in seconds between polling checks.",
    )
    condition: Optional[str] = Field(
        default=None,
        description="Optional condition to evaluate for triggering (e.g., 'file_size > 0').",
    )
    timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Timeout for polling operations in seconds.",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retries on failure.",
    )


class MessageQueueEvent(BaseModel):
    """Message queue-based event trigger.

    Triggers workflows based on messages from message queue systems
    such as RabbitMQ, Apache Kafka, AWS SQS, or Azure Service Bus.

    Attributes:
        queue_name: Name of the queue to monitor.
        message_pattern: Pattern to match in message content.
        source: Message queue system (e.g., 'rabbitmq', 'kafka', 'aws-sqs').
        batch_size: Number of messages to process in batch.
        visibility_timeout: Message visibility timeout in seconds.
        dead_letter_queue: Dead letter queue for failed messages.
    """

    queue_name: str = Field(description="Name of the queue to monitor.")
    message_pattern: Optional[str] = Field(
        default=None,
        description="Pattern to match in message content (regex).",
    )
    source: str = Field(
        description="Message queue system (e.g., 'rabbitmq', 'kafka', 'aws-sqs', 'azure-service-bus').",
    )
    batch_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of messages to process in batch.",
    )
    visibility_timeout: int = Field(
        default=300,
        ge=30,
        le=43200,
        description="Message visibility timeout in seconds.",
    )
    dead_letter_queue: Optional[str] = Field(
        default=None,
        description="Dead letter queue for failed messages.",
    )


class StreamProcessingEvent(BaseModel):
    """Real-time stream processing event trigger.

    Triggers workflows based on stream processing events from systems
    such as Apache Kafka, Apache Flink, or AWS Kinesis.

    Attributes:
        stream_name: Name of the stream to monitor.
        window_size: Time window size in seconds for stream processing.
        aggregation_type: Type of aggregation to perform.
        source: Stream processing system (e.g., 'kafka', 'flink', 'kinesis').
        checkpoint_interval: Checkpoint interval in seconds.
        watermark_delay: Watermark delay for late data handling.
    """

    stream_name: str = Field(description="Name of the stream to monitor.")
    window_size: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Time window size in seconds for stream processing.",
    )
    aggregation_type: Literal["count", "sum", "avg", "min", "max", "custom"] = (
        Field(
            default="count",
            description="Type of aggregation to perform.",
        )
    )
    source: str = Field(
        description="Stream processing system (e.g., 'kafka', 'flink', 'kinesis').",
    )
    checkpoint_interval: int = Field(
        default=60,
        ge=10,
        le=300,
        description="Checkpoint interval in seconds.",
    )
    watermark_delay: int = Field(
        default=30,
        ge=0,
        le=300,
        description="Watermark delay in seconds for late data handling.",
    )


class BatchProcessingEvent(BaseModel):
    """Batch processing completion event trigger.

    Triggers workflows based on batch job completion events from systems
    such as Apache Spark, AWS EMR, or Azure HDInsight.

    Attributes:
        job_name: Name of the batch job to monitor.
        job_status: Expected job status to trigger on.
        source: Batch processing system (e.g., 'spark', 'emr', 'hdinsight', 'databricks').
        timeout_minutes: Job timeout in minutes.
        retry_count: Number of retries on failure.
        dependencies: List of dependent jobs that must complete first.
    """

    job_name: str = Field(description="Name of the batch job to monitor.")
    job_status: Literal["completed", "failed", "cancelled", "any"] = Field(
        default="completed",
        description="Expected job status to trigger on.",
    )
    source: str = Field(
        description="Batch processing system (e.g., 'spark', 'emr', 'hdinsight', 'databricks').",
    )
    timeout_minutes: int = Field(
        default=120,
        ge=10,
        le=1440,
        description="Job timeout in minutes.",
    )
    retry_count: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Number of retries on failure.",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="List of dependent jobs that must complete first.",
    )


class DataQualityEvent(BaseModel):
    """Data quality monitoring event trigger.

    Triggers workflows based on data quality metrics and validation results
    from data quality monitoring systems like Great Expectations, Deequ, or custom validators.

    Attributes:
        quality_metric: Type of quality metric to monitor.
        threshold: Quality threshold value to trigger on.
        operator: Comparison operator for threshold evaluation.
        source: Data quality monitoring system.
        dataset_name: Name of the dataset being monitored.
        validation_rules: List of validation rules that failed.
        severity: Severity level of the quality issue.
    """

    quality_metric: str = Field(
        description="Type of quality metric to monitor (e.g., 'completeness', 'accuracy', 'consistency')."
    )
    threshold: Union[int, float] = Field(
        description="Quality threshold value to trigger on."
    )
    operator: Literal["gt", "gte", "lt", "lte", "eq", "ne"] = Field(
        default="lt",
        description="Comparison operator for threshold evaluation.",
    )
    source: str = Field(
        description="Data quality monitoring system (e.g., 'great-expectations', 'deequ', 'custom-validator').",
    )
    dataset_name: str = Field(
        description="Name of the dataset being monitored."
    )
    validation_rules: list[str] = Field(
        default_factory=list,
        description="List of validation rules that failed.",
    )
    severity: Literal["low", "medium", "high", "critical"] = Field(
        default="medium",
        description="Severity level of the quality issue.",
    )


class APIRateLimitEvent(BaseModel):
    """API rate limiting event trigger.

    Triggers workflows based on API rate limiting events from external APIs
    or internal API gateways to handle throttling and backoff strategies.

    Attributes:
        api_name: Name of the API being rate limited.
        rate_limit_type: Type of rate limit exceeded.
        current_usage: Current API usage percentage.
        reset_time: Time until rate limit resets (in seconds).
        source: API gateway or monitoring system.
        retry_strategy: Retry strategy to apply.
    """

    api_name: str = Field(description="Name of the API being rate limited.")
    rate_limit_type: Literal[
        "requests_per_minute",
        "requests_per_hour",
        "requests_per_day",
        "bandwidth",
    ] = Field(
        description="Type of rate limit exceeded.",
    )
    current_usage: float = Field(
        ge=0.0,
        le=100.0,
        description="Current API usage percentage.",
    )
    reset_time: int = Field(
        ge=0,
        description="Time until rate limit resets (in seconds).",
    )
    source: str = Field(
        description="API gateway or monitoring system (e.g., 'kong', 'aws-api-gateway', 'custom-monitor').",
    )
    retry_strategy: Literal[
        "exponential_backoff", "linear_backoff", "immediate_retry", "skip"
    ] = Field(
        default="exponential_backoff",
        description="Retry strategy to apply when rate limited.",
    )


class DataLineageEvent(BaseModel):
    """Data lineage tracking event trigger.

    Triggers workflows based on data lineage events to track data flow,
    dependencies, and impact analysis in data pipelines.

    Attributes:
        lineage_type: Type of lineage event.
        source_dataset: Source dataset name.
        target_dataset: Target dataset name.
        transformation_type: Type of transformation applied.
        source: Data lineage tracking system.
        impact_level: Impact level of the lineage change.
        dependencies: List of dependent datasets.
    """

    lineage_type: Literal[
        "data_flow", "schema_change", "dependency_update", "impact_analysis"
    ] = Field(
        description="Type of lineage event.",
    )
    source_dataset: str = Field(description="Source dataset name.")
    target_dataset: str = Field(description="Target dataset name.")
    transformation_type: str = Field(
        default="unknown",
        description="Type of transformation applied.",
    )
    source: str = Field(
        description="Data lineage tracking system (e.g., 'apache-atlas', 'datahub', 'custom-lineage').",
    )
    impact_level: Literal["low", "medium", "high", "critical"] = Field(
        default="medium",
        description="Impact level of the lineage change.",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="List of dependent datasets.",
    )


class MLPipelineEvent(BaseModel):
    """Machine learning pipeline event trigger.

    Triggers workflows based on ML pipeline events such as model training completion,
    model drift detection, or feature store updates.

    Attributes:
        pipeline_stage: Stage of the ML pipeline.
        model_name: Name of the ML model.
        metric_name: Performance metric being monitored.
        threshold: Threshold value for the metric.
        operator: Comparison operator for threshold evaluation.
        source: ML pipeline monitoring system.
        model_version: Version of the model.
        drift_detected: Whether model drift was detected.
    """

    pipeline_stage: Literal[
        "training", "validation", "deployment", "monitoring", "retraining"
    ] = Field(
        description="Stage of the ML pipeline.",
    )
    model_name: str = Field(description="Name of the ML model.")
    metric_name: str = Field(description="Performance metric being monitored.")
    threshold: Union[int, float] = Field(
        description="Threshold value for the metric."
    )
    operator: Literal["gt", "gte", "lt", "lte", "eq", "ne"] = Field(
        default="lt",
        description="Comparison operator for threshold evaluation.",
    )
    source: str = Field(
        description="ML pipeline monitoring system (e.g., 'mlflow', 'kubeflow', 'sagemaker', 'custom-ml-monitor').",
    )
    model_version: str = Field(description="Version of the model.")
    drift_detected: bool = Field(
        default=False,
        description="Whether model drift was detected.",
    )


class DataCatalogEvent(BaseModel):
    """Data catalog event trigger.

    Triggers workflows based on data catalog events such as metadata updates,
    data discovery, or governance policy changes.

    Attributes:
        catalog_event_type: Type of catalog event.
        dataset_name: Name of the dataset in the catalog.
        metadata_type: Type of metadata being updated.
        source: Data catalog system.
        governance_level: Governance level of the dataset.
        tags: List of tags associated with the dataset.
    """

    catalog_event_type: Literal[
        "metadata_update",
        "data_discovery",
        "governance_change",
        "access_request",
    ] = Field(
        description="Type of catalog event.",
    )
    dataset_name: str = Field(description="Name of the dataset in the catalog.")
    metadata_type: str = Field(
        default="general",
        description="Type of metadata being updated.",
    )
    source: str = Field(
        description="Data catalog system (e.g., 'apache-atlas', 'datahub', 'aws-glue-catalog', 'custom-catalog').",
    )
    governance_level: Literal[
        "public", "internal", "confidential", "restricted"
    ] = Field(
        default="internal",
        description="Governance level of the dataset.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="List of tags associated with the dataset.",
    )


class InfrastructureEvent(BaseModel):
    """Infrastructure event trigger.

    Triggers workflows based on infrastructure events such as scaling events,
    resource availability, or cost optimization triggers.

    Attributes:
        infrastructure_type: Type of infrastructure component.
        event_type: Type of infrastructure event.
        resource_name: Name of the resource.
        current_utilization: Current resource utilization percentage.
        threshold: Threshold value for the metric.
        source: Infrastructure monitoring system.
        scaling_action: Recommended scaling action.
    """

    infrastructure_type: Literal[
        "compute", "storage", "network", "database", "cache"
    ] = Field(
        description="Type of infrastructure component.",
    )
    event_type: Literal[
        "scaling", "maintenance", "failure", "cost_optimization"
    ] = Field(
        description="Type of infrastructure event.",
    )
    resource_name: str = Field(description="Name of the resource.")
    current_utilization: float = Field(
        ge=0.0,
        le=100.0,
        description="Current resource utilization percentage.",
    )
    threshold: Union[int, float] = Field(
        description="Threshold value for the metric."
    )
    source: str = Field(
        description="Infrastructure monitoring system (e.g., 'cloudwatch', 'datadog', 'prometheus', 'custom-monitor').",
    )
    scaling_action: Literal["scale_up", "scale_down", "maintain", "migrate"] = (
        Field(
            default="maintain",
            description="Recommended scaling action.",
        )
    )


class ComplianceEvent(BaseModel):
    """Compliance and regulatory event trigger.

    Triggers workflows based on compliance events such as audit requirements,
    regulatory changes, or data retention policies.

    Attributes:
        compliance_type: Type of compliance requirement.
        regulation_name: Name of the regulation or standard.
        audit_scope: Scope of the audit.
        source: Compliance monitoring system.
        deadline: Deadline for compliance action (in days).
        severity: Severity level of the compliance issue.
    """

    compliance_type: Literal[
        "audit", "regulatory_change", "data_retention", "privacy", "security"
    ] = Field(
        description="Type of compliance requirement.",
    )
    regulation_name: str = Field(
        description="Name of the regulation or standard."
    )
    audit_scope: str = Field(description="Scope of the audit.")
    source: str = Field(
        description="Compliance monitoring system (e.g., 'compliance-monitor', 'audit-system', 'regulatory-tracker').",
    )
    deadline: int = Field(
        ge=0,
        description="Deadline for compliance action (in days).",
    )
    severity: Literal["low", "medium", "high", "critical"] = Field(
        default="medium",
        description="Severity level of the compliance issue.",
    )


class BusinessEvent(BaseModel):
    """Business event trigger.

    Triggers workflows based on business events such as business hours,
    seasonal patterns, or business rule changes.

    Attributes:
        business_event_type: Type of business event.
        business_unit: Business unit affected.
        event_time: Time when the business event occurs.
        source: Business event system.
        priority: Priority level of the business event.
        business_rules: List of business rules affected.
    """

    business_event_type: Literal[
        "business_hours",
        "seasonal_pattern",
        "rule_change",
        "campaign",
        "holiday",
    ] = Field(
        description="Type of business event.",
    )
    business_unit: str = Field(description="Business unit affected.")
    event_time: str = Field(
        description="Time when the business event occurs (ISO format)."
    )
    source: str = Field(
        description="Business event system (e.g., 'business-calendar', 'campaign-manager', 'rule-engine').",
    )
    priority: Literal["low", "medium", "high", "urgent"] = Field(
        default="medium",
        description="Priority level of the business event.",
    )
    business_rules: list[str] = Field(
        default_factory=list,
        description="List of business rules affected.",
    )


Cron = Annotated[
    Union[
        CrontabYear,
        Crontab,
        CrontabValue,
    ],
    Field(
        union_mode="smart",
        description=(
            "Event model type supporting year-based, standard, and "
            "interval-based cron scheduling."
        ),
    ),
]  # pragma: no cov


class Event(BaseModel):
    """Event model with comprehensive trigger support.

    Supports multiple types of event triggers including cron scheduling,
    file monitoring, webhooks, database changes, sensor-based triggers,
    polling-based triggers, message queue events, stream processing events,
    batch processing events, data quality events, API rate limiting events,
    data lineage events, ML pipeline events, data catalog events,
    infrastructure events, compliance events, and business events.

    Attributes:
        schedule: List of cron-based schedules.
        release: List of workflow names for release-based triggering.
        file: List of file monitoring events from external services.
        webhook: List of webhook-based events from external systems.
        database: List of database change monitoring events from external services.
        sensor: List of sensor-based monitoring events from monitoring systems.
        polling: List of polling-based events for systems without event capabilities.
        message_queue: List of message queue-based events.
        stream_processing: List of stream processing events.
        batch_processing: List of batch processing events.
        data_quality: List of data quality monitoring events.
        api_rate_limit: List of API rate limiting events.
        data_lineage: List of data lineage tracking events.
        ml_pipeline: List of machine learning pipeline events.
        data_catalog: List of data catalog events.
        infrastructure: List of infrastructure events.
        compliance: List of compliance and regulatory events.
        business: List of business events.
    """

    schedule: list[Cron] = Field(
        default_factory=list,
        description="A list of Cron schedule.",
    )
    release: list[str] = Field(
        default_factory=list,
        description=(
            "A list of workflow name that want to receive event from release"
            "trigger."
        ),
    )
    file: list[FileEvent] = Field(
        default_factory=list,
        description="A list of file monitoring events from external services.",
    )
    webhook: list[WebhookEvent] = Field(
        default_factory=list,
        description="A list of webhook-based events from external systems.",
    )
    database: list[DatabaseEvent] = Field(
        default_factory=list,
        description="A list of database change monitoring events from external services.",
    )
    sensor: list[SensorEvent] = Field(
        default_factory=list,
        description="A list of sensor-based monitoring events from monitoring systems.",
    )
    polling: list[PollingEvent] = Field(
        default_factory=list,
        description="A list of polling-based events for systems without event capabilities.",
    )
    message_queue: list[MessageQueueEvent] = Field(
        default_factory=list,
        description="A list of message queue-based events.",
    )
    stream_processing: list[StreamProcessingEvent] = Field(
        default_factory=list,
        description="A list of stream processing events.",
    )
    batch_processing: list[BatchProcessingEvent] = Field(
        default_factory=list,
        description="A list of batch processing events.",
    )
    data_quality: list[DataQualityEvent] = Field(
        default_factory=list,
        description="A list of data quality monitoring events.",
    )
    api_rate_limit: list[APIRateLimitEvent] = Field(
        default_factory=list,
        description="A list of API rate limiting events.",
    )
    data_lineage: list[DataLineageEvent] = Field(
        default_factory=list,
        description="A list of data lineage tracking events.",
    )
    ml_pipeline: list[MLPipelineEvent] = Field(
        default_factory=list,
        description="A list of machine learning pipeline events.",
    )
    data_catalog: list[DataCatalogEvent] = Field(
        default_factory=list,
        description="A list of data catalog events.",
    )
    infrastructure: list[InfrastructureEvent] = Field(
        default_factory=list,
        description="A list of infrastructure events.",
    )
    compliance: list[ComplianceEvent] = Field(
        default_factory=list,
        description="A list of compliance and regulatory events.",
    )
    business: list[BusinessEvent] = Field(
        default_factory=list,
        description="A list of business events.",
    )

    @field_validator("schedule", mode="after")
    def __on_no_dup_and_reach_limit__(
        cls,
        value: list[Crontab],
    ) -> list[Crontab]:
        """Validate the on fields should not contain duplicate values and if it
        contains the every minute value more than one value, it will remove to
        only one value.

        Args:
            value: A list of on object.

        Returns:
            list[CronJobYear | Crontab]: The validated list of Crontab objects.

        Raises:
            ValueError: If it has some duplicate value.
        """
        set_ons: set[str] = {str(on.cronjob) for on in value}
        if len(set_ons) != len(value):
            raise ValueError(
                "The on fields should not contain duplicate on value."
            )

        # WARNING:
        # if '* * * * *' in set_ons and len(set_ons) > 1:
        #     raise ValueError(
        #         "If it has every minute cronjob on value, it should have "
        #         "only one value in the on field."
        #     )
        set_tz: set[str] = {on.tz for on in value}
        if len(set_tz) > 1:
            raise ValueError(
                f"The on fields should not contain multiple timezone, "
                f"{list(set_tz)}."
            )

        if len(set_ons) > 10:
            raise ValueError(
                "The number of the on should not more than 10 crontabs."
            )
        return value

    @field_validator("file", mode="after")
    def __validate_file_events__(
        cls, value: list[FileEvent]
    ) -> list[FileEvent]:
        """Validate file monitoring events.

        Args:
            value: List of file events to validate.

        Returns:
            list[FileEvent]: Validated list of file events.

        Raises:
            ValueError: If validation fails.
        """
        if len(value) > 20:
            raise ValueError("The number of file events should not exceed 20.")

        # Check for duplicate paths
        paths = [event.path for event in value]
        if len(paths) != len(set(paths)):
            raise ValueError("File events should not contain duplicate paths.")

        return value

    @field_validator("webhook", mode="after")
    def __validate_webhook_events__(
        cls, value: list[WebhookEvent]
    ) -> list[WebhookEvent]:
        """Validate webhook events.

        Args:
            value: List of webhook events to validate.

        Returns:
            list[WebhookEvent]: Validated list of webhook events.

        Raises:
            ValueError: If validation fails.
        """
        if len(value) > 10:
            raise ValueError(
                "The number of webhook events should not exceed 10."
            )

        # Check for duplicate endpoints
        endpoints = [event.endpoint for event in value]
        if len(endpoints) != len(set(endpoints)):
            raise ValueError(
                "Webhook events should not contain duplicate endpoints."
            )

        return value

    @field_validator("database", mode="after")
    def __validate_database_events__(
        cls, value: list[DatabaseEvent]
    ) -> list[DatabaseEvent]:
        """Validate database events.

        Args:
            value: List of database events to validate.

        Returns:
            list[DatabaseEvent]: Validated list of database events.

        Raises:
            ValueError: If validation fails.
        """
        if len(value) > 5:
            raise ValueError(
                "The number of database events should not exceed 5."
            )

        return value

    @field_validator("sensor", mode="after")
    def __validate_sensor_events__(
        cls, value: list[SensorEvent]
    ) -> list[SensorEvent]:
        """Validate sensor events.

        Args:
            value: List of sensor events to validate.

        Returns:
            list[SensorEvent]: Validated list of sensor events.

        Raises:
            ValueError: If validation fails.
        """
        if len(value) > 15:
            raise ValueError(
                "The number of sensor events should not exceed 15."
            )

        return value

    @field_validator("polling", mode="after")
    def __validate_polling_events__(
        cls, value: list[PollingEvent]
    ) -> list[PollingEvent]:
        """Validate polling events.

        Args:
            value: List of polling events to validate.

        Returns:
            list[PollingEvent]: Validated list of polling events.

        Raises:
            ValueError: If validation fails.
        """
        if len(value) > 8:
            raise ValueError(
                "The number of polling events should not exceed 8."
            )

        # Check for reasonable polling intervals
        for event in value:
            if event.check_interval_seconds < 10:
                raise ValueError(
                    f"Polling interval too short: {event.check_interval_seconds}s. "
                    "Minimum is 10 seconds."
                )

        return value

    @field_validator("message_queue", mode="after")
    def __validate_message_queue_events__(
        cls, value: list[MessageQueueEvent]
    ) -> list[MessageQueueEvent]:
        """Validate message queue events.

        Args:
            value: List of message queue events to validate.

        Returns:
            list[MessageQueueEvent]: Validated list of message queue events.

        Raises:
            ValueError: If validation fails.
        """
        if len(value) > 5:
            raise ValueError(
                "The number of message queue events should not exceed 5."
            )

        return value

    @field_validator("stream_processing", mode="after")
    def __validate_stream_processing_events__(
        cls, value: list[StreamProcessingEvent]
    ) -> list[StreamProcessingEvent]:
        """Validate stream processing events.

        Args:
            value: List of stream processing events to validate.

        Returns:
            list[StreamProcessingEvent]: Validated list of stream processing events.

        Raises:
            ValueError: If validation fails.
        """
        if len(value) > 3:
            raise ValueError(
                "The number of stream processing events should not exceed 3."
            )

        return value

    @field_validator("batch_processing", mode="after")
    def __validate_batch_processing_events__(
        cls, value: list[BatchProcessingEvent]
    ) -> list[BatchProcessingEvent]:
        """Validate batch processing events.

        Args:
            value: List of batch processing events to validate.

        Returns:
            list[BatchProcessingEvent]: Validated list of batch processing events.

        Raises:
            ValueError: If validation fails.
        """
        if len(value) > 5:
            raise ValueError(
                "The number of batch processing events should not exceed 5."
            )

        return value

    @field_validator("data_quality", mode="after")
    def __validate_data_quality_events__(
        cls, value: list[DataQualityEvent]
    ) -> list[DataQualityEvent]:
        """Validate data quality events.

        Args:
            value: List of data quality events to validate.

        Returns:
            list[DataQualityEvent]: Validated list of data quality events.

        Raises:
            ValueError: If validation fails.
        """
        if len(value) > 10:
            raise ValueError(
                "The number of data quality events should not exceed 10."
            )

        return value

    @field_validator("api_rate_limit", mode="after")
    def __validate_api_rate_limit_events__(
        cls, value: list[APIRateLimitEvent]
    ) -> list[APIRateLimitEvent]:
        """Validate API rate limit events.

        Args:
            value: List of API rate limit events to validate.

        Returns:
            list[APIRateLimitEvent]: Validated list of API rate limit events.

        Raises:
            ValueError: If validation fails.
        """
        if len(value) > 5:
            raise ValueError(
                "The number of API rate limit events should not exceed 5."
            )

        return value

    @field_validator("data_lineage", mode="after")
    def __validate_data_lineage_events__(
        cls, value: list[DataLineageEvent]
    ) -> list[DataLineageEvent]:
        """Validate data lineage events.

        Args:
            value: List of data lineage events to validate.

        Returns:
            list[DataLineageEvent]: Validated list of data lineage events.

        Raises:
            ValueError: If validation fails.
        """
        if len(value) > 8:
            raise ValueError(
                "The number of data lineage events should not exceed 8."
            )

        return value

    @field_validator("ml_pipeline", mode="after")
    def __validate_ml_pipeline_events__(
        cls, value: list[MLPipelineEvent]
    ) -> list[MLPipelineEvent]:
        """Validate ML pipeline events.

        Args:
            value: List of ML pipeline events to validate.

        Returns:
            list[MLPipelineEvent]: Validated list of ML pipeline events.

        Raises:
            ValueError: If validation fails.
        """
        if len(value) > 6:
            raise ValueError(
                "The number of ML pipeline events should not exceed 6."
            )

        return value

    @field_validator("data_catalog", mode="after")
    def __validate_data_catalog_events__(
        cls, value: list[DataCatalogEvent]
    ) -> list[DataCatalogEvent]:
        """Validate data catalog events.

        Args:
            value: List of data catalog events to validate.

        Returns:
            list[DataCatalogEvent]: Validated list of data catalog events.

        Raises:
            ValueError: If validation fails.
        """
        if len(value) > 5:
            raise ValueError(
                "The number of data catalog events should not exceed 5."
            )

        return value

    @field_validator("infrastructure", mode="after")
    def __validate_infrastructure_events__(
        cls, value: list[InfrastructureEvent]
    ) -> list[InfrastructureEvent]:
        """Validate infrastructure events.

        Args:
            value: List of infrastructure events to validate.

        Returns:
            list[InfrastructureEvent]: Validated list of infrastructure events.

        Raises:
            ValueError: If validation fails.
        """
        if len(value) > 8:
            raise ValueError(
                "The number of infrastructure events should not exceed 8."
            )

        return value

    @field_validator("compliance", mode="after")
    def __validate_compliance_events__(
        cls, value: list[ComplianceEvent]
    ) -> list[ComplianceEvent]:
        """Validate compliance events.

        Args:
            value: List of compliance events to validate.

        Returns:
            list[ComplianceEvent]: Validated list of compliance events.

        Raises:
            ValueError: If validation fails.
        """
        if len(value) > 5:
            raise ValueError(
                "The number of compliance events should not exceed 5."
            )

        return value

    @field_validator("business", mode="after")
    def __validate_business_events__(
        cls, value: list[BusinessEvent]
    ) -> list[BusinessEvent]:
        """Validate business events.

        Args:
            value: List of business events to validate.

        Returns:
            list[BusinessEvent]: Validated list of business events.

        Raises:
            ValueError: If validation fails.
        """
        if len(value) > 10:
            raise ValueError(
                "The number of business events should not exceed 10."
            )

        return value
