from ddeutil.workflow import (
    CANCEL,
    FAILED,
    SKIP,
    SUCCESS,
    Result,
    Workflow,
)
from ddeutil.workflow.stages import ForEachStage, Stage

from .utils import MockEvent, dump_yaml_context


def test_foreach_stage_exec_all_skipped():
    stage: Stage = ForEachStage(
        name="Start run for-each stage",
        id="foreach-stage",
        foreach=[1, 2, 3],
        stages=[
            {
                "name": "Echo stage",
                "if": "${{ item }} == 4",
                "echo": "Start run with item ${{ item }}",
            },
            {
                "name": "Final Echo",
                "if": "${{ item }} == 4",
                "echo": "Final stage",
            },
        ],
    )
    rs: Result = stage.handler_execute({})
    assert rs.status == SKIP
    assert rs.context == {
        "status": SKIP,
        "items": [1, 2, 3],
        "foreach": {
            1: {
                "status": SKIP,
                "item": 1,
                "stages": {
                    "2709471980": {"outputs": {}, "status": SKIP},
                    "9263488742": {"outputs": {}, "status": SKIP},
                },
            },
            2: {
                "status": SKIP,
                "item": 2,
                "stages": {
                    "2709471980": {"outputs": {}, "status": SKIP},
                    "9263488742": {"outputs": {}, "status": SKIP},
                },
            },
            3: {
                "status": SKIP,
                "item": 3,
                "stages": {
                    "2709471980": {"outputs": {}, "status": SKIP},
                    "9263488742": {"outputs": {}, "status": SKIP},
                },
            },
        },
    }


def test_foreach_stage_exec_skipped():
    stage: Stage = ForEachStage(
        name="Start run for-each stage",
        id="foreach-stage",
        foreach=[1, 2, 3, 4],
        stages=[
            {"name": "Echo stage", "echo": "Start run with item ${{ item }}"},
            {
                "name": "Final Echo",
                "if": "${{ item }} == 4",
                "echo": "Final stage",
            },
        ],
    )
    assert stage.is_nested

    rs: Result = stage.handler_execute({})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "items": [1, 2, 3, 4],
        "foreach": {
            1: {
                "status": SUCCESS,
                "item": 1,
                "stages": {
                    "2709471980": {"outputs": {}, "status": SUCCESS},
                    "9263488742": {"outputs": {}, "status": SKIP},
                },
            },
            2: {
                "status": SUCCESS,
                "item": 2,
                "stages": {
                    "2709471980": {"outputs": {}, "status": SUCCESS},
                    "9263488742": {"outputs": {}, "status": SKIP},
                },
            },
            3: {
                "status": SUCCESS,
                "item": 3,
                "stages": {
                    "2709471980": {"outputs": {}, "status": SUCCESS},
                    "9263488742": {"outputs": {}, "status": SKIP},
                },
            },
            4: {
                "status": SUCCESS,
                "item": 4,
                "stages": {
                    "2709471980": {"outputs": {}, "status": SUCCESS},
                    "9263488742": {"outputs": {}, "status": SUCCESS},
                },
            },
        },
    }


def test_foreach_stage_exec():
    stage: ForEachStage = ForEachStage(
        name="Foreach item was duplicated but use index",
        desc="If set `use_index_as_key` to True it will ignore duplicate value",
        foreach=[1, 1, 2, 3],
        stages=[{"name": "Echo stage", "echo": "Start item ${{ item }}"}],
        use_index_as_key=True,
    )
    rs: Result = stage.handler_execute({})
    assert rs.status == SUCCESS
    assert rs.context == {
        "status": SUCCESS,
        "items": [1, 1, 2, 3],
        "foreach": {
            0: {
                "status": SUCCESS,
                "item": 1,
                "stages": {"2709471980": {"outputs": {}, "status": SUCCESS}},
            },
            1: {
                "status": SUCCESS,
                "item": 1,
                "stages": {"2709471980": {"outputs": {}, "status": SUCCESS}},
            },
            2: {
                "status": SUCCESS,
                "item": 2,
                "stages": {"2709471980": {"outputs": {}, "status": SUCCESS}},
            },
            3: {
                "status": SUCCESS,
                "item": 3,
                "stages": {"2709471980": {"outputs": {}, "status": SUCCESS}},
            },
        },
    }


