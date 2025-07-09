# Event API Reference

The Event module provides cron-based scheduling and event-driven triggers for workflow orchestration, enabling time-based execution and release-based triggering.

## Overview

The Event module implements a cron-based scheduling system that provides:

- **Cron scheduling**: Traditional cron expressions for time-based triggers
- **Interval scheduling**: Simple interval-based scheduling (daily, weekly, monthly)
- **Year-aware scheduling**: Extended cron with year support for tools like AWS Glue
- **Release events**: Workflow-to-workflow triggering based on completion events
- **Timezone support**: Full timezone handling for global deployments
- **Validation**: Comprehensive validation of cron expressions and schedules

## Quick Start

```python
from ddeutil.workflow.event import Crontab, CrontabValue, Event
from datetime import datetime

# Create a daily schedule at 9:30 AM
daily_schedule = CrontabValue(
    interval="daily",
    time="09:30",
    timezone="America/New_York"
)

# Create a traditional cron schedule
cron_schedule = Crontab(
    cronjob="0 9 * * 1-5",  # 9 AM on weekdays
    timezone="UTC"
)

# Create an event with multiple schedules
event = Event(
    schedule=[daily_schedule, cron_schedule],
    release=["upstream-workflow"]
)

# Generate next execution time
runner = cron_schedule.generate(datetime.now())
next_run = runner.next
print(f"Next execution: {next_run}")
```

## Classes

### BaseCrontab

Base class for crontab-based scheduling models.

#### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `extras` | `DictData` | `{}` | Additional parameters to pass to the CronJob field |
| `tz` | `TimeZoneName` | `"UTC"` | Timezone string value (alias: timezone) |

### CrontabValue

Crontab model using interval-based specification for simplified scheduling.

#### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `interval` | `Interval` | - | Scheduling interval string ('daily', 'weekly', 'monthly') |
| `day` | `str` | `None` | Day specification for weekly/monthly schedules |
| `time` | `str` | `"00:00"` | Time of day in 'HH:MM' format |
| `tz` | `TimeZoneName` | `"UTC"` | Timezone string value |

#### Methods

##### `cronjob` (property)

Get CronJob object built from interval format.

**Returns:**
- `CronJob`: CronJob instance configured with interval-based schedule

##### `generate(start)`

Generate CronRunner from initial datetime.

**Parameters:**
- `start` (Union[str, datetime]): Starting datetime for schedule generation

**Returns:**
- `CronRunner`: CronRunner instance for schedule generation

##### `next(start)`

Get next scheduled datetime after given start time.

**Parameters:**
- `start` (Union[str, datetime]): Starting datetime for schedule generation

**Returns:**
- `CronRunner`: CronRunner instance positioned at next scheduled time

### Crontab

Cron event model wrapping CronJob functionality for traditional cron expressions.

#### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `cronjob` | `CronJob` | - | CronJob instance for schedule validation and generation |
| `tz` | `TimeZoneName` | `"UTC"` | Timezone string value |

#### Methods

##### `generate(start)`

Generate schedule runner from start time.

**Parameters:**
- `start` (Union[str, datetime]): Starting datetime for schedule generation

**Returns:**
- `CronRunner`: CronRunner instance for schedule generation

##### `next(start)`

Get runner positioned at next scheduled time.

**Parameters:**
- `start` (Union[str, datetime]): Starting datetime for schedule generation

**Returns:**
- `CronRunner`: CronRunner instance positioned at next scheduled time

### CrontabYear

Cron event model with enhanced year-based scheduling, particularly useful for tools like AWS Glue.

#### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `cronjob` | `CronJobYear` | - | CronJobYear instance for year-aware schedule validation |
| `tz` | `TimeZoneName` | `"UTC"` | Timezone string value |

### Event

Event model for defining workflow triggers combining scheduled and release-based events.

#### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `schedule` | `list[Cron]` | `[]` | List of cron schedules for time-based triggers |
| `release` | `list[str]` | `[]` | List of workflow names for release-based triggers |

## Functions

### interval2crontab(interval, *, day=None, time="00:00")

