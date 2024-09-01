from datetime import datetime

import ddeutil.workflow as wf


def test_pipe_params_py():
    workflow = wf.Workflow.from_loader(
        name="wf-run-hook",
        externals={},
    )
    rs = workflow.params["run-date"].receive("2024-01-01")
    assert rs == datetime(2024, 1, 1)
