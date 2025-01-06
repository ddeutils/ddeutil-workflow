# Configuration

## Package Config

The main configuration that use to dynamic changing with your propose of this
application. If any configuration values do not set yet, it will use default value
and do not raise any error to you.

| Environment                             | Component  | Default                                            | Description                                                                                                        | Remark |
|:----------------------------------------|:----------:|:---------------------------------------------------|:-------------------------------------------------------------------------------------------------------------------|--------|
| `WORKFLOW_ROOT_PATH`                    |    Core    | .                                                  | The root path of the workflow application.                                                                         |        |
| `WORKFLOW_CORE_REGISTRY`                |    Core    | src,src.ddeutil.workflow,tests,tests.utils         | List of importable string for the hook stage.                                                                      |        |
| `WORKFLOW_CORE_REGISTRY_FILTER`         |    Core    | src.ddeutil.workflow.utils,ddeutil.workflow.utils  | List of importable string for the filter template.                                                                 |        |
| `WORKFLOW_CORE_PATH_CONF`               |    Core    | conf                                               | The config path that keep all template `.yaml` files.                                                              |        |
| `WORKFLOW_CORE_TIMEZONE`                |    Core    | Asia/Bangkok                                       | A Timezone string value that will pass to `ZoneInfo` object.                                                       |        |
| `WORKFLOW_CORE_STAGE_DEFAULT_ID`        |    Core    | true                                               | A flag that enable default stage ID that use for catch an execution output.                                        |        |
| `WORKFLOW_CORE_STAGE_RAISE_ERROR`       |    Core    | false                                              | A flag that all stage raise StageException from stage execution.                                                   |        |
| `WORKFLOW_CORE_JOB_DEFAULT_ID`          |    Core    | false                                              | A flag that enable default job ID that use for catch an execution output. The ID that use will be sequence number. |        |
| `WORKFLOW_CORE_JOB_RAISE_ERROR`         |    Core    | true                                               | A flag that all job raise JobException from job strategy execution.                                                |        |
| `WORKFLOW_CORE_MAX_NUM_POKING`          |    Core    | 4                                                  | .                                                                                                                  |        |
| `WORKFLOW_CORE_MAX_JOB_PARALLEL`        |    Core    | 2                                                  | The maximum job number that able to run parallel in workflow executor.                                             |        |
| `WORKFLOW_CORE_MAX_JOB_EXEC_TIMEOUT`    |    Core    | 600                                                |                                                                                                                    |        |
| `WORKFLOW_CORE_MAX_CRON_PER_WORKFLOW`   |    Core    | 5                                                  |                                                                                                                    |        |
| `WORKFLOW_CORE_MAX_QUEUE_COMPLETE_HIST` |    Core    | 16                                                 |                                                                                                                    |        |
| `WORKFLOW_CORE_GENERATE_ID_SIMPLE_MODE` |    Core    | true                                               | A flog that enable generating ID with `md5` algorithm.                                                             |        |
| `WORKFLOW_LOG_DEBUG_MODE`               |    Log     | true                                               | A flag that enable logging with debug level mode.                                                                  |        |
| `WORKFLOW_LOG_ENABLE_WRITE`             |    Log     | true                                               | A flag that enable logging object saving log to its destination.                                                   |        |
| `WORKFLOW_APP_MAX_PROCESS`              |  Schedule  | 2                                                  | The maximum process worker number that run in scheduler app module.                                                |        |
| `WORKFLOW_APP_MAX_SCHEDULE_PER_PROCESS` |  Schedule  | 100                                                | A schedule per process that run parallel.                                                                          |        |
| `WORKFLOW_APP_STOP_BOUNDARY_DELTA`      |  Schedule  | '{"minutes": 5, "seconds": 20}'                    | A time delta value that use to stop scheduler app in json string format.                                           |        |

**API Application**:

| Environment                           |  Component  | Default | Description                                                                        | Remark |
|:--------------------------------------|:-----------:|---------|------------------------------------------------------------------------------------|--------|
| `WORKFLOW_API_ENABLE_ROUTE_WORKFLOW`  |     API     | true    | A flag that enable workflow route to manage execute manually and workflow logging. |        |
| `WORKFLOW_API_ENABLE_ROUTE_SCHEDULE`  |     API     | true    | A flag that enable run scheduler.                                                  |        |
