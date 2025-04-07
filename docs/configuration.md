# Configuration

!!! important

    The config value that you will set on the environment should combine with
    prefix, component, and name which is `WORKFLOW_{component}_{name}` (With upper
    case).

## Core

The main configuration that use to dynamic changing with your objective of this
application. If any configuration values do not set yet, it will use default value
and do not raise any error to you.

| Name                         | Component | Default                                                                                                                         | Override | Description                                                                                                        |
|:-----------------------------|:---------:|:--------------------------------------------------------------------------------------------------------------------------------|:--------:|:-------------------------------------------------------------------------------------------------------------------|
| **ROOT_PATH**                |   Core    | `.`                                                                                                                             |    No    | The root path of the workflow application.                                                                         |
| **REGISTRY_CALLER**          |   Core    | `.`                                                                                                                             |   Yes    | List of importable string for the call stage.                                                                      |
| **REGISTRY_FILTER**          |   Core    | `ddeutil.workflow.templates`                                                                                                    |   Yes    | List of importable string for the filter template.                                                                 |
| **CONF_PATH**                |   Core    | `conf`                                                                                                                          |   Yes    | The config path that keep all template `.yaml` files.                                                              |
| **TIMEZONE**                 |   Core    | `Asia/Bangkok`                                                                                                                  |    No    | A Timezone string value that will pass to `ZoneInfo` object.                                                       |
| **STAGE_DEFAULT_ID**         |   Core    | `true`                                                                                                                          |   Yes    | A flag that enable default stage ID that use for catch an execution output.                                        |
| **STAGE_RAISE_ERROR**        |   Core    | `false`                                                                                                                         |   Yes    | A flag that all stage raise StageException from stage execution.                                                   |
| **JOB_DEFAULT_ID**           |   Core    | `false`                                                                                                                         |   Yes    | A flag that enable default job ID that use for catch an execution output. The ID that use will be sequence number. |
| **JOB_RAISE_ERROR**          |   Core    | `true`                                                                                                                          |   Yes    | A flag that all job raise JobException from job strategy execution.                                                |
| **MAX_CRON_PER_WORKFLOW**    |   Core    | `5`                                                                                                                             |    No    |                                                                                                                    |
| **MAX_QUEUE_COMPLETE_HIST**  |   Core    | `16`                                                                                                                            |    No    |                                                                                                                    |
| **GENERATE_ID_SIMPLE_MODE**  |   Core    | `true`                                                                                                                          |    No    | A flog that enable generating ID with `md5` algorithm.                                                             |
| **DEBUG_MODE**               |    Log    | `true`                                                                                                                          |    No    | A flag that enable logging with debug level mode.                                                                  |
| **FORMAT**                   |    Log    | `%(asctime)s.%(msecs)03d (%(name)-10s, %(process)-5d,%(thread)-5d) [%(levelname)-7s] %(message)-120s (%(filename)s:%(lineno)s)` |    No    |                                                                                                                    |
| **FORMAT_FILE**              |    Log    | `{datetime} ({process:5d}, {thread:5d}) {message:120s} ({filename}:{lineno})`                                                   |    No    |                                                                                                                    |
| **DATETIME_FORMAT**          |    Log    | `%Y-%m-%d %H:%M:%S`                                                                                                             |    No    |                                                                                                                    |
| **TRACE_PATH**               |    Log    | `./logs`                                                                                                                        |    No    | The log path of the workflow saving log.                                                                           |
| **TRACE_ENABLE_WRITE**       |    Log    | `false`                                                                                                                         |    No    |                                                                                                                    |
| **AUDIT_PATH**               |    Log    | `./audits`                                                                                                                      |    No    |                                                                                                                    |
| **AUDIT_ENABLE_WRITE**       |    Log    | `true`                                                                                                                          |    No    | A flag that enable logging object saving log to its destination.                                                   |
| **MAX_PROCESS**              |    App    | `2`                                                                                                                             |    No    | The maximum process worker number that run in scheduler app module.                                                |
| **MAX_SCHEDULE_PER_PROCESS** |    App    | `100`                                                                                                                           |    No    | A schedule per process that run parallel.                                                                          |
| **STOP_BOUNDARY_DELTA**      |    App    | `'{"minutes": 5, "seconds": 20}'`                                                                                               |    No    | A time delta value that use to stop scheduler app in json string format.                                           |

## API

| Environment                |  Component  | Default | <div style="width:25em">Description</div>                                          |
|:---------------------------|:-----------:|---------|------------------------------------------------------------------------------------|
| **ENABLE_ROUTE_WORKFLOW**  |     API     | `true`  | A flag that enable workflow route to manage execute manually and workflow logging. |
| **ENABLE_ROUTE_SCHEDULE**  |     API     | `true`  | A flag that enable run scheduler.                                                  |

## Override

Some config can override by an extra parameters.

```python
from pathlib import Path
from ddeutil.workflow import Workflow

workflow = Workflow.from_conf(
    "wf-tester", extras={"conf_path": Path("."), "job_default_id": True}
)
```
