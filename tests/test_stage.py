import ddeutil.workflow.stage as st


def test_empty_stage():
    stage = st.EmptyStage.model_validate(
        {
            "name": "Empty Stage",
            "echo": "hello world",
        }
    )
    print(stage)
    print(stage.run_id)
    print(stage.execute(params={}))
    stage.run_id = "demo"
    print(stage.run_id)
