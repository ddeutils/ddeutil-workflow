# Reusables

The Reusables module contains template functions, filters, and decorators for workflow parameter templating and function registration.

## Overview

This module provides:

- **Template rendering**: Dynamic parameter substitution with `${{ }}` syntax
- **Filter functions**: Data transformation functions for template values
- **Function registration**: Decorator-based system for workflow callable functions
- **Argument parsing**: Utilities for parsing and validating function arguments

## Template Functions

### `str2template`

Converts a string with template syntax to its resolved value.

!!! example "Template Syntax"

    ```python
    from ddeutil.workflow.reusables import str2template

    params = {
        "name": "John",
        "date": datetime(2024, 1, 1)
    }

    # Basic templating
    result = str2template("Hello ${{ params.name }}", params)
    # Output: "Hello John"

    # With filters
    result = str2template("Date: ${{ params.date | fmt('%Y-%m-%d') }}", params)
    # Output: "Date: 2024-01-01"
    ```

### `param2template`

Recursively processes nested data structures for template resolution.

!!! example "Nested Templates"

    ```python
    from ddeutil.workflow.reusables import param2template

    params = {"env": "prod", "version": "1.0"}
    data = {
        "image": "app:${{ params.version }}",
        "config": {
            "environment": "${{ params.env }}"
        }
    }

    result = param2template(data, params)
    # Output: {"image": "app:1.0", "config": {"environment": "prod"}}
    ```

## Filter Functions

### Built-in Filters

| Filter | Description | Example |
|--------|-------------|---------|
| `abs` | Absolute value | `${{ -5 \| abs }}` → `5` |
| `str` | Convert to string | `${{ 123 \| str }}` → `"123"` |
| `int` | Convert to integer | `${{ "123" \| int }}` → `123` |
| `upper` | Uppercase string | `${{ "hello" \| upper }}` → `"HELLO"` |
| `lower` | Lowercase string | `${{ "HELLO" \| lower }}` → `"hello"` |
| `title` | Title case | `${{ "hello world" \| title }}` → `"Hello World"` |

### Custom Filters

#### `@custom_filter`

Decorator for creating custom filter functions.

!!! example "Custom Filter"

    ```python
    from ddeutil.workflow.reusables import custom_filter

    @custom_filter("multiply")
    def multiply_by(value: int, factor: int = 2) -> int:
        return value * factor

    # Usage in template: ${{ 5 | multiply(3) }}
    # Result: 15
    ```

#### Built-in Custom Filters

##### `fmt`

Formats datetime objects using strftime patterns.

!!! example "Date Formatting"

    ```python
    # Template: ${{ params.date | fmt('%Y-%m-%d') }}
    # Input: datetime(2024, 1, 15, 10, 30)
    # Output: "2024-01-15"
    ```

##### `coalesce`

Returns the first non-None value or a default.

!!! example "Coalesce"

    ```python
    # Template: ${{ params.optional_value | coalesce('default') }}
    # Input: None
    # Output: "default"
    ```

##### `getitem`

Gets item from dictionary with optional default.

!!! example "Get Item"

    ```python
    # Template: ${{ params.config | getitem('timeout', 30) }}
    # Input: {"host": "localhost"}
    # Output: 30
    ```

##### `getindex`

Gets item from list by index.

!!! example "Get Index"

    ```python
    # Template: ${{ params.servers | getindex(0) }}
    # Input: ["server1", "server2"]
    # Output: "server1"
    ```

## Function Registration

### `@tag`

Decorator for registering workflow callable functions.

!!! example "Function Registration"

    ```python
    from ddeutil.workflow import tag, Result

    @tag("database", alias="connect-postgres")
    def connect_to_postgres(
        host: str,
        port: int = 5432,
        database: str = "mydb",
        result: Result = None
    ) -> dict:
        # Database connection logic
        return {"status": "connected", "host": host}
    ```

    !!! info "Usage in YAML"

        ```yaml
        stages:
          - name: "Connect to Database"
            uses: database/connect_to_postgres@connect-postgres
            with:
              host: ${{ params.db_host }}
              database: ${{ params.db_name }}
        ```

### Registry Functions

#### `make_registry`

Creates a registry of tagged functions from specified modules.

!!! example "Registry Creation"

    ```python
    from ddeutil.workflow.reusables import make_registry

    # Load functions from tasks module
    registry = make_registry("tasks", registries=["my_project.tasks"])

    # Access registered function
    func = registry["my_function"]
    ```

#### `extract_call`

Extracts and validates function calls from workflow strings.

!!! example "Call Extraction"

    ```python
    from ddeutil.workflow.reusables import extract_call

    # From workflow: "tasks/process_data@etl"
    func = extract_call("tasks/process_data@etl")
    result = func()  # Execute the function
    ```

## Utility Functions

### `has_template`

Checks if a value contains template syntax.

!!! example "Template Detection"

    ```python
    from ddeutil.workflow.reusables import has_template

    has_template("Hello ${{ params.name }}")  # True
    has_template("Hello World")               # False
    ```

### `get_args_const`

Parses function call expressions to extract arguments.

!!! example "Argument Parsing"

    ```python
    from ddeutil.workflow.reusables import get_args_const

    name, args, kwargs = get_args_const("func(1, 2, key='value')")
    # name: "func"
    # args: [1, 2]
    # kwargs: {"key": "value"}
    ```

## Configuration

Reusables behavior can be configured through environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKFLOW_CORE_REGISTRY_FILTER` | `[]` | List of modules to search for filter functions |
| `WORKFLOW_CORE_REGISTRY_CALLER` | `[]` | List of modules to search for callable functions |

!!! tip "Performance"

    Filter and tag registries are cached at module level for optimal performance. Use `make_filter_registry()` and `make_registry()` to rebuild registries when needed.
