import ddeutil.workflow.pipeline as pipe


def test_stage_trigger():
    pipeline = pipe.Pipeline.from_loader(name="pipe_trigger", externals={})
    stage = pipeline.job("trigger-job").stage(stage_id="trigger-stage")
    params = pipeline.params.copy()
    rs = stage.execute(params=params)
    print(rs)
    print(params)
