import pytest
from ddeutil.workflow import CANCEL, FAILED, SKIP, SUCCESS, Result
from ddeutil.workflow.stages import CaseStage, Stage
from pydantic import ValidationError

from ..utils import MockEvent


def test_case_stage_raise():
    # NOTE: Raise because it contains else case more than 1.
    with pytest.raises(ValidationError):
        CaseStage.model_validate(
            {
                "name": "Start run case-match stage",
                "id": "case-stage",
                "case": "${{ params.name }}",
                "match": [
                    {
                        "else": [
                            {
                                "name": "Else stage",
                                "echo": "Not match any case.",
                            },
                        ],
                    },
                    {
                        "else": [
                            {
                                "name": "Else stage",
                                "echo": "Not match any case.",
                            },
                        ],
                    },
                ],
            }
        )

    # NOTE: Raise because it contains else case more than 1.
    with pytest.raises(ValidationError):
        CaseStage.model_validate(
            {
                "name": "Start run case-match stage",
                "id": "case-stage",
                "case": "${{ params.name }}",
                "match": [
                    {
                        "case": "_",
                        "stages": [
                            {
                                "name": "Else stage",
                                "echo": "Not match any case.",
                            },
                        ],
                    },
                    {
                        "case": "_",
                        "stages": [
                            {
                                "name": "Else stage",
                                "echo": "Not match any case.",
                            },
                        ],
                    },
                ],
            }
        )


def test_case_stage_exec():
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
        },
    )
    rs: Result = stage.execute({"params": {"name": "bar"}}, run_id="01")
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

    rs: Result = stage.execute({"params": {"name": "foo"}}, run_id="02")
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

    rs: Result = stage.execute({"params": {"name": "test"}}, run_id="03")
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "case": "_",
        "stages": {"5883888894": {"outputs": {}, "status": SUCCESS}},
    }


def test_case_stage_exec_else():
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
                    "else": [
                        {"name": "Else stage", "echo": "Not match any case."},
                    ],
                },
            ],
        },
    )
    rs: Result = stage.execute({"params": {"name": "test"}}, run_id="03")
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
            "extras": {"foo": "bar"},
        }
    )
    # NOTE: Raise because else condition does not set.
    rs: Result = stage.execute({"params": {"name": "test"}}, run_id="01")
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
                            "name": "Raise stage",
                            "raise": "Raise with ${{ params.name }}",
                        }
                    ],
                },
            ],
            "extras": {"foo": "bar"},
        }
    )
    rs: Result = stage.execute({"params": {"name": "bar"}}, run_id="02")
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "case": "bar",
        "stages": {
            "4045646338": {
                "outputs": {},
                "errors": {"name": "StageError", "message": "Raise with bar"},
                "status": FAILED,
            }
        },
        "errors": {
            "name": "StageError",
            "message": "Break case: 'bar' because nested stage: Raise stage, failed.",
        },
    }


def test_case_stage_exec_cancel():
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
    event = MockEvent(n=0)
    rs: Result = stage.execute(
        {"params": {"name": "bar"}}, event=event, run_id="03"
    )
    assert rs.status == CANCEL
    assert rs.context == {
        "status": CANCEL,
        "errors": {
            "name": "StageCancelError",
            "message": "Cancel before start case process.",
        },
    }

    event = MockEvent(n=1)
    rs: Result = stage.execute(
        {"params": {"name": "bar"}}, event=event, run_id="04"
    )
    assert rs.status == CANCEL
    assert rs.context == {
        "status": CANCEL,
        "case": "bar",
        "stages": {},
        "errors": {
            "name": "StageError",
            "message": "Cancel case: 'bar' before start nested process.",
        },
    }

    event = MockEvent(n=2)
    rs: Result = stage.execute(
        {"params": {"name": "bar"}}, event=event, run_id="04"
    )
    assert rs.status == CANCEL
    assert rs.context == {
        "status": CANCEL,
        "case": "bar",
        "stages": {
            "3616274431": {
                "outputs": {},
                "errors": {
                    "name": "StageCancelError",
                    "message": "Cancel before start empty process.",
                },
                "status": CANCEL,
            }
        },
        "errors": {
            "name": "StageCancelError",
            "message": "Cancel case 'bar' after end nested process.",
        },
    }


def test_case_stage_exec_skipped():
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
    rs: Result = stage.execute({"params": {"name": "test"}}, run_id="01")
    assert rs.status == SKIP
    assert rs.context == {"status": SKIP}

    stage: Stage = CaseStage.model_validate(
        {
            "name": "Stage skip not has else condition",
            "id": "not-else",
            "case": "${{ params.name }}",
            "match": [
                {
                    "case": "bar",
                    "stages": [
                        {
                            "name": "Match name with Bar",
                            "if": "'${{ params.name }}' != 'bar'",
                            "echo": "Hello ${{ params.name }}",
                        }
                    ],
                }
            ],
        }
    )
    rs: Result = stage.execute({"params": {"name": "bar"}}, run_id="02")
    assert rs.status == SKIP
    assert rs.context == {
        "status": SKIP,
        "case": "bar",
        "stages": {"3616274431": {"outputs": {}, "status": SKIP}},
    }