Convert interval specification to cron expression.

**Parameters:**
- `interval` (Interval): Scheduling interval ('daily', 'weekly', or 'monthly')
- `day` (str, optional): Day of week for weekly intervals or monthly schedules
- `time` (str): Time of day in 'HH:MM' format

**Returns:**
- `str`: Generated crontab expression string

## Usage Examples

### Basic Cron Scheduling

```python
from ddeutil.workflow.event import Crontab
from datetime import datetime

# Create a cron schedule for every weekday at 9 AM
schedule = Crontab(
    cronjob="0 9 * * 1-5",
    timezone="America/New_York"
)

# Generate next execution times
runner = schedule.generate(datetime.now())
print(f"Next execution: {runner.next}")
print(f"Following execution: {runner.next}")
```

### Interval-Based Scheduling

```python
from ddeutil.workflow.event import CrontabValue

# Daily schedule at 2:30 PM
daily_schedule = CrontabValue(
    interval="daily",
    time="14:30",
    timezone="UTC"
)

# Weekly schedule on Friday at 6 PM
weekly_schedule = CrontabValue(
    interval="weekly",
    day="friday",
    time="18:00",
    timezone="Europe/London"
)

# Monthly schedule on the 1st at midnight
monthly_schedule = CrontabValue(
    interval="monthly",
    time="00:00",
    timezone="Asia/Tokyo"
)

# Generate next execution
runner = weekly_schedule.generate(datetime.now())
next_run = runner.next
print(f"Next Friday 6 PM: {next_run}")
```

### Year-Aware Scheduling

```python
from ddeutil.workflow.event import CrontabYear

# AWS Glue compatible schedule with year
glue_schedule = CrontabYear(
    cronjob="0 12 1 * ? 2024",  # First day of every month at noon in 2024
    timezone="UTC"
)

# Generate schedule for specific year
runner = glue_schedule.generate(datetime(2024, 1, 1))
executions = []
for _ in range(12):  # Get all monthly executions
    executions.append(runner.next)

print("Monthly executions in 2024:")
for execution in executions:
    print(f"  {execution}")
```

### Complex Event Configuration

```python
from ddeutil.workflow.event import Event, Crontab, CrontabValue

# Create multiple schedules
morning_schedule = CrontabValue(
    interval="daily",
    time="09:00",
    timezone="UTC"
)

evening_schedule = Crontab(
    cronjob="0 18 * * 1-5",  # 6 PM on weekdays
    timezone="UTC"
)

weekend_schedule = CrontabValue(
    interval="weekly",
    day="saturday",
    time="10:00",
    timezone="UTC"
)

# Create event with multiple triggers
event = Event(
    schedule=[morning_schedule, evening_schedule, weekend_schedule],
    release=["data-ingestion-workflow", "validation-workflow"]
)

# This workflow will trigger:
# 1. Daily at 9 AM
# 2. Weekdays at 6 PM
# 3. Saturdays at 10 AM
# 4. When data-ingestion-workflow completes
# 5. When validation-workflow completes
```

### Timezone Handling

```python
from ddeutil.workflow.event import Crontab
from datetime import datetime

# Create schedules in different timezones
ny_schedule = Crontab(
    cronjob="0 9 * * *",  # 9 AM Eastern
    timezone="America/New_York"
)

london_schedule = Crontab(
    cronjob="0 9 * * *",  # 9 AM GMT
    timezone="Europe/London"
)

tokyo_schedule = Crontab(
    cronjob="0 9 * * *",  # 9 AM JST
    timezone="Asia/Tokyo"
)

# Generate next execution times
now = datetime.now()
schedules = [
    ("New York", ny_schedule),
    ("London", london_schedule),
    ("Tokyo", tokyo_schedule)
]

for name, schedule in schedules:
    runner = schedule.generate(now)
    next_run = runner.next
    print(f"{name}: {next_run}")
```

### Interval Conversion

