import ddeutil.workflow.pipeline as pipe
from ddeutil.workflow.utils import Result


def test_stage_if():
    params = {"name": "foo"}
    pipeline = pipe.Pipeline.from_loader(name="pipe-condition", externals={})
    stage = pipeline.job("condition-job").stage(stage_id="condition-stage")

    assert not stage.is_skip(params=pipeline.parameterize(params))
    assert stage.is_skip(params=pipeline.parameterize({"name": "bar"}))
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
                    "ab2214618b003cb11f62e1766d176986": {"outputs": {}},
                },
            },
        },
    } == rs.context