def test_foreach_stage_exec_raise():
    # NOTE: Raise because type of foreach does not match with list of item.
    stage: ForEachStage = ForEachStage(
        name="Foreach values type not valid",
        id="foreach-raise",
        foreach="${{values.items}}",
    )
    rs: Result = stage.handler_execute({"values": {"items": "test"}})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "TypeError",
            "message": (
                "Does not support string foreach: 'test' that can not convert "
                "to list."
            ),
        },
    }

    # NOTE: Raise because foreach item was duplicated.
    stage: ForEachStage = ForEachStage(
        name="Foreach item was duplicated",
        foreach=[1, 1, 2, 3],
    )
    rs: Result = stage.handler_execute({})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "errors": {
            "name": "ValueError",
            "message": "Foreach item should not duplicate. If this stage must to pass duplicate item, it should set `use_index_as_key: true`.",
        },
    }


def test_foreach_stage_exec_raise_full():
    stage: Stage = ForEachStage.model_validate(
        {
            "name": "Start run for-each stage",
            "id": "foreach-stage",
            "foreach": [1, 2],
            "concurrent": 2,
            "stages": [
                {
                    "name": "Echo stage",
                    "echo": "Start run with item ${{ item }}",
                },
                {
                    "name": "Final Echo",
                    "if": "${{ item }} == 2",
                    "raise": "Raise for item equal 2",
                },
                {
                    "name": "Sleep stage",
                    "sleep": 4,
                },
                {
                    "name": "Echo Final",
                    "echo": "This stage should not echo because event was set",
                },
            ],
        }
    )
    rs: Result = stage.handler_execute(params={})
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "items": [1, 2],
        "foreach": {
            2: {
                "status": FAILED,
                "item": 2,
                "stages": {
                    "2709471980": {"outputs": {}, "status": SUCCESS},
                    "9263488742": {
                        "outputs": {},
                        "errors": {
                            "name": "StageError",
                            "message": "Raise for item equal 2",
                        },
                        "status": FAILED,
                    },
                },
                "errors": {
                    "name": "StageError",
                    "message": "Item execution was break because its nested-stage, 'Final Echo', failed.",
                },
            },
            1: {
                "status": CANCEL,
                "item": 1,
                "stages": {
                    "2709471980": {"outputs": {}, "status": SUCCESS},
                    "9263488742": {"outputs": {}, "status": SKIP},
                    "2238460182": {"outputs": {}, "status": SUCCESS},
                },
                "errors": {
                    "name": "StageCancelError",
                    "message": "Item execution was canceled from the event before start item execution.",
                },
            },
        },
        "errors": {
            2: {
                "name": "StageError",
                "message": "Item execution was break because its nested-stage, 'Final Echo', failed.",
            },
            1: {
                "name": "StageCancelError",
                "message": "Item execution was canceled from the event before start item execution.",
            },
        },
    }


