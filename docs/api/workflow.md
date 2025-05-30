# Workflow

Workflow module is the core module of this package. It keeps Release,
ReleaseQueue, and Workflow models.

This package implement timeout strategy on the workflow execution layer only
because the main propose of this package is using Workflow to be orchestrator.

## Workflow

!!! example "YAML"

    === "Workflow"

        ```yaml
        wf-name:
          type: Workflow
          on: 'on_every_5_min'
          params:
            author-run:
              type: str
            run-date:
              type: datetime
          jobs:
            first-job:
              stages:
                - name: "Empty stage do logging to console only!!"
        ```

!!! example "Python"

    ```python
    from ddeutil.workflow import Workflow

    wf = Workflow.from_loader(name='pipeline-name', externals={})
    wf.execute(params={'author-run': 'Local Workflow', 'run-date': '2024-01-01'})
    ```

    !!! note

        The above parameter can use short declarative statement. You can pass a parameter
        type to the key of a parameter name but it does not handler default value if you
        run this pipeline workflow with schedule.

        ```yaml
        ...
        params:
          author-run: str
          run-date: datetime
        ...
        ```

        And for the type, you can remove `ddeutil.workflow` prefix because we can find
        it by looping search from `WORKFLOW_CORE_REGISTRY` value.

| field    | data type         | default  | description |
|----------|-------------------|:--------:|-------------|
| name     | str               |          |             |
| desc     | str \| None       |  `None`  |             |
| params   | dict[str, Param]  | `dict()` |             |
| on       | list[Crontab]     | `list()` |             |
| jobs     | dict[str, Job]    | `dict()` |             |
