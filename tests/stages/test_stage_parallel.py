from ddeutil.workflow import (
    CANCEL,
    FAILED,
    SKIP,
    SUCCESS,
    Result,
)
from ddeutil.workflow.stages import ParallelStage, Stage

from ..utils import MockEvent


def test_parallel_stage_exec():
    stage: Stage = ParallelStage.model_validate(
        {
            "id": "parallel-stage",
            "name": "Start run parallel stage",
            "parallel": {
                "branch01": [
                    {
                        "name": "Echo branch01 stage",
                        "echo": "Start run with branch 1\n",
                        "sleep": 1.0,
                    },
                    {
                        "id": "skip-stage",
                        "name": "Skip Stage",
                        "if": "${{ branch | rstr }} == 'branch02'",
                    },
                ],
                "branch02": [
                    {
                        "name": "Echo branch02 stage",
                        "echo": "Start run with branch 2\n",
                    }
                ],
            },
        }
    )
    rs: Result = stage.handler_execute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "workers": 2,
        "parallel": {
            "branch02": {
                "status": SUCCESS,
                "branch": "branch02",
                "stages": {"4967824305": {"outputs": {}, "status": SUCCESS}},
            },
            "branch01": {
                "status": SUCCESS,
                "branch": "branch01",
                "stages": {
                    "0573477600": {"outputs": {}, "status": SUCCESS},
                    "skip-stage": {"outputs": {}, "status": SKIP},
                },
            },
        },
    }


def test_parallel_stage_exec_cancel_from_stage():
    stage: Stage = ParallelStage.model_validate(
        {
            "id": "parallel-stage",
            "name": "Start run parallel stage",
            "max-workers": 1,
            "parallel": {
                "branch01": [
                    {
                        "name": "Echo branch01 stage",
                        "echo": "Start run with branch 1\n",
                    },
                ],
                "branch02": [
                    {
                        "name": "Echo branch02 stage",
                        "echo": "Start run with branch 2\n",
                    }
                ],
            },
        }
    )
    event = MockEvent(n=3)
    rs: Result = stage.handler_execute({}, event=event)
    assert rs.context == {
        "status": CANCEL,
        "workers": 1,
        "parallel": {
            "branch01": {
                "status": SUCCESS,
                "branch": "branch01",
                "stages": {"0573477600": {"outputs": {}, "status": SUCCESS}},
            },
            "branch02": {
                "status": CANCEL,
                "branch": "branch02",
                "stages": {},
                "errors": {
                    "name": "StageCancelError",
                    "message": "Branch execution was canceled from the event before start branch execution.",
                },
            },
        },
        "errors": {
            "branch02": {
                "name": "StageCancelError",
                "message": "Branch execution was canceled from the event before start branch execution.",
            }
        },
    }


def test_parallel_stage_exec_cancel():
    stage: Stage = ParallelStage.model_validate(
        {
            "id": "parallel-stage",
            "name": "Start run parallel stage",
            "max_workers": 1,
            "parallel": {
                "branch01": [
                    {
                        "name": "Echo branch01 stage",
                        "echo": "Start run with branch 1\n",
                    },
                ],
                "branch02": [
                    {
                        "name": "Echo branch02 stage",
                        "echo": "Start run with branch 2\n",
                    }
                ],
            },
        }
    )
    event = MockEvent(n=0)
    rs: Result = stage.handler_execute({}, event=event)
    assert rs.status == CANCEL
    assert rs.context == {
        "status": CANCEL,
        "workers": 2,
        "parallel": {},
        "errors": {
            "name": "StageCancelError",
            "message": "Execution was canceled from the event before start parallel.",
        },
    }

    event = MockEvent(n=2)
    rs: Result = stage.handler_execute({}, event=event)
    assert rs.status == CANCEL
    assert rs.context == {
        "status": CANCEL,
        "workers": 2,
        "parallel": {
            "branch02": {
                "status": CANCEL,
                "branch": "branch02",
                "stages": {},
                "errors": {
                    "name": "StageCancelError",
                    "message": "Branch execution was canceled from the event before start branch execution.",
                },
            },
            "branch01": {
                "status": CANCEL,
                "branch": "branch01",
                "stages": {
                    "0573477600": {
                        "outputs": {},
                        "errors": {
                            "name": "StageCancelError",
                            "message": "Execution was canceled from the event before start parallel.",
                        },
                        "status": CANCEL,
                    }
                },
                "errors": {
                    "name": "StageCancelError",
                    "message": "Branch execution was canceled from the event after end branch execution.",
                },
            },
        },
        "errors": {
            "branch02": {
                "name": "StageCancelError",
                "message": "Branch execution was canceled from the event before start branch execution.",
            },
            "branch01": {
                "name": "StageCancelError",
                "message": "Branch execution was canceled from the event after end branch execution.",
            },
        },
    }


def test_parallel_stage_exec_raise():
    stage = ParallelStage(
        name="Parallel Stage Raise",
        parallel={
            "branch01": [
                {
                    "name": "Raise Stage",
                    "raise": "Raise error inside parallel stage.",
                }
            ]
        },
    )
    rs: Result = stage.handler_execute({})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "workers": 2,
        "parallel": {
            "branch01": {
                "status": FAILED,
                "branch": "branch01",
                "stages": {
                    "6966382767": {
                        "outputs": {},
                        "errors": {
                            "name": "StageError",
                            "message": "Raise error inside parallel stage.",
                        },
                        "status": FAILED,
                    }
                },
                "errors": {
                    "name": "StageError",
                    "message": "Branch execution was break because its nested-stage, 'Raise Stage', failed.",
                },
            }
        },
        "errors": {
            "branch01": {
                "name": "StageError",
                "message": "Branch execution was break because its nested-stage, 'Raise Stage', failed.",
            }
        },
    }
