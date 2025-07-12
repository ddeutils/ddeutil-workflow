from threading import Event

from ddeutil.workflow import (
    CANCEL,
    FAILED,
    SKIP,
    SUCCESS,
    Result,
    Stage,
    Workflow,
)
from ddeutil.workflow.stages import EmptyStage, RaiseStage, UntilStage

from ..utils import MockEvent, dump_yaml_context


def test_until_stage():
    stage = UntilStage.model_validate(
        {
            "name": "This is until stage",
            "item": 1,
            "until": "${{ item }} > 2",
            "stages": [
                EmptyStage(name="Empty stage nested", echo="1"),
                EmptyStage(name="Empty stage nested", echo="2"),
            ],
            "extras": {"foo": "bar"},
        }
    )
    assert stage.is_nested

    rs: Result = stage.execute(params={})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "until": {
            1: {
                "status": SUCCESS,
                "loop": 1,
                "item": 1,
                "stages": {"4735427693": {"outputs": {}, "status": SUCCESS}},
            },
            2: {
                "status": SUCCESS,
                "loop": 2,
                "item": 2,
                "stages": {"4735427693": {"outputs": {}, "status": SUCCESS}},
            },
        },
    }


def test_until_stage_raise():
    stage = UntilStage.model_validate(
        {
            "name": "This is until stage",
            "item": 1,
            "until": "${{ item }} > 2",
            "stages": [
                RaiseStage.model_validate(
                    {"name": "Raise stage nested", "raise": "Raise some error."}
                ),
            ],
            "extras": {"foo": "bar"},
        }
    )
    rs: Result = stage.execute(params={})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "until": {
            1: {
                "status": FAILED,
                "loop": 1,
                "item": 1,
                "stages": {
                    "1426584094": {
                        "outputs": {},
                        "errors": {
                            "name": "StageError",
                            "message": "Raise some error.",
                        },
                        "status": FAILED,
                    }
                },
                "errors": {
                    "name": "StageError",
                    "message": "Loop execution was break because its nested-stage, 'Raise stage nested', failed.",
                },
            }
        },
        "errors": {
            "name": "StageError",
            "message": "Loop execution was break because its nested-stage, 'Raise stage nested', failed.",
        },
    }

    stage = UntilStage.model_validate(
        {
            "name": "This is until stage",
            "item": 1,
            "until": "${{ item }} if ${{ item }} == 1 else 'demo'",
            "stages": [
                EmptyStage(name="Empty stage nested", echo="1"),
            ],
            "extras": {"foo": "bar"},
        }
    )
    rs: Result = stage.execute(params={})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "until": {
            1: {
                "status": SUCCESS,
                "loop": 1,
                "item": 1,
                "stages": {"4735427693": {"outputs": {}, "status": SUCCESS}},
            }
        },
        "errors": {
            "name": "TypeError",
            "message": "Return type of until condition not be `boolean`, getting: 'demo'",
        },
    }


def test_until_stage_skipped():
    stage = UntilStage.model_validate(
        {
            "name": "This is until stage",
            "item": 1,
            "until": "${{ item }} > 2",
            "stages": [
                EmptyStage.model_validate(
                    {
                        "name": "Empty stage nested",
                        "echo": "1",
                        "if": "${{ item }} == 10",
                    }
                ),
            ],
        }
    )
    rs: Result = stage.execute(params={})
    assert rs.status == SKIP
    assert rs.context == {
        "status": SKIP,
        "until": {
            1: {
                "status": SKIP,
                "loop": 1,
                "item": 1,
                "stages": {"4735427693": {"outputs": {}, "status": SKIP}},
            },
            2: {
                "status": SKIP,
                "loop": 2,
                "item": 2,
                "stages": {"4735427693": {"outputs": {}, "status": SKIP}},
            },
        },
    }


def test_until_stage_cancel():
    stage = UntilStage.model_validate(
        {
            "name": "This is until stage",
            "item": 1,
            "until": "${{ item }} > 2",
            "stages": [
                EmptyStage(name="Empty stage nested", echo="1"),
                EmptyStage(name="Empty stage nested", echo="2"),
            ],
            "extras": {"foo": "bar"},
        }
    )
    event = Event()
    event.set()
    rs: Result = stage.execute(params={}, event=event)
    assert rs.status == CANCEL
    assert rs.context == {
        "status": CANCEL,
        "until": {},
        "errors": {
            "name": "StageCancelError",
            "message": "Execution was canceled from the event before start loop.",
        },
    }

    event = MockEvent(n=1)
    rs: Result = stage.execute(params={}, event=event)
    assert rs.status == CANCEL
    assert rs.context == {
        "status": CANCEL,
        "until": {
            1: {
                "status": CANCEL,
                "loop": 1,
                "item": 1,
                "stages": {},
                "errors": {
                    "name": "StageCancelError",
                    "message": "Loop execution was canceled from the event before start loop execution.",
                },
            }
        },
        "errors": {
            "name": "StageCancelError",
            "message": "Loop execution was canceled from the event before start loop execution.",
        },
    }

    event = MockEvent(n=2)
    rs: Result = stage.execute(params={}, event=event)
    assert rs.status == CANCEL
    assert rs.context == {
        "status": CANCEL,
        "until": {
            1: {
                "status": CANCEL,
                "loop": 1,
                "item": 1,
                "stages": {
                    "4735427693": {
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
                    "message": "Loop execution was canceled from the event after end loop execution.",
                },
            }
        },
        "errors": {
            "name": "StageCancelError",
            "message": "Loop execution was canceled from the event after end loop execution.",
        },
    }


def test_until_stage_exec_exceed_loop():
    stage = UntilStage.model_validate(
        {
            "name": "This is until stage",
            "item": 1,
            "until": "${{ item }} > 2",
            "max-loop": 1,
            "stages": [
                EmptyStage(name="Empty stage nested", echo="1"),
            ],
        }
    )
    rs: Result = stage.execute(params={})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "until": {
            1: {
                "status": SUCCESS,
                "loop": 1,
                "item": 1,
                "stages": {"4735427693": {"outputs": {}, "status": SUCCESS}},
            }
        },
        "errors": {
            "name": "StageError",
            "message": "Loop was exceed the maximum 1 loop.",
        },
    }


