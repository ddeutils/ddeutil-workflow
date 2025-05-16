from ddeutil.workflow import CANCEL, FAILED, SUCCESS, Result
from ddeutil.workflow.stages import CaseStage, Stage


def test_case_stage_exec(test_path):
    stage: Stage = CaseStage.model_validate(
        {
            "name": "Start run case-match stage",
            "id": "case-stage",
            "case": "${{ params.name }}",
            "match": [
                {
                    "case": "bar",
                    "stages": [
                        {
                            "name": "Match name with Bar",
                            "echo": "Hello ${{ params.name }}",
                        },
                    ],
                },
                {
                    "case": "foo",
                    "stages": [
                        {
                            "name": "Match name with Foo",
                            "echo": "Hello ${{ params.name }}",
                        },
                    ],
                },
                {
                    "case": "_",
                    "stages": [
                        {"name": "Else stage", "echo": "Not match any case."},
                    ],
                },
            ],
        }
    )
    rs: Result = stage.handler_execute({"params": {"name": "bar"}})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "case": "bar",
        "stages": {"3616274431": {"outputs": {}, "status": SUCCESS}},
    }

    output = stage.set_outputs(rs.context, to={})
    assert output == {
        "stages": {
            "case-stage": {
                "status": SUCCESS,
                "outputs": {
                    "case": "bar",
                    "stages": {
                        "3616274431": {"outputs": {}, "status": SUCCESS}
                    },
                },
            }
        }
    }

    rs: Result = stage.handler_execute({"params": {"name": "foo"}})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "case": "foo",
        "stages": {"9300140245": {"outputs": {}, "status": SUCCESS}},
    }

    output = stage.set_outputs(rs.context, to={})
    assert output == {
        "stages": {
            "case-stage": {
                "status": SUCCESS,
                "outputs": {
                    "case": "foo",
                    "stages": {
                        "9300140245": {"outputs": {}, "status": SUCCESS}
                    },
                },
            }
        }
    }

    rs: Result = stage.handler_execute({"params": {"name": "test"}})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "case": "_",
        "stages": {"5883888894": {"outputs": {}, "status": SUCCESS}},
    }


def test_case_stage_exec_raise():
    stage: Stage = CaseStage.model_validate(
        {
            "name": "Stage raise not has else condition",
            "id": "raise-else",
            "case": "${{ params.name }}",
            "match": [
                {
                    "case": "bar",
                    "stages": [
                        {
                            "name": "Match name with Bar",
                            "echo": "Hello ${{ params.name }}",
                        }
                    ],
                },
            ],
        }
    )
    # NOTE: Raise because else condition does not set.
    rs: Result = stage.handler_execute({"params": {"name": "test"}})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "StageError",
            "message": (
                "This stage does not set else for support not match any case."
            ),
        },
    }


def test_case_stage_exec_cancel():
    stage: Stage = CaseStage.model_validate(
        {
            "name": "Stage skip not has else condition",
            "id": "not-else",
            "case": "${{ params.name }}",
            "skip-not-match": True,
            "match": [
                {
                    "case": "bar",
                    "stages": [
                        {
                            "name": "Match name with Bar",
                            "echo": "Hello ${{ params.name }}",
                        }
                    ],
                }
            ],
        }
    )
    rs: Result = stage.handler_execute({"params": {"name": "test"}})
    assert rs.status == CANCEL
    assert rs.context == {
        "status": CANCEL,
        "errors": {
            "name": "StageError",
            "message": (
                "Case-Stage was canceled because it does not match "
                "any case and else condition does not set too."
            ),
        },
    }
