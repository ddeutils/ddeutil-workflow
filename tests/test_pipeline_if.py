import ddeutil.workflow as pipe
from ddeutil.workflow.utils import Result


def test_stage_if():
    params = {"name": "foo"}
    pipeline = pipe.Pipeline.from_loader(name="pipe-condition", externals={})
    stage = pipeline.job("condition-job").stage(stage_id="condition-stage")

    assert not stage.is_skipped(params=pipeline.parameterize(params))
    assert stage.is_skipped(params=pipeline.parameterize({"name": "bar"}))
    assert {"name": "foo"} == params


def test_pipe_id():
    pipeline = pipe.Pipeline.from_loader(name="pipe-condition", externals={})
    rs: Result = pipeline.execute(params={"name": "bar"})
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
