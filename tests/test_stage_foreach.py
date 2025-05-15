from ddeutil.workflow import (
    FAILED,
    SKIP,
    SUCCESS,
    Result,
    Workflow,
)
from ddeutil.workflow.stages import ForEachStage, Stage

from .utils import MockEvent, dump_yaml_context


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
                "item": 1,
                "stages": {
                    "2709471980": {"outputs": {"status": SUCCESS}},
                    "9263488742": {
                        "outputs": {"status": SKIP},
                        "skipped": True,
                    },
                },
            },
            2: {
                "item": 2,
                "stages": {
                    "2709471980": {"outputs": {"status": SUCCESS}},
                    "9263488742": {
                        "outputs": {"status": SKIP},
                        "skipped": True,
                    },
                },
            },
            3: {
                "item": 3,
                "stages": {
                    "2709471980": {"outputs": {"status": SUCCESS}},
                    "9263488742": {
                        "outputs": {"status": SKIP},
                        "skipped": True,
                    },
                },
            },
            4: {
                "item": 4,
                "stages": {
                    "2709471980": {"outputs": {"status": SUCCESS}},
                    "9263488742": {"outputs": {"status": SUCCESS}},
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
                "item": 1,
                "stages": {"2709471980": {"outputs": {"status": SUCCESS}}},
            },
            1: {
                "item": 1,
                "stages": {"2709471980": {"outputs": {"status": SUCCESS}}},
            },
            2: {
                "item": 2,
                "stages": {"2709471980": {"outputs": {"status": SUCCESS}}},
            },
            3: {
                "item": 3,
                "stages": {"2709471980": {"outputs": {"status": SUCCESS}}},
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


def test_foreach_stage_exec_raise_full(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_foreach_raise.yml",
        data="""
        tmp-wf-foreach-raise:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Start run for-each stage"
                  id: foreach-stage
                  foreach: [1, 2]
                  concurrent: 2
                  stages:
                    - name: "Echo stage"
                      echo: |
                        Start run with item ${{ item }}
                    - name: "Final Echo"
                      if: ${{ item }} == 2
                      raise: Raise for item equal 2
                    - name: "Sleep stage"
                      sleep: 4
                    - name: "Echo Final"
                      echo: "This stage should not echo because event was set"
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-foreach-raise")
        stage: Stage = workflow.job("first-job").stage("foreach-stage")
        rs: Result = stage.handler_execute(params={})
        assert rs.status == FAILED
        assert rs.context == {
            "status": FAILED,
            "items": [1, 2],
            "foreach": {
                2: {
                    "item": 2,
                    "stages": {
                        "2709471980": {"outputs": {"status": SUCCESS}},
                        "9263488742": {
                            "outputs": {"status": FAILED},
                            "errors": {
                                "name": "StageError",
                                "message": "Raise for item equal 2",
                            },
                        },
                    },
                    "errors": {
                        "name": "StageError",
                        "message": (
                            "Item-Stage was break because it has a "
                            "nested-stage, 'Final Echo', failed."
                        ),
                    },
                },
                1: {
                    "item": 1,
                    "stages": {
                        "2709471980": {"outputs": {"status": SUCCESS}},
                        "9263488742": {
                            "outputs": {"status": SKIP},
                            "skipped": True,
                        },
                        "2238460182": {"outputs": {"status": SUCCESS}},
                    },
                    "errors": {
                        "name": "StageError",
                        "message": "Item-Stage was canceled because event was set.",
                    },
                },
            },
            "errors": {
                2: {
                    "name": "StageError",
                    "message": (
                        "Item-Stage was break because it has a nested-stage, "
                        "'Final Echo', failed."
                    ),
                },
                1: {
                    "name": "StageError",
                    "message": "Item-Stage was canceled because event was set.",
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
                    - name: "Echo stage"
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
        rs = stage.set_outputs(stage.handler_execute({}).context, to={})
        assert rs == {
            "stages": {
                "foreach-stage": {
                    "outputs": {
                        "status": SUCCESS,
                        "items": [1, 2, 3, 4],
                        "foreach": {
                            1: {
                                "item": 1,
                                "stages": {
                                    "2709471980": {
                                        "outputs": {"status": SUCCESS}
                                    },
                                    "9263488742": {
                                        "outputs": {"status": SKIP},
                                        "skipped": True,
                                    },
                                },
                            },
                            3: {
                                "item": 3,
                                "stages": {
                                    "2709471980": {
                                        "outputs": {"status": SUCCESS}
                                    },
                                    "9263488742": {
                                        "outputs": {"status": SKIP},
                                        "skipped": True,
                                    },
                                },
                            },
                            2: {
                                "item": 2,
                                "stages": {
                                    "2709471980": {
                                        "outputs": {"status": SUCCESS}
                                    },
                                    "9263488742": {
                                        "outputs": {"status": SKIP},
                                        "skipped": True,
                                    },
                                },
                            },
                            4: {
                                "item": 4,
                                "stages": {
                                    "2709471980": {
                                        "outputs": {"status": SUCCESS}
                                    },
                                    "9263488742": {
                                        "outputs": {"status": SUCCESS}
                                    },
                                },
                            },
                        },
                    }
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
                "item": 2,
                "stages": {},
                "errors": {
                    "name": "StageError",
                    "message": "Item-Stage was break because it has a nested-stage, 'Raise with PyStage', failed.",
                },
            },
            1: {"item": 1, "stages": {}},
            3: {"item": 3, "stages": {}},
        },
        "errors": {
            2: {
                "name": "StageError",
                "message": "Item-Stage was break because it has a nested-stage, 'Raise with PyStage', failed.",
            }
        },
    }
