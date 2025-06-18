# Configuration

!!! important

    The config value that you will set on the environment should combine with
    prefix, component, and name which is `WORKFLOW_{component}_{name}` with upper
    case.

## Environment Variable

### Core

The main configuration that use to dynamic changing with your objective of this
application. If any configuration values do not set yet, it will use default value
and do not raise any error to you.

| Name                        | Component | Default                                                                                                                         | Description                                                                            |
|:----------------------------|:---------:|:--------------------------------------------------------------------------------------------------------------------------------|:---------------------------------------------------------------------------------------|
| **REGISTRY_CALLER**         |   CORE    | `.`                                                                                                                             | List of importable string for the call stage.                                          |
| **REGISTRY_FILTER**         |   CORE    | `ddeutil.workflow.templates`                                                                                                    | List of importable string for the filter template.                                     |
| **CONF_PATH**               |   CORE    | `./conf`                                                                                                                        | The config path that keep all template `.yaml` files.                                  |
| **STAGE_DEFAULT_ID**        |   CORE    | `false`                                                                                                                         | A flag that enable default stage ID that use for catch an execution output.            |
| **GENERATE_ID_SIMPLE_MODE** |   CORE    | `true`                                                                                                                          | A flog that enable generating ID with `md5` algorithm.                                 |
| **DEBUG_MODE**              |    LOG    | `true`                                                                                                                          | A flag that enable logging with debug level mode.                                      |
| **TIMEZONE**                |    LOG    | `Asia/Bangkok`                                                                                                                  | A Timezone string value that will pass to `ZoneInfo` object.                           |
| **FORMAT**                  |    LOG    | `%(asctime)s.%(msecs)03d (%(name)-10s, %(process)-5d,%(thread)-5d) [%(levelname)-7s] %(message)-120s (%(filename)s:%(lineno)s)` | A trace message console format.                                                        |
| **FORMAT_FILE**             |    LOG    | `{datetime} ({process:5d}, {thread:5d}) {message:120s} ({filename}:{lineno})`                                                   | A trace message format that use to write to target pointer.                            |
| **DATETIME_FORMAT**         |    LOG    | `%Y-%m-%d %H:%M:%S`                                                                                                             | A datetime format of the trace log.                                                    |
| **TRACE_URL**               |    LOG    | `file:./logs`                                                                                                                   | A pointer URL of trace log that use to emit log message.                               |
| **TRACE_ENABLE_WRITE**      |    LOG    | `false`                                                                                                                         | A flag that enable writing trace log.                                                  |
| **AUDIT_URL**               |    LOG    | `file:./audits`                                                                                                                 | A pointer URL of audit log that use to write audit metrix.                             |
| **AUDIT_ENABLE_WRITE**      |    LOG    | `true`                                                                                                                          | A flag that enable writing audit log after end execution in the workflow release step. |

## Execution Override

Some config can override by an extra parameters. For the below example, I override
the `conf_path` and `stage_default_id` config values at the execution time from
`WORKFLOW_CORE_CONF_PATH` and `WORKFLOW_CORE_STAGE_DEFAULT_ID` environment variables.

That is mean, it does not impact to running workflow that do not override and use
the current environment config values.

```python
from pathlib import Path
from ddeutil.workflow import Workflow

workflow = Workflow.from_conf(
    "wf-tester",
    extras={
        "conf_path": Path("./new-path/conf"),
        "stage_default_id": True,
    }
)
```
