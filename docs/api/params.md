# Parameters

The Parameters module provides a comprehensive type system for workflow parameter definitions, validation, and processing. All parameter types inherit from a base `Param` type and support various data types with validation rules.

## Overview

The parameter system provides:

- **Type validation**: Strong typing with Pydantic validation
- **Default values**: Optional default values for parameters
- **Description support**: Human-readable parameter descriptions
- **Nested structures**: Support for complex data types
- **Template integration**: Seamless integration with workflow templating

## Base Parameter Type

The `Param` type is constructed as:

```text
Param = Annotated[
    Union[
        MapParam,
        ArrayParam,
        ChoiceParam,
        DatetimeParam,
        DateParam,
        IntParam,
        StrParam,
    ],
    Field(discriminator="type"),
]
```

## Parameter Types

### StrParam

String parameter type for text values.

!!! example "String Parameter"

    === "Basic String"

        ```yaml
        params:
            name:
                type: str
                description: "User's full name"
        ```

    === "String with Default"

        ```yaml
        params:
            environment:
                type: str
                default: "development"
                description: "Target environment"
        ```

    === "Required String"

        ```yaml
        params:
            api_key:
                type: str
                description: "API authentication key"
                required: true
        ```

#### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `type` | str | `"str"` | Parameter type identifier |
| `description` | str \| None | `None` | Human-readable description |
| `default` | str \| None | `None` | Default value if not provided |
| `required` | bool | `False` | Whether parameter is required |

### IntParam

Integer parameter type for numeric values.

!!! example "Integer Parameter"

    === "Basic Integer"

        ```yaml
        params:
            batch_size:
                type: int
                description: "Number of records to process"
        ```

    === "Integer with Default"

        ```yaml
        params:
            timeout:
                type: int
                default: 300
                description: "Operation timeout in seconds"
        ```

    === "Integer with Constraints"

        ```yaml
        params:
            port:
                type: int
                default: 8080
                description: "Server port number"
                ge: 1024
                le: 65535
        ```

#### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `type` | str | `"int"` | Parameter type identifier |
| `description` | str \| None | `None` | Human-readable description |
| `default` | int \| None | `None` | Default value if not provided |
| `ge` | int \| None | `None` | Greater than or equal constraint |
| `le` | int \| None | `None` | Less than or equal constraint |
| `gt` | int \| None | `None` | Greater than constraint |
| `lt` | int \| None | `None` | Less than constraint |

### DatetimeParam

Datetime parameter type for date and time values.

!!! example "Datetime Parameter"

    === "Basic Datetime"

        ```yaml
        params:
            start_time:
                type: datetime
                description: "Workflow start time"
        ```

    === "Datetime with Default"

        ```yaml
        params:
            scheduled_time:
                type: datetime
                default: "2024-01-01T00:00:00"
                description: "Scheduled execution time"
        ```

    === "Datetime with Format"

        ```yaml
        params:
            event_time:
                type: datetime
                description: "Event timestamp"
                format: "%Y-%m-%d %H:%M:%S"
        ```

#### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `type` | str | `"datetime"` | Parameter type identifier |
| `description` | str \| None | `None` | Human-readable description |
| `default` | str \| None | `None` | Default value in ISO format |
| `format` | str \| None | `None` | Custom datetime format string |

### DateParam

Date parameter type for date-only values.

!!! example "Date Parameter"

    === "Basic Date"

        ```yaml
        params:
            processing_date:
                type: date
                description: "Data processing date"
        ```

    === "Date with Default"

        ```yaml
        params:
            report_date:
                type: date
                default: "2024-01-01"
                description: "Report generation date"
        ```

#### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `type` | str | `"date"` | Parameter type identifier |
| `description` | str \| None | `None` | Human-readable description |
| `default` | str \| None | `None` | Default value in YYYY-MM-DD format |

### ChoiceParam

Choice parameter type for enumerated values.

!!! example "Choice Parameter"

    === "Basic Choice"

        ```yaml
        params:
            environment:
                type: choice
                choices: ["development", "staging", "production"]
                description: "Target environment"
        ```

    === "Choice with Default"

        ```yaml
        params:
            mode:
                type: choice
                choices: ["batch", "stream", "interactive"]
                default: "batch"
                description: "Processing mode"
        ```

#### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `type` | str | `"choice"` | Parameter type identifier |
| `description` | str \| None | `None` | Human-readable description |
| `choices` | list[str] | `[]` | Available choice options |
| `default` | str \| None | `None` | Default selected choice |

### MapParam

Map parameter type for key-value structures.

!!! example "Map Parameter"

    === "Basic Map"

        ```yaml
        params:
            config:
                type: map
                description: "Configuration settings"
        ```

    === "Map with Default"

        ```yaml
        params:
            headers:
                type: map
                default:
                    "Content-Type": "application/json"
                    "User-Agent": "Workflow/1.0"
                description: "HTTP request headers"
        ```

#### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `type` | str | `"map"` | Parameter type identifier |
| `description` | str \| None | `None` | Human-readable description |
| `default` | dict | `{}` | Default key-value pairs |

### ArrayParam

Array parameter type for list values.

!!! example "Array Parameter"

    === "Basic Array"

        ```yaml
        params:
            files:
                type: array
                description: "List of files to process"
        ```

    === "Array with Default"

        ```yaml
        params:
            regions:
                type: array
                default: ["us-east", "us-west"]
                description: "Target regions"
        ```

    === "Typed Array"

        ```yaml
        params:
            numbers:
                type: array
                items_type: int
                description: "List of numeric values"
        ```

#### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `type` | str | `"array"` | Parameter type identifier |
| `description` | str \| None | `None` | Human-readable description |
| `default` | list | `[]` | Default array values |
| `items_type` | str \| None | `None` | Type of array items |

## Usage Examples

### Workflow Parameter Definition

```yaml
workflow:
  type: Workflow
  params:
    # String parameters
    data_source:
      type: str
      description: "Source data location"
      required: true

    environment:
      type: str
      default: "development"
      description: "Target environment"

    # Numeric parameters
    batch_size:
      type: int
      default: 1000
      description: "Processing batch size"
      ge: 1
      le: 10000

    # Date/time parameters
    start_date:
      type: date
      description: "Processing start date"

    scheduled_time:
      type: datetime
      default: "2024-01-01T09:00:00"
      description: "Scheduled execution time"

    # Choice parameters
    mode:
      type: choice
      choices: ["full", "incremental", "test"]
      default: "incremental"
      description: "Processing mode"

    # Complex parameters
    config:
      type: map
      default:
        timeout: 300
        retries: 3
      description: "Processing configuration"

    file_list:
      type: array
      description: "Files to process"
```

### Parameter Validation

```python
from ddeutil.workflow.params import StrParam, IntParam, ChoiceParam

# String parameter with validation
name_param = StrParam(
    description="User name",
    required=True
)

# Integer parameter with constraints
age_param = IntParam(
    description="User age",
    default=18,
    ge=0,
    le=120
)

# Choice parameter
status_param = ChoiceParam(
    description="User status",
    choices=["active", "inactive", "pending"],
    default="pending"
)
```

### Template Integration

Parameters integrate seamlessly with workflow templating:

```yaml
stages:
  - name: "Process data for ${{ params.environment }}"
    run: |
      process_data(
          source="${{ params.data_source }}",
          batch_size=${{ params.batch_size }},
          mode="${{ params.mode }}"
      )

  - name: "Generate report"
    if: "${{ params.mode }} == 'full'"
    run: |
      generate_report(
          date="${{ params.start_date }}",
          config=${{ params.config }}
      )
```

## Best Practices

### 1. Parameter Naming

- Use descriptive, lowercase names with underscores
- Avoid reserved words and special characters
- Be consistent with naming conventions

### 2. Validation Rules

- Set appropriate constraints for numeric parameters
- Use choice parameters for enumerated values
- Provide meaningful default values when possible

### 3. Documentation

- Always include descriptions for parameters
- Use clear, concise language
- Provide examples for complex parameters

### 4. Type Safety

- Choose the most specific parameter type
- Use typed arrays when possible
- Leverage validation constraints

### 5. Default Values

- Provide sensible defaults for optional parameters
- Use environment-specific defaults
- Document the rationale for default choices
