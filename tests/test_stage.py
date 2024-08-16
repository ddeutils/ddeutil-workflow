import ddeutil.workflow.stage as st
from ddeutil.workflow.stage import Stage
from ddeutil.workflow.utils import Result


def test_empty_stage():
    stage: Stage = st.EmptyStage.model_validate(
        {
            "name": "Empty Stage",
            "echo": "hello world",
        }
    )

    rs: Result = stage.execute(params={})
    assert Result(status=0) == rs

    stage.run_id = "demo"
    assert "demo" == stage.run_id
