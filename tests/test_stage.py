import ddeutil.workflow.stage as st
import pytest
from ddeutil.workflow.stage import Stage
from ddeutil.workflow.utils import Result
from pydantic import ValidationError


def test_model_copy():
    stage: Stage = st.EmptyStage.model_validate(
        {
            "name": "Empty Stage",
            "echo": "hello world",
        }
    )
    new_stage: Stage = stage.model_copy(update={"run_id": "dummy"})
    assert "dummy" == new_stage.run_id
    assert id(stage) != id(new_stage)


def test_empty_stage():
    stage: Stage = st.EmptyStage.model_validate(
        {
            "name": "Empty Stage",
            "echo": "hello world",
        }
    )

    rs: Result = stage.execute(params={})
    assert 0 == rs.status
    assert {} == rs.context

    stage.run_id = "demo"
    assert "demo" == stage.run_id


def test_empty_stage_name_raise():
    with pytest.raises(ValidationError):
        st.EmptyStage.model_validate(
            {
                "run_id": "demo",
                "name": "Empty ${{ params.name }}",
                "echo": "hello world",
            }
        )
