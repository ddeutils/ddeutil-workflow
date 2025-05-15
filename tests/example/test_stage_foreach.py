from ddeutil.workflow import SUCCESS, Result, Stage, Workflow

from ..utils import dump_yaml_context


def test_foreach_stage_exec_with_trigger(test_path):
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
        rs = stage.set_outputs(stage.handler_execute({}).context, to={})
        assert rs == {
            "stages": {
                "foreach-stage": {
                    "outputs": {
                        "items": [1, 2],
                        "foreach": {
                            1: {
                                "item": 1,
                                "stages": {
                                    "8713259197": {
                                        "outputs": {
                                            "params": {"item": 1},
                                            "jobs": {
                                                "first-job": {
                                                    "stages": {
                                                        "hello": {"outputs": {}}
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                            2: {
                                "item": 2,
                                "stages": {
                                    "8713259197": {
                                        "outputs": {
                                            "params": {"item": 2},
                                            "jobs": {
                                                "first-job": {
                                                    "stages": {
                                                        "hello": {"outputs": {}}
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


def test_foreach_stage_exec_with_trigger_raise(test_path):
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
        rs = stage.set_outputs(stage.handler_execute({}).context, to={})
        assert rs == {
            "stages": {
                "foreach-raise": {
                    "outputs": {
                        "items": [1, 2],
                        "foreach": {
                            1: {
                                "item": 1,
                                "stages": {},
                                "errors": {
                                    "name": "StageError",
                                    "message": "Trigger workflow return `FAILED` status with:\nJob, 'first-job', return `FAILED` status.",
                                },
                            },
                            2: {
                                "item": 2,
                                "stages": {},
                                "errors": {
                                    "name": "StageError",
                                    "message": "Trigger workflow return `FAILED` status with:\nWorkflow job was canceled because event was set.",
                                },
                            },
                        },
                    },
                    "errors": {
                        1: {
                            "name": "StageError",
                            "message": "Trigger workflow return `FAILED` status with:\nJob, 'first-job', return `FAILED` status.",
                        },
                        2: {
                            "name": "StageError",
                            "message": "Trigger workflow return `FAILED` status with:\nWorkflow job was canceled because event was set.",
                        },
                    },
                }
            }
        }


def test_foreach_stage_exec_nested_foreach_and_trigger(test_path):
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
        rs: Result = stage.handler_execute({})
        assert rs.status == SUCCESS
        assert rs.context == {
            "items": [1, 2],
            "foreach": {
                1: {
                    "item": 1,
                    "stages": {
                        "foreach-nested": {
                            "outputs": {
                                "items": [3, 4],
                                "foreach": {
                                    3: {
                                        "item": 3,
                                        "stages": {
                                            "trigger-stage": {
                                                "outputs": {
                                                    "params": {"item": 3},
                                                    "jobs": {
                                                        "first-job": {
                                                            "stages": {
                                                                "hello": {
                                                                    "outputs": {}
                                                                }
                                                            }
                                                        }
                                                    },
                                                }
                                            }
                                        },
                                    },
                                    4: {
                                        "item": 4,
                                        "stages": {
                                            "trigger-stage": {
                                                "outputs": {
                                                    "params": {"item": 4},
                                                    "jobs": {
                                                        "first-job": {
                                                            "stages": {
                                                                "hello": {
                                                                    "outputs": {}
                                                                }
                                                            }
                                                        }
                                                    },
                                                }
                                            }
                                        },
                                    },
                                },
                            }
                        }
                    },
                },
                2: {
                    "item": 2,
                    "stages": {
                        "foreach-nested": {
                            "outputs": {
                                "items": [3, 4],
                                "foreach": {
                                    3: {
                                        "item": 3,
                                        "stages": {
                                            "trigger-stage": {
                                                "outputs": {
                                                    "params": {"item": 3},
                                                    "jobs": {
                                                        "first-job": {
                                                            "stages": {
                                                                "hello": {
                                                                    "outputs": {}
                                                                }
                                                            }
                                                        }
                                                    },
                                                }
                                            }
                                        },
                                    },
                                    4: {
                                        "item": 4,
                                        "stages": {
                                            "trigger-stage": {
                                                "outputs": {
                                                    "params": {"item": 4},
                                                    "jobs": {
                                                        "first-job": {
                                                            "stages": {
                                                                "hello": {
                                                                    "outputs": {}
                                                                }
                                                            }
                                                        }
                                                    },
                                                }
                                            }
                                        },
                                    },
                                },
                            }
                        }
                    },
                },
            },
        }
