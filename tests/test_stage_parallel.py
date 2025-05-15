from threading import Event

from ddeutil.workflow import (
    CANCEL,
    FAILED,
    ParallelStage,
    Result,
    Workflow,
)
from ddeutil.workflow.stages import Stage

from .utils import MockEvent, dump_yaml_context


def test_parallel_stage_exec(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_parallel.yml",
        data="""
        tmp-wf-parallel:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Start run parallel stage"
                  id: parallel-stage
                  parallel:
                    branch01:
                      - name: "Echo branch01 stage"
                        echo: |
                          Start run with branch 1
                        sleep: 1
                      - name: "Skip Stage"
                        if: ${{ branch | rstr }} == "branch02"
                        id: skip-stage
                    branch02:
                      - name: "Echo branch02 stage"
                        echo: |
                          Start run with branch 2
        """,
    ):
        workflow = Workflow.from_conf(
            name="tmp-wf-parallel",
        )
        stage: Stage = workflow.job("first-job").stage("parallel-stage")
        rs = stage.set_outputs(stage.handler_execute({}).context, to={})
        assert rs == {
            "stages": {
                "parallel-stage": {
                    "outputs": {
                        "parallel": {
                            "branch02": {
                                "branch": "branch02",
                                "stages": {"4967824305": {"outputs": {}}},
                            },
                            "branch01": {
                                "branch": "branch01",
                                "stages": {
                                    "0573477600": {"outputs": {}},
                                    "skip-stage": {
                                        "outputs": {},
                                        "skipped": True,
                                    },
                                },
                            },
                        },
                    },
                },
            },
        }

        event = Event()
        event.set()
        rs: Result = stage.handler_execute({}, event=event)
        assert rs.status == CANCEL
        assert rs.context == {
            "parallel": {},
            "errors": {
                "name": "StageError",
                "message": (
                    "Stage was canceled from event that had set before stage "
                    "parallel execution."
                ),
            },
        }

        event = MockEvent(n=2)
        rs: Result = stage.handler_execute({}, event=event)
        assert rs.status == FAILED
        assert rs.context == {
            "parallel": {
                "branch02": {
                    "branch": "branch02",
                    "stages": {},
                    "errors": {
                        "name": "StageError",
                        "message": "Branch-Stage was canceled from event that had set before stage branch execution.",
                    },
                },
                "branch01": {
                    "branch": "branch01",
                    "stages": {
                        "0573477600": {"outputs": {}},
                        "skip-stage": {"outputs": {}, "skipped": True},
                    },
                },
            },
            "errors": {
                "branch02": {
                    "name": "StageError",
                    "message": "Branch-Stage was canceled from event that had set before stage branch execution.",
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
        "parallel": {
            "branch01": {
                "branch": "branch01",
                "stages": {
                    "6966382767": {
                        "outputs": {},
                        "errors": {
                            "name": "StageError",
                            "message": "Raise error inside parallel stage.",
                        },
                    }
                },
                "errors": {
                    "name": "StageError",
                    "message": "Branch-Stage was break because it has a sub stage, Raise Stage, failed without raise error.",
                },
            }
        },
        "errors": {
            "branch01": {
                "name": "StageError",
                "message": "Branch-Stage was break because it has a sub stage, Raise Stage, failed without raise error.",
            }
        },
    }
