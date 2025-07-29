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
            "extras": {"foo": "bar"},
        },
    )
    rs: Result = stage.execute(params={})
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


def test_parallel_stage_exec_max_workers():
    stage: Stage = ParallelStage.model_validate(
        {
            "id": "parallel-stage",
            "name": "Start run parallel stage",
            "max-workers": "${{ max-workers }}",
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
            "extras": {"foo": "bar"},
        },
    )
    rs: Result = stage.execute(params={"max-workers": 1})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "workers": 1,
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

    rs: Result = stage.execute(params={"max-workers": 100})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "ValueError",
            "message": "A max-workers value should between 1 and 19.",
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
    rs: Result = stage.execute({}, event=event)
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
                    "message": "Cancel branch: 'branch02' before start nested process.",
                },
            },
        },
        "errors": {
            "branch02": {
                "name": "StageCancelError",
                "message": "Cancel branch: 'branch02' before start nested process.",
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
    rs: Result = stage.execute({}, event=event)
    assert rs.status == CANCEL
    assert rs.context == {
        "status": CANCEL,
        "workers": 2,
        "parallel": {},
        "errors": {
            "name": "StageCancelError",
            "message": "Cancel before start parallel process.",
        },
    }

    event = MockEvent(n=2)
    rs: Result = stage.execute({}, event=event)
    assert rs.status == CANCEL
    possible = []
    try:
        assert rs.context == {
            "status": CANCEL,
            "workers": 2,
            "parallel": {
                "branch01": {
                    "status": CANCEL,
                    "branch": "branch01",
                    "stages": {},
                    "errors": {
                        "name": "StageCancelError",
                        "message": "Cancel branch: 'branch01' before start nested process.",
                    },
                },
                "branch02": {
                    "status": CANCEL,
                    "branch": "branch02",
                    "stages": {
                        "4967824305": {
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
                        "message": "Cancel branch: 'branch02' after end nested process.",
                    },
                },
            },
            "errors": {
                "branch01": {
                    "name": "StageCancelError",
                    "message": "Cancel branch: 'branch01' before start nested process.",
                },
                "branch02": {
                    "name": "StageCancelError",
                    "message": "Cancel branch: 'branch02' after end nested process.",
                },
            },
        }
        possible.append(True)
    except AssertionError:
        possible.append(False)
    try:
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
                        "message": "Cancel branch: 'branch02' before start nested process.",
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
                                "message": "Cancel before start empty process.",
                            },
                            "status": CANCEL,
                        }
                    },
                    "errors": {
                        "name": "StageCancelError",
                        "message": "Cancel branch: 'branch01' after end nested process.",
                    },
                },
            },
            "errors": {
                "branch02": {
                    "name": "StageCancelError",
                    "message": "Cancel branch: 'branch02' before start nested process.",
                },
                "branch01": {
                    "name": "StageCancelError",
                    "message": "Cancel branch: 'branch01' after end nested process.",
                },
            },
        }
        possible.append(True)
    except AssertionError:
        possible.append(False)
    if not any(possible):
        print(rs.context)
        raise AssertionError("checking context does not match any case.")


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
    rs: Result = stage.execute({})
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
                    "message": "Break branch: 'branch01' because nested stage: 'Raise Stage', failed.",
                },
            }
        },
        "errors": {
            "branch01": {
                "name": "StageError",
                "message": "Break branch: 'branch01' because nested stage: 'Raise Stage', failed.",
            }
        },
    }
