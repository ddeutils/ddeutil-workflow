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

| Name                         | Component | Default                                                                                                                         | Description                                                                                                        |
|:-----------------------------|:---------:|:--------------------------------------------------------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------------------------------------|
| **REGISTRY_CALLER**          |   CORE    | `.`                                                                                                                             | List of importable string for the call stage.                                                                      |
| **REGISTRY_FILTER**          |   CORE    | `ddeutil.workflow.templates`                                                                                                    | List of importable string for the filter template.                                                                 |
| **CONF_PATH**                |   CORE    | `./conf`                                                                                                                        | The config path that keep all template `.yaml` files.                                                              |
| **TIMEZONE**                 |   CORE    | `Asia/Bangkok`                                                                                                                  | A Timezone string value that will pass to `ZoneInfo` object.                                                       |
| **STAGE_DEFAULT_ID**         |   CORE    | `false`                                                                                                                         | A flag that enable default stage ID that use for catch an execution output.                                        |
| **MAX_QUEUE_COMPLETE_HIST**  |   CORE    | `16`                                                                                                                            |                                                                                                                    |
| **GENERATE_ID_SIMPLE_MODE**  |   CORE    | `true`                                                                                                                          | A flog that enable generating ID with `md5` algorithm.                                                             |
| **DEBUG_MODE**               |    LOG    | `true`                                                                                                                          | A flag that enable logging with debug level mode.                                                                  |
| **FORMAT**                   |    LOG    | `%(asctime)s.%(msecs)03d (%(name)-10s, %(process)-5d,%(thread)-5d) [%(levelname)-7s] %(message)-120s (%(filename)s:%(lineno)s)` |                                                                                                                    |
| **FORMAT_FILE**              |    LOG    | `{datetime} ({process:5d}, {thread:5d}) {message:120s} ({filename}:{lineno})`                                                   |                                                                                                                    |
| **DATETIME_FORMAT**          |    LOG    | `%Y-%m-%d %H:%M:%S`                                                                                                             |                                                                                                                    |
| **TRACE_PATH**               |    LOG    | `./logs`                                                                                                                        | The log path of the workflow saving log.                                                                           |
| **TRACE_ENABLE_WRITE**       |    LOG    | `false`                                                                                                                         |                                                                                                                    |
| **AUDIT_PATH**               |    LOG    | `./audits`                                                                                                                      |                                                                                                                    |
| **AUDIT_ENABLE_WRITE**       |    LOG    | `true`                                                                                                                          | A flag that enable logging object saving log to its destination.                                                   |

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
