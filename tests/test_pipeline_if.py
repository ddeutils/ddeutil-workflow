import ddeutil.workflow as wf
from ddeutil.workflow.utils import Result


def test_stage_if():
    params = {"name": "foo"}
    workflow = wf.Workflow.from_loader(name="wf-condition", externals={})
    stage = workflow.job("condition-job").stage(stage_id="condition-stage")

    assert not stage.is_skipped(params=workflow.parameterize(params))
    assert stage.is_skipped(params=workflow.parameterize({"name": "bar"}))
    assert {"name": "foo"} == params


def test_pipe_id():
    workflow = wf.Workflow.from_loader(name="wf-condition", externals={})
    rs: Result = workflow.execute(params={"name": "bar"})
    assert {
        "params": {"name": "bar"},
        "jobs": {
            "condition-job": {
                "matrix": {},
                "stages": {
                    "6708019737": {"outputs": {}},
                },
            },
        },
    } == rs.context
