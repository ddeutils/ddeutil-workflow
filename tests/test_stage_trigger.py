from datetime import datetime

import ddeutil.workflow.pipeline as pipe
import ddeutil.workflow.stage as st
from ddeutil.core import getdot
from ddeutil.workflow.utils import Result


def test_stage_trigger():
    pipeline = pipe.Pipeline.from_loader(name="pipe-trigger", externals={})
    stage: st.Stage = pipeline.job("trigger-job").stage(
        stage_id="trigger-stage"
    )
    rs: Result = stage.execute(params={})
    assert all(k in ("params", "jobs") for k in rs.context.keys())
    assert {
        "author-run": "Trigger Runner",
        "run-date": datetime(2024, 8, 1),
    } == rs.context["params"]


def test_pipe_trigger():
    pipeline = pipe.Pipeline.from_loader(name="pipe-trigger", externals={})
    rs: Result = pipeline.execute(params={})
    # import json
    # print(json.dumps(rs.context, indent=2, default=str))
    assert {
        "author-run": "Trigger Runner",
        "run-date": datetime(2024, 8, 1),
    } == getdot(
        "jobs.trigger-job.stages.trigger-stage.outputs.params", rs.context
    )
