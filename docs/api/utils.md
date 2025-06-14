# Utilities

The Utils module provides essential utility functions for workflow operations including ID generation, datetime handling, data transformation, and cross-product operations.

## ID Generation

### `gen_id`

Generate running ID for tracking workflow executions. Uses MD5 algorithm or simple mode based on configuration.

!!! example "ID Generation"

    ```python
    from ddeutil.workflow.utils import gen_id

    # Simple hash-based ID
    id1 = gen_id("workflow-name")
    # Output: "a1b2c3d4e5"

    # Case-insensitive ID
    id2 = gen_id("WORKFLOW-NAME", sensitive=False)
    # Output: "a1b2c3d4e5" (same as lowercase)

    # Unique ID with timestamp
    id3 = gen_id("workflow-name", unique=True)
    # Output: "20240115103000123456Ta1b2c3d4e5"

    # Simple mode (configurable)
    id4 = gen_id("workflow-name", simple_mode=True)
    # Output: "20240115103000123456Ta1b2c3d4e5"
    ```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `value` | Any | Required | Value to generate ID from |
| `sensitive` | bool | `True` | Case-sensitive ID generation |
| `unique` | bool | `False` | Add timestamp for uniqueness |
| `simple_mode` | bool \| None | `None` | Use simple mode (from config) |
| `extras` | dict \| None | `None` | Override config values |

### `default_gen_id`

Generate a default running ID for manual executions.

!!! example "Default ID"

    ```python
    from ddeutil.workflow.utils import default_gen_id

    # Generate default ID with timestamp
    default_id = default_gen_id()
    # Output: "20240115103000123456Tmanual123abc"
    ```

### `cut_id`

Cut running ID to specified length for display purposes.

!!! example "ID Cutting"

    ```python
    from ddeutil.workflow.utils import cut_id

    # Full ID: "20240115103000123456T1354680202"
    short_id = cut_id("20240115103000123456T1354680202")
    # Output: "202401151030680202"

    # Custom length
    custom_id = cut_id("20240115103000123456T1354680202", num=8)
    # Output: "2024011580202"
    ```

## DateTime Utilities

### `get_dt_now`

Get current datetime with timezone and offset support.

!!! example "Current DateTime"

    ```python
    from ddeutil.workflow.utils import get_dt_now
    from zoneinfo import ZoneInfo

    # Current UTC time
    now_utc = get_dt_now()

    # Current time in specific timezone
    now_asia = get_dt_now(tz=ZoneInfo("Asia/Bangkok"))

    # Current time with offset
    now_offset = get_dt_now(offset=3600)  # +1 hour
    ```

### `get_d_now`

Get current date with timezone and offset support.

!!! example "Current Date"

    ```python
    from ddeutil.workflow.utils import get_d_now

    # Current date
    today = get_d_now()

    # Date with timezone
    today_tz = get_d_now(tz=ZoneInfo("America/New_York"))
    ```

### `replace_sec`

Replace seconds and microseconds in datetime to zero.

!!! example "Time Replacement"

    ```python
    from ddeutil.workflow.utils import replace_sec
    from datetime import datetime

    dt = datetime(2024, 1, 15, 10, 30, 45, 123456)
    clean_dt = replace_sec(dt)
    # Output: datetime(2024, 1, 15, 10, 30, 0, 0)
    ```

### `clear_tz`

Remove timezone information from datetime object.

!!! example "Timezone Removal"

    ```python
    from ddeutil.workflow.utils import clear_tz

    # Datetime with timezone
    dt_with_tz = datetime.now(tz=ZoneInfo("UTC"))
    dt_naive = clear_tz(dt_with_tz)
    # Output: datetime without timezone info
    ```

### `get_diff_sec`

Get difference in seconds between datetime and current time.

!!! example "Time Difference"

    ```python
    from ddeutil.workflow.utils import get_diff_sec
    from datetime import datetime, timedelta

    future_dt = datetime.now() + timedelta(minutes=5)
    diff = get_diff_sec(future_dt)
    # Output: 300 (seconds)
    ```

## Date/Time Checking

### `reach_next_minute`

Check if datetime is in the next minute relative to current time.

!!! example "Minute Check"

    ```python
    from ddeutil.workflow.utils import reach_next_minute
    from datetime import datetime, timedelta

    future_dt = datetime.now() + timedelta(minutes=2)
    is_next_minute = reach_next_minute(future_dt)
    # Output: True
    ```

### `wait_until_next_minute`

Wait with sleep until the next minute with optional offset.

