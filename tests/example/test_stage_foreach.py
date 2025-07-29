from ddeutil.workflow import CANCEL, FAILED, SUCCESS, Result, Stage, Workflow

from ..utils import dump_yaml_context


def test_example_foreach_stage_exec_with_trigger(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_foreach_with_trigger.yml",
        data="""
        tmp-wf-foreach-trigger-task:
          type: Workflow
          params:
            item: int
          jobs:
            first-job:
              stages:
                - name: "Echo"
                  id: hello
                  echo: "Run trigger with item: ${{ params.item }}"
        tmp-wf-foreach-trigger:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Start run for-each stage"
                  id: foreach-stage
                  foreach: [1, 2]
                  stages:
                    - name: "Stage trigger"
                      trigger: tmp-wf-foreach-trigger-task
                      params:
                        item: ${{ item }}
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-foreach-trigger")
        stage: Stage = workflow.job("first-job").stage("foreach-stage")
        rs = stage.set_outputs(stage.execute({}).context, to={})
        assert rs == {
            "stages": {
                "foreach-stage": {
                    "status": SUCCESS,
                    "outputs": {
                        "items": [1, 2],
                        "foreach": {
                            1: {
                                "status": SUCCESS,
                                "item": 1,
                                "stages": {
                                    "8713259197": {
                                        "status": SUCCESS,
                                        "outputs": {
                                            "params": {"item": 1},
                                            "jobs": {
                                                "first-job": {
                                                    "status": SUCCESS,
                                                    "stages": {
                                                        "hello": {
                                                            "status": SUCCESS,
                                                            "outputs": {},
                                                        }
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                            2: {
                                "status": SUCCESS,
                                "item": 2,
                                "stages": {
                                    "8713259197": {
                                        "status": SUCCESS,
                                        "outputs": {
                                            "params": {"item": 2},
                                            "jobs": {
                                                "first-job": {
                                                    "status": SUCCESS,
                                                    "stages": {
                                                        "hello": {
                                                            "status": SUCCESS,
                                                            "outputs": {},
                                                        }
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        }


def test_example_foreach_stage_exec_with_trigger_raise(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_foreach_with_trigger_raise.yml",
        data="""
        tmp-wf-foreach-trigger-task-raise:
          type: Workflow
          params:
            item: int
          jobs:
            first-job:
              stages:
                - name: "Echo"
                  id: raise-stage
                  raise: "Raise trigger with item: ${{ params.item }}"

        tmp-wf-foreach-trigger-raise:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Raise run for-each stage"
                  id: foreach-raise
                  foreach: [1, 2]
                  stages:
                    - name: "Stage trigger for raise"
                      trigger: tmp-wf-foreach-trigger-task-raise
                      params:
                        item: ${{ item }}
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-foreach-trigger-raise")
        stage: Stage = workflow.job("first-job").stage("foreach-raise")
        rs: Result = stage.execute({})
        assert rs.status == FAILED
        assert_status: list[bool] = []
        try:
            assert rs.context == {
                "status": FAILED,
                "items": [1, 2],
                "foreach": {
                    1: {
                        "status": FAILED,
                        "item": 1,
                        "stages": {
                            "2827845371": {
                                "outputs": {
                                    "params": {"item": 1},
                                    "jobs": {
                                        "first-job": {
                                            "status": FAILED,
                                            "stages": {
                                                "raise-stage": {
                                                    "outputs": {},
                                                    "errors": {
                                                        "name": "StageError",
                                                        "message": "Raise trigger with item: 1",
                                                    },
                                                    "status": FAILED,
                                                }
                                            },
                                            "errors": {
                                                "name": "JobError",
                                                "message": "Strategy execution was break because its nested-stage, 'raise-stage', failed.",
                                            },
                                        }
                                    },
                                },
                                "errors": {
                                    "name": "StageError",
                                    "message": "Trigger workflow was failed with:\nJob execution, 'first-job', was failed.",
                                },
                                "status": FAILED,
                            }
                        },
                        "errors": {
                            "name": "StageError",
                            "message": "Break item: 1 because nested stage: 'Stage trigger for raise', failed.",
                        },
                    },
                    2: {
                        "status": CANCEL,
                        "item": 2,
                        "stages": {
                            "2827845371": {
                                "outputs": {"params": {"item": 2}, "jobs": {}},
                                "errors": {
                                    "name": "StageCancelError",
                                    "message": "Trigger workflow was cancel.",
                                },
                                "status": CANCEL,
                            }
                        },
                        "errors": {
                            "name": "StageCancelError",
                            "message": "Cancel item: 2 after end nested process.",
                        },
                    },
                },
                "errors": {
                    2: {
                        "name": "StageCancelError",
                        "message": "Cancel item: 2 after end nested process.",
                    },
                    1: {
                        "name": "StageError",
                        "message": "Break item: 1 because nested stage: 'Stage trigger for raise', failed.",
                    },
                },
            }
            assert_status.append(True)
        except AssertionError:
            assert_status.append(False)

        try:
            assert rs.context == {
                "status": FAILED,
                "items": [1, 2],
                "foreach": {
                    1: {
                        "status": FAILED,
                        "item": 1,
                        "stages": {
                            "2827845371": {
                                "outputs": {
                                    "params": {"item": 1},
                                    "jobs": {
                                        "first-job": {
                                            "status": FAILED,
                                            "stages": {
                                                "raise-stage": {
                                                    "outputs": {},
                                                    "errors": {
                                                        "name": "StageError",
                                                        "message": "Raise trigger with item: 1",
                                                    },
                                                    "status": FAILED,
                                                }
                                            },
                                            "errors": {
                                                "name": "JobError",
                                                "message": "Strategy execution was break because its nested-stage, 'raise-stage', failed.",
                                            },
                                        }
                                    },
                                },
                                "errors": {
                                    "name": "StageError",
                                    "message": "Trigger workflow was failed with:\nJob execution, 'first-job', was failed.",
                                },
                                "status": FAILED,
                            }
                        },
                        "errors": {
                            "name": "StageError",
                            "message": "Break item: 1 because nested stage: 'Stage trigger for raise', failed.",
                        },
                    },
                    2: {
                        "status": CANCEL,
                        "item": 2,
                        "stages": {},
                        "errors": {
                            "name": "StageCancelError",
                            "message": "Cancel item: 2 before start nested process.",
                        },
                    },
                },
                "errors": {
                    2: {
                        "name": "StageCancelError",
                        "message": "Cancel item: 2 before start nested process.",
                    },
                    1: {
                        "name": "StageError",
                        "message": "Break item: 1 because nested stage: 'Stage trigger for raise', failed.",
                    },
                },
            }
            assert_status.append(True)
        except AssertionError:
            assert_status.append(False)

        assert len(assert_status) == 2
        assert any(assert_status), f"{rs.context}"


def test_example_foreach_stage_exec_nested_foreach_and_trigger(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_foreach_with_trigger.yml",
        data="""
        tmp-wf-foreach-nested-trigger-task:
          type: Workflow
          params:
            item: int
          jobs:
            first-job:
              stages:
                - name: "Echo"
                  id: hello
                  echo: "Trigger Item: ${{ params.item }}"

        tmp-wf-foreach-nested-trigger:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Start run for-each stage"
                  id: foreach-stage
                  foreach: [1, 2]
                  stages:

                    - name: "Start run for-each stage inside foreach"
                      id: foreach-nested
                      foreach: [3, 4]
                      stages:
                        - name: "Check params"

                        - name: "Stage trigger"
                          id: trigger-stage
                          trigger: tmp-wf-foreach-nested-trigger-task
                          params:
                            item: ${{ item }}
        """,
    ):
        workflow = Workflow.from_conf(
            name="tmp-wf-foreach-nested-trigger",
            extras={"stage_default_id": False},
        )
        stage: Stage = workflow.job("first-job").stage("foreach-stage")
        rs: Result = stage.execute({})
        assert rs.status == SUCCESS
        assert rs.context == {
            "status": SUCCESS,
            "items": [1, 2],
            "foreach": {
                1: {
                    "status": SUCCESS,
                    "item": 1,
                    "stages": {
                        "foreach-nested": {
                            "outputs": {
                                "items": [3, 4],
                                "foreach": {
                                    3: {
                                        "status": SUCCESS,
                                        "item": 3,
                                        "stages": {
                                            "trigger-stage": {
                                                "outputs": {
                                                    "params": {"item": 3},
                                                    "jobs": {
                                                        "first-job": {
                                                            "status": SUCCESS,
                                                            "stages": {
                                                                "hello": {
                                                                    "outputs": {},
                                                                    "status": SUCCESS,
                                                                }
                                                            },
                                                        }
                                                    },
                                                },
                                                "status": SUCCESS,
                                            }
                                        },
                                    },
                                    4: {
                                        "status": SUCCESS,
                                        "item": 4,
                                        "stages": {
                                            "trigger-stage": {
                                                "outputs": {
                                                    "params": {"item": 4},
                                                    "jobs": {
                                                        "first-job": {
                                                            "status": SUCCESS,
                                                            "stages": {
                                                                "hello": {
                                                                    "outputs": {},
                                                                    "status": SUCCESS,
                                                                }
                                                            },
                                                        }
                                                    },
                                                },
                                                "status": SUCCESS,
                                            }
                                        },
                                    },
                                },
                            },
                            "status": SUCCESS,
                        }
                    },
                },
                2: {
                    "status": SUCCESS,
                    "item": 2,
                    "stages": {
                        "foreach-nested": {
                            "outputs": {
                                "items": [3, 4],
                                "foreach": {
                                    3: {
                                        "status": SUCCESS,
                                        "item": 3,
                                        "stages": {
                                            "trigger-stage": {
                                                "outputs": {
                                                    "params": {"item": 3},
                                                    "jobs": {
                                                        "first-job": {
                                                            "status": SUCCESS,
                                                            "stages": {
                                                                "hello": {
                                                                    "outputs": {},
                                                                    "status": SUCCESS,
                                                                }
                                                            },
                                                        }
                                                    },
                                                },
                                                "status": SUCCESS,
                                            }
                                        },
                                    },
                                    4: {
                                        "status": SUCCESS,
                                        "item": 4,
                                        "stages": {
                                            "trigger-stage": {
                                                "outputs": {
                                                    "params": {"item": 4},
                                                    "jobs": {
                                                        "first-job": {
                                                            "status": SUCCESS,
                                                            "stages": {
                                                                "hello": {
                                                                    "outputs": {},
                                                                    "status": SUCCESS,
                                                                }
                                                            },
                                                        }
                                                    },
                                                },
                                                "status": SUCCESS,
                                            }
                                        },
                                    },
                                },
                            },
                            "status": SUCCESS,
                        }
                    },
                },
            },
        }