def test_until_stage_exec_full(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_until.yml",
        data="""
        tmp-wf-until:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Start run until stage"
                  id: until-stage
                  item: 1
                  until: "${{ item }} > 4"
                  max-loop: 5
                  stages:
                    - name: "Echo stage"
                      echo: |
                        Start run with item ${{ item }}
                    - name: "Final Echo"
                      if: ${{ item }} == 4
                      echo: |
                        Final run
                    - name: "Set item"
                      run: |
                        item = ${{ item }}
                        item += 1
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-until")
        stage: Stage = workflow.job("first-job").stage("until-stage")
        rs: Result = stage.execute(params={})
        assert rs.status == SUCCESS
        assert rs.context == {
            "status": SUCCESS,
            "until": {
                1: {
                    "status": SUCCESS,
                    "loop": 1,
                    "item": 1,
                    "stages": {
                        "2709471980": {"outputs": {}, "status": SUCCESS},
                        "9263488742": {"outputs": {}, "status": SKIP},
                        "3635623619": {
                            "outputs": {"item": 2},
                            "status": SUCCESS,
                        },
                    },
                },
                2: {
                    "status": SUCCESS,
                    "loop": 2,
                    "item": 2,
                    "stages": {
                        "2709471980": {"outputs": {}, "status": SUCCESS},
                        "9263488742": {"outputs": {}, "status": SKIP},
                        "3635623619": {
                            "outputs": {"item": 3},
                            "status": SUCCESS,
                        },
                    },
                },
                3: {
                    "status": SUCCESS,
                    "loop": 3,
                    "item": 3,
                    "stages": {
                        "2709471980": {"outputs": {}, "status": SUCCESS},
                        "9263488742": {"outputs": {}, "status": SKIP},
                        "3635623619": {
                            "outputs": {"item": 4},
                            "status": SUCCESS,
                        },
                    },
                },
                4: {
                    "status": SUCCESS,
                    "loop": 4,
                    "item": 4,
                    "stages": {
                        "2709471980": {"outputs": {}, "status": SUCCESS},
                        "9263488742": {"outputs": {}, "status": SUCCESS},
                        "3635623619": {
                            "outputs": {"item": 5},
                            "status": SUCCESS,
                        },
                    },
                },
            },
        }

        output = stage.set_outputs(rs.context, to={})
        assert output == {
            "stages": {
                "until-stage": {
                    "status": SUCCESS,
                    "outputs": {
                        "until": {
                            1: {
                                "status": SUCCESS,
                                "loop": 1,
                                "item": 1,
                                "stages": {
                                    "2709471980": {
                                        "outputs": {},
                                        "status": SUCCESS,
                                    },
                                    "9263488742": {
                                        "outputs": {},
                                        "status": SKIP,
                                    },
                                    "3635623619": {
                                        "outputs": {"item": 2},
                                        "status": SUCCESS,
                                    },
                                },
                            },
                            2: {
                                "status": SUCCESS,
                                "loop": 2,
                                "item": 2,
                                "stages": {
                                    "2709471980": {
                                        "outputs": {},
                                        "status": SUCCESS,
                                    },
                                    "9263488742": {
                                        "outputs": {},
                                        "status": SKIP,
                                    },
                                    "3635623619": {
                                        "outputs": {"item": 3},
                                        "status": SUCCESS,
                                    },
                                },
                            },
                            3: {
                                "status": SUCCESS,
                                "loop": 3,
                                "item": 3,
                                "stages": {
                                    "2709471980": {
                                        "outputs": {},
                                        "status": SUCCESS,
                                    },
                                    "9263488742": {
                                        "outputs": {},
                                        "status": SKIP,
                                    },
                                    "3635623619": {
                                        "outputs": {"item": 4},
                                        "status": SUCCESS,
                                    },
                                },
                            },
                            4: {
                                "status": SUCCESS,
                                "loop": 4,
                                "item": 4,
                                "stages": {
                                    "2709471980": {
                                        "outputs": {},
                                        "status": SUCCESS,
                                    },
                                    "9263488742": {
                                        "outputs": {},
                                        "status": SUCCESS,
                                    },
                                    "3635623619": {
                                        "outputs": {"item": 5},
                                        "status": SUCCESS,
                                    },
                                },
                            },
                        }
                    },
                }
            }
        }