!!! example "Wait Function"

    ```python
    from ddeutil.workflow.utils import wait_until_next_minute
    from datetime import datetime

    # Wait until next minute
    wait_until_next_minute(datetime.now())

    # Wait with 2 second offset
    wait_until_next_minute(datetime.now(), second=2)
    ```

### `delay`

Delay execution with random offset for load distribution.

!!! example "Random Delay"

    ```python
    from ddeutil.workflow.utils import delay

    # Delay 1 second + random 0.00-0.99 seconds
    delay(1.0)

    # Just random delay
    delay()  # 0.00-0.99 seconds
    ```

## Data Transformation

### `to_train`

Convert camelCase to train-case (kebab-case).

!!! example "Case Conversion"

    ```python
    from ddeutil.workflow.utils import to_train

    # Convert camelCase
    result = to_train("camelCaseString")
    # Output: "camel-case-string"

    # Convert PascalCase
    result = to_train("PascalCaseString")
    # Output: "pascal-case-string"
    ```

### `prepare_newline`

Prepare newline characters in strings for consistent formatting.

!!! example "Newline Preparation"

    ```python
    from ddeutil.workflow.utils import prepare_newline

    # Replace custom markers with newlines
    text = "Line 1||Line 2||Line 3"
    result = prepare_newline(text)
    # Output: "Line 1\nLine 2\nLine 3"
    ```

### `filter_func`

Filter out function objects from data structures, replacing with function names.

!!! example "Function Filtering"

    ```python
    from ddeutil.workflow.utils import filter_func

    def my_function():
        return "hello"

    data = {
        "name": "test",
        "func": my_function,
        "nested": {
            "callback": lambda x: x * 2
        }
    }

    filtered = filter_func(data)
    # Output: {
    #     "name": "test",
    #     "func": "my_function",
    #     "nested": {"callback": "<lambda>"}
    # }
    ```

### `dump_all`

Recursively dump all nested Pydantic models to dictionaries.

!!! example "Model Dumping"

    ```python
    from ddeutil.workflow.utils import dump_all
    from pydantic import BaseModel

    class User(BaseModel):
        name: str
        age: int

    class Team(BaseModel):
        name: str
        members: list[User]

    team = Team(
        name="Dev Team",
        members=[User(name="Alice", age=30), User(name="Bob", age=25)]
    )

    # Dump all nested models
    result = dump_all(team)
    # Output: Plain dict with all nested models converted
    ```

## Matrix Operations

### `cross_product`

Generate cross product of matrix values for parameter combinations.

!!! example "Cross Product"

    ```python
    from ddeutil.workflow.utils import cross_product

    matrix = {
        "env": ["dev", "prod"],
        "version": ["1.0", "2.0"],
        "region": ["us", "eu"]
    }

    # Generate all combinations
    for combination in cross_product(matrix):
        print(combination)

    # Output:
    # {"env": "dev", "version": "1.0", "region": "us"}
    # {"env": "dev", "version": "1.0", "region": "eu"}
    # {"env": "dev", "version": "2.0", "region": "us"}
    # {"env": "dev", "version": "2.0", "region": "eu"}
    # {"env": "prod", "version": "1.0", "region": "us"}
    # {"env": "prod", "version": "1.0", "region": "eu"}
    # {"env": "prod", "version": "2.0", "region": "us"}
    # {"env": "prod", "version": "2.0", "region": "eu"}
    ```

## File Operations

### `make_exec`

Make a file executable by changing its permissions.

!!! example "File Permissions"

    ```python
    from ddeutil.workflow.utils import make_exec
    from pathlib import Path

    # Make script executable
    script_path = Path("script.sh")
    make_exec(script_path)

    # Also works with string paths
    make_exec("/path/to/script.py")
    ```

## Object Utilities

### `obj_name`

Get the name of an object, class, or string.

!!! example "Object Names"

    ```python
    from ddeutil.workflow.utils import obj_name

    class MyClass:
        pass

    instance = MyClass()

    # Get class name from instance
    name1 = obj_name(instance)  # "MyClass"

    # Get class name from class
    name2 = obj_name(MyClass)   # "MyClass"

    # Return string as-is
    name3 = obj_name("CustomName")  # "CustomName"

    # Handle None
    name4 = obj_name(None)      # None
    ```

## Configuration

Utility functions can be configured through environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKFLOW_CORE_WORKFLOW_ID_SIMPLE_MODE` | `false` | Enable simple ID generation mode |
| `WORKFLOW_CORE_TZ` | `UTC` | Default timezone for datetime operations |

!!! tip "Performance Notes"

    - ID generation functions are optimized for high-frequency use
    - DateTime utilities handle timezone conversions efficiently
    - Cross product operations use generators for memory efficiency
    - Function filtering preserves object structure while removing callables