```python
from ddeutil.workflow.event import interval2crontab

# Convert various intervals to cron expressions
examples = [
    ("daily", None, "01:30"),
    ("weekly", "friday", "18:30"),
    ("monthly", None, "00:00"),
    ("monthly", "tuesday", "12:00"),
]

for interval, day, time in examples:
    cron_expr = interval2crontab(interval, day=day, time=time)
    print(f"{interval} {day or ''} at {time}: {cron_expr}")

# Output:
# daily  at 01:30: 1 30 * * *
# weekly friday at 18:30: 18 30 * * 5
# monthly  at 00:00: 0 0 1 * *
# monthly tuesday at 12:00: 12 0 1 * 2
```

### Release-Based Triggering

```python
from ddeutil.workflow.event import Event

# Create event that triggers on workflow completion
downstream_event = Event(
    release=[
        "etl-pipeline",
        "data-validation",
        "quality-check"
    ]
)

# This event will trigger when any of the specified workflows complete
# Useful for creating dependent workflow chains
```

### Advanced Scheduling Patterns

```python
from ddeutil.workflow.event import Crontab, CrontabValue, Event

# Business hours schedule (9 AM - 5 PM, weekdays)
business_hours_schedules = [
    Crontab(cronjob=f"0 {hour} * * 1-5", timezone="UTC")
    for hour in range(9, 18)
]

# Quarter-end schedule (last day of quarter)
quarter_end_schedule = Crontab(
    cronjob="0 23 31 3,6,9,12 *",  # Last day of quarters at 11 PM
    timezone="UTC"
)

# Monthly reporting schedule (first Monday of each month)
monthly_reporting = Crontab(
    cronjob="0 8 1-7 * 1",  # 8 AM on first Monday
    timezone="UTC"
)

# Combine all schedules
comprehensive_event = Event(
    schedule=business_hours_schedules + [
        quarter_end_schedule,
        monthly_reporting
    ],
    release=["upstream-data-pipeline"]
)
```

### Schedule Validation and Debugging

```python
from ddeutil.workflow.event import Crontab, CrontabValue
from datetime import datetime, timedelta

def validate_schedule(schedule, hours_ahead=24):
    """Validate and debug schedule generation."""
    now = datetime.now()
    future = now + timedelta(hours=hours_ahead)

    print(f"Schedule: {schedule}")
    print(f"Timezone: {schedule.tz}")

    runner = schedule.generate(now)
    executions = []

    current = runner.next
    while current <= future:
        executions.append(current)
        current = runner.next

    print(f"Next {len(executions)} executions:")
    for i, execution in enumerate(executions):
        print(f"  {i+1}. {execution}")

    return executions

# Test different schedules
schedules = [
    Crontab(cronjob="0 */4 * * *", timezone="UTC"),  # Every 4 hours
    CrontabValue(interval="daily", time="12:00", timezone="UTC"),
    Crontab(cronjob="0 9 * * 1-5", timezone="America/New_York"),
]

for schedule in schedules:
    validate_schedule(schedule)
    print("-" * 50)
```

## Best Practices

### 1. Schedule Design

- **Clear expressions**: Use readable cron expressions or interval formats
- **Timezone awareness**: Always specify appropriate timezones
- **Validation**: Test schedule generation before deployment
- **Documentation**: Document complex cron expressions

### 2. Performance Considerations

- **Limit schedules**: Keep the number of schedules per event reasonable (≤10)
- **Efficient expressions**: Use efficient cron expressions to minimize CPU usage
- **Timezone caching**: Timezone objects are cached for performance
- **Memory usage**: Large numbers of schedules can impact memory

### 3. Error Handling

- **Invalid expressions**: Handle cron expression validation errors
- **Timezone errors**: Validate timezone strings
- **Schedule conflicts**: Avoid overlapping schedules that might cause issues
- **Resource limits**: Monitor resource usage with frequent schedules

### 4. Debugging

- **Schedule testing**: Test schedules with different start times
- **Timezone verification**: Verify timezone behavior with daylight saving time
- **Expression validation**: Validate cron expressions before deployment
- **Execution tracking**: Monitor actual execution times vs. scheduled times
- **Use logging**: Enable debug logging for schedule processing

## Validation Rules