def test_foreach_stage_exec_concurrent(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_foreach_concurrent.yml",
        data="""
        tmp-wf-foreach-concurrent:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Start run for-each stage"
                  id: foreach-stage
                  foreach: [1, 2, 3, 4]
                  concurrent: 3
                  stages:
                    - name: "Start Echo stage"
                      echo: |
                        Start run with item ${{ item }}
                    - name: "Final Echo"
                      if: ${{ item }} == 4
                      echo: |
                        Final run
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-foreach-concurrent")
        stage: Stage = workflow.job("first-job").stage("foreach-stage")
        rs: Result = stage.handler_execute(params={})
        assert rs.status == SUCCESS
        assert rs.context == {
            "status": SUCCESS,
            "items": [1, 2, 3, 4],
            "foreach": {
                2: {
                    "status": SUCCESS,
                    "item": 2,
                    "stages": {
                        "0257114922": {"outputs": {}, "status": SUCCESS},
                        "9263488742": {"outputs": {}, "status": SKIP},
                    },
                },
                1: {
                    "status": SUCCESS,
                    "item": 1,
                    "stages": {
                        "0257114922": {"outputs": {}, "status": SUCCESS},
                        "9263488742": {"outputs": {}, "status": SKIP},
                    },
                },
                3: {
                    "status": SUCCESS,
                    "item": 3,
                    "stages": {
                        "0257114922": {"outputs": {}, "status": SUCCESS},
                        "9263488742": {"outputs": {}, "status": SKIP},
                    },
                },
                4: {
                    "status": SUCCESS,
                    "item": 4,
                    "stages": {
                        "0257114922": {"outputs": {}, "status": SUCCESS},
                        "9263488742": {"outputs": {}, "status": SUCCESS},
                    },
                },
            },
        }

        output = stage.set_outputs(rs.context, {})
        assert output == {
            "stages": {
                "foreach-stage": {
                    "outputs": {
                        "items": [1, 2, 3, 4],
                        "foreach": {
                            1: {
                                "status": SUCCESS,
                                "item": 1,
                                "stages": {
                                    "0257114922": {
                                        "outputs": {},
                                        "status": SUCCESS,
                                    },
                                    "9263488742": {
                                        "outputs": {},
                                        "status": SKIP,
                                    },
                                },
                            },
                            2: {
                                "status": SUCCESS,
                                "item": 2,
                                "stages": {
                                    "0257114922": {
                                        "outputs": {},
                                        "status": SUCCESS,
                                    },
                                    "9263488742": {
                                        "outputs": {},
                                        "status": SKIP,
                                    },
                                },
                            },
                            3: {
                                "status": SUCCESS,
                                "item": 3,
                                "stages": {
                                    "0257114922": {
                                        "outputs": {},
                                        "status": SUCCESS,
                                    },
                                    "9263488742": {
                                        "outputs": {},
                                        "status": SKIP,
                                    },
                                },
                            },
                            4: {
                                "status": SUCCESS,
                                "item": 4,
                                "stages": {
                                    "0257114922": {
                                        "outputs": {},
                                        "status": SUCCESS,
                                    },
                                    "9263488742": {
                                        "outputs": {},
                                        "status": SUCCESS,
                                    },
                                },
                            },
                        },
                    },
                    "status": SUCCESS,
                }
            }
        }


def test_foreach_stage_exec_concurrent_with_raise():
    stage: ForEachStage = ForEachStage(
        id="foreach-stage",
        name="Start run for-each stage",
        foreach=[1, 2, 3, 4, 5],
        concurrent=2,
        stages=[
            {
                "name": "Raise with PyStage",
                "run": (
                    "import time\n\n"
                    "if ${{ item }} == 2:\n"
                    "\ttime.sleep(0.8)\n"
                    '\traise ValueError("Raise error for item equal 2")\n'
                    "else:\n"
                    "\ttime.sleep(3)"
                ),
            },
        ],
        extras={"stage_default_id": False},
    )
    event = MockEvent(n=4)
    rs: Result = stage.handler_execute({}, event=event)
    assert rs.status == FAILED
    assert rs.context == {
        "status": FAILED,
        "items": [1, 2, 3, 4, 5],
        "foreach": {
            2: {
                "status": FAILED,
                "item": 2,
                "stages": {},
                "errors": {
                    "name": "StageError",
                    "message": "Item execution was break because its nested-stage, 'Raise with PyStage', failed.",
                },
            },
            1: {"status": SUCCESS, "item": 1, "stages": {}},
            3: {"status": SUCCESS, "item": 3, "stages": {}},
        },
        "errors": {
            2: {
                "name": "StageError",
                "message": "Item execution was break because its nested-stage, 'Raise with PyStage', failed.",
            }
        },
    }


def test_foreach_stage_exec_concurrent_raise():
    stage: Stage = ForEachStage.model_validate(
        {
            "id": "foreach-stage",
            "name": "Start run foreach with concurrent",
            "foreach": [1, 2],
            "concurrent": 3,
            "stages": [
                {
                    "name": "Raise Error Inside",
                    "id": "raise-error",
                    "if": "${{ item }} == 1",
                    "run": "raise ValueError('Testing raise error PyStage!!!')",
                },
                {
                    "name": "Echo hello world",
                    "id": "echo",
                    "if": "${{ item }} == 2",
                    "echo": "Hello World",
                },
            ],
        }
    )
    rs: Result = stage.handler_execute(params={})
    assert rs.status == FAILED
    try:
        assert rs.context == {
            "status": FAILED,
            "items": [1, 2],
            "foreach": {
                1: {
                    "status": FAILED,
                    "item": 1,
                    "stages": {
                        "raise-error": {
                            "outputs": {},
                            "errors": {
                                "name": "ValueError",
                                "message": "Testing raise error PyStage!!!",
                            },
                            "status": FAILED,
                        }
                    },
                    "errors": {
                        "name": "StageError",
                        "message": "Item execution was break because its nested-stage, 'raise-error', failed.",
                    },
                },
                2: {
                    "status": SUCCESS,
                    "item": 2,
                    "stages": {
                        "raise-error": {"outputs": {}, "status": SKIP},
                        "echo": {"outputs": {}, "status": SUCCESS},
                    },
                },
            },
            "errors": {
                1: {
                    "name": "StageError",
                    "message": "Item execution was break because its nested-stage, 'raise-error', failed.",
                }
            },
        }
    except AssertionError:
        try:
            assert rs.context == {
                "status": FAILED,
                "items": [1, 2],
                "foreach": {
                    1: {
                        "status": FAILED,
                        "item": 1,
                        "stages": {
                            "raise-error": {
                                "outputs": {},
                                "errors": {
                                    "name": "ValueError",
                                    "message": "Testing raise error PyStage!!!",
                                },
                                "status": FAILED,
                            }
                        },
                        "errors": {
                            "name": "StageError",
                            "message": "Item execution was break because its nested-stage, 'raise-error', failed.",
                        },
                    },
                    2: {
                        "status": CANCEL,
                        "item": 2,
                        "stages": {
                            "raise-error": {"outputs": {}, "status": SKIP}
                        },
                        "errors": {
                            "name": "StageCancelError",
                            "message": "Item execution was canceled from the event before start item execution.",
                        },
                    },
                },
                "errors": {
                    2: {
                        "name": "StageCancelError",
                        "message": "Item execution was canceled from the event before start item execution.",
                    },
                    1: {
                        "name": "StageError",
                        "message": "Item execution was break because its nested-stage, 'raise-error', failed.",
                    },
                },
            }
        except AssertionError:
            assert rs.context == {
                "status": FAILED,
                "items": [1, 2],
                "foreach": {
                    1: {
                        "status": FAILED,
                        "item": 1,
                        "stages": {
                            "raise-error": {
                                "outputs": {},
                                "errors": {
                                    "name": "ValueError",
                                    "message": "Testing raise error PyStage!!!",
                                },
                                "status": FAILED,
                            }
                        },
                        "errors": {
                            "name": "StageError",
                            "message": "Item execution was break because its nested-stage, 'raise-error', failed.",
                        },
                    },
                    2: {
                        "status": CANCEL,
                        "item": 2,
                        "stages": {
                            "raise-error": {"outputs": {}, "status": SKIP},
                            "echo": {
                                "outputs": {},
                                "errors": {
                                    "name": "StageCancelError",
                                    "message": "Execution was canceled from the event before start parallel.",
                                },
                                "status": CANCEL,
                            },
                        },
                        "errors": {
                            "name": "StageCancelError",
                            "message": "Item execution was canceled from the event after end item execution.",
                        },
                    },
                },
                "errors": {
                    2: {
                        "name": "StageCancelError",
                        "message": "Item execution was canceled from the event after end item execution.",
                    },
                    1: {
                        "name": "StageError",
                        "message": "Item execution was break because its nested-stage, 'raise-error', failed.",
                    },
                },
            }
