from datetime import datetime

import ddeutil.workflow as wf
import ddeutil.workflow.stage as st
from ddeutil.core import getdot
from ddeutil.workflow.utils import Result


def test_stage_exec_trigger():
    workflow = wf.Workflow.from_loader(name="wf-trigger", externals={})
    stage: st.Stage = workflow.job("trigger-job").stage(
        stage_id="trigger-stage"
    )
    rs: Result = stage.execute(params={})
    assert all(k in ("params", "jobs") for k in rs.context.keys())
    assert {
        "author-run": "Trigger Runner",
        "run-date": datetime(2024, 8, 1),
    } == rs.context["params"]


def test_stage_exec_trigger_from_workflow():
    workflow = wf.Workflow.from_loader(name="wf-trigger", externals={})
    rs: Result = workflow.execute(params={})
    assert {
        "author-run": "Trigger Runner",
        "run-date": datetime(2024, 8, 1),
    } == getdot(
        "jobs.trigger-job.stages.trigger-stage.outputs.params", rs.context
    )