### Schedule Validation

The Event model enforces several validation rules:

1. **No duplicate schedules**: Each cron expression must be unique
2. **Timezone consistency**: All schedules in an event must use the same timezone
3. **Schedule limit**: Maximum of 10 schedules per event
4. **Valid expressions**: All cron expressions must be syntactically valid

### Interval Validation

- **Time format**: Time must be in 'HH:MM' format
- **Day validation**: Day names must be valid (Monday, Tuesday, etc.)
- **Interval types**: Only 'daily', 'weekly', 'monthly' are supported

## Configuration Reference

### Supported Cron Formats

| Format | Example | Description |
|--------|---------|-------------|
| Standard | `0 9 * * 1-5` | Minute Hour Day Month DayOfWeek |
| Year-aware | `0 9 * * ? 2024` | Minute Hour Day Month DayOfWeek Year |

### Timezone Support

The module uses `TimeZoneName` validation from `pydantic_extra_types`, supporting:
- IANA timezone names (e.g., 'America/New_York')
- UTC and GMT
- Common timezone abbreviations

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKFLOW_EVENT_DEFAULT_TIMEZONE` | `UTC` | Default timezone for schedules |
| `WORKFLOW_EVENT_MAX_SCHEDULES` | `10` | Maximum schedules per event |

## Common Patterns

### Data Pipeline Scheduling

```python
# ETL pipeline with multiple triggers
etl_event = Event(
    schedule=[
        CrontabValue(interval="daily", time="02:00", timezone="UTC"),  # Daily at 2 AM
        Crontab(cronjob="0 */6 * * *", timezone="UTC"),  # Every 6 hours
    ],
    release=["data-source-updated"]
)
```

### Reporting Schedules

```python
# Business reporting schedule
reporting_event = Event(
    schedule=[
        CrontabValue(interval="weekly", day="monday", time="08:00"),  # Weekly reports
        Crontab(cronjob="0 9 1 * *", timezone="UTC"),  # Monthly reports
        Crontab(cronjob="0 10 1 1,4,7,10 *", timezone="UTC"),  # Quarterly reports
    ]
)
```

### Maintenance Windows

```python
# Maintenance and cleanup schedules
maintenance_event = Event(
    schedule=[
        Crontab(cronjob="0 3 * * 0", timezone="UTC"),  # Weekly maintenance (Sunday 3 AM)
        Crontab(cronjob="0 2 1 * *", timezone="UTC"),  # Monthly cleanup
    ]
)
```

## Troubleshooting

### Common Issues

#### Invalid Cron Expression

```python
# Problem: Invalid cron expression
try:
    schedule = Crontab(cronjob="invalid expression")
except ValueError as e:
    print(f"Invalid cron expression: {e}")

# Solution: Use valid cron format
schedule = Crontab(cronjob="0 9 * * 1-5")  # 9 AM weekdays
```

#### Timezone Issues

```python
# Problem: Incorrect timezone
try:
    schedule = Crontab(cronjob="0 9 * * *", timezone="Invalid/Timezone")
except ValueError as e:
    print(f"Invalid timezone: {e}")

# Solution: Use valid IANA timezone
schedule = Crontab(cronjob="0 9 * * *", timezone="America/New_York")
```

#### Schedule Conflicts

```python
# Problem: Duplicate schedules
try:
    event = Event(schedule=[
        Crontab(cronjob="0 9 * * *"),
        Crontab(cronjob="0 9 * * *"),  # Duplicate
    ])
except ValueError as e:
    print(f"Duplicate schedule: {e}")

# Solution: Use unique schedules
event = Event(schedule=[
    Crontab(cronjob="0 9 * * *"),
    Crontab(cronjob="0 18 * * *"),  # Different time
])
```

### Debugging Tips

1. **Test expressions**: Use online cron expression testers
2. **Validate timezones**: Verify timezone strings with `zoneinfo`
3. **Check generation**: Test schedule generation with different start times
4. **Monitor execution**: Track actual vs. scheduled execution times
5. **Use logging**: Enable debug logging for schedule processing
