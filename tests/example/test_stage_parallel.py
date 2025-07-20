from ddeutil.workflow import FAILED, SUCCESS, Result, Stage, Workflow

from ..utils import dump_yaml_context


def test_example_parallel_stage_exec_with_trigger(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_parallel_with_trigger.yml",
        data="""
        tmp-wf-parallel-trigger-task:
          type: Workflow
          params:
            branch: str
          jobs:
            first-job:
              stages:
                - name: "Echo"
                  id: hello
                  echo: "Run trigger with branch: ${{ params.branch }}"
        tmp-wf-parallel-trigger:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Start run parallel stage"
                  id: parallel-stage
                  parallel:
                    trigger-branch:
                      - name: "Stage trigger"
                        trigger: tmp-wf-parallel-trigger-task
                        params:
                          branch: ${{ branch }}
        """,
    ):
        workflow = Workflow.from_conf("tmp-wf-parallel-trigger")
        stage: Stage = workflow.job("first-job").stage("parallel-stage")
        rs = stage.execute(params={})
        assert rs.status == SUCCESS
        assert rs.context == {
            "status": SUCCESS,
            "workers": 2,
            "parallel": {
                "trigger-branch": {
                    "status": SUCCESS,
                    "branch": "trigger-branch",
                    "stages": {
                        "8713259197": {
                            "outputs": {
                                "params": {"branch": "trigger-branch"},
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
                }
            },
        }


def test_example_parallel_stage_exec_with_trigger_raise(test_path):
    with dump_yaml_context(
        test_path
        / "conf/demo/01_99_wf_test_wf_parallel_with_trigger-raise.yml",
        data="""
        tmp-wf-parallel-trigger-raise-task:
          type: Workflow
          params:
            branch: str
          jobs:
            first-job:
              stages:
                - name: "Echo"
                  id: raise-stage
                  raise: "Raise trigger with branch: ${{ params.branch }}"

        tmp-wf-parallel-trigger-raise:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Start run parallel stage"
                  id: parallel-stage
                  parallel:
                    branch01:
                      - name: "Stage trigger"
                        trigger: tmp-wf-parallel-trigger-raise-task
                        params:
                          branch: ${{ branch }}
                    branch02:
                      - name: "Stage Echo"
                        echo: "Do not raise trigger error: ${{ branch }}"
                      - name: Raise Stage
                        raise: "Raise with branch: ${{ branch }}"
        """,
    ):
        workflow = Workflow.from_conf("tmp-wf-parallel-trigger-raise")
        stage: Stage = workflow.job("first-job").stage("parallel-stage")
        rs: Result = stage.execute({})
        assert rs.status == FAILED
        assert rs.context == {
            "status": FAILED,
            "workers": 2,
            "parallel": {
                "branch02": {
                    "status": FAILED,
                    "branch": "branch02",
                    "stages": {
                        "7741720823": {"outputs": {}, "status": SUCCESS},
                        "6966382767": {
                            "outputs": {},
                            "errors": {
                                "name": "StageError",
                                "message": "Raise with branch: branch02",
                            },
                            "status": FAILED,
                        },
                    },
                    "errors": {
                        "name": "StageError",
                        "message": "Branch execution was break because its nested-stage, 'Raise Stage', failed.",
                    },
                },
                "branch01": {
                    "status": FAILED,
                    "branch": "branch01",
                    "stages": {
                        "8713259197": {
                            "outputs": {},
                            "errors": {
                                "name": "StageNestedError",
                                "message": "Trigger workflow was failed with:\nJob execution, 'first-job', was failed.",
                            },
                            "status": FAILED,
                        }
                    },
                    "errors": {
                        "name": "StageError",
                        "message": "Branch execution was break because its nested-stage, 'Stage trigger', failed.",
                    },
                },
            },
            "errors": {
                "branch02": {
                    "name": "StageError",
                    "message": "Branch execution was break because its nested-stage, 'Raise Stage', failed.",
                },
                "branch01": {
                    "name": "StageError",
                    "message": "Branch execution was break because its nested-stage, 'Stage trigger', failed.",
                },
            },
        }


def test_example_parallel_stage_exec_with_trigger_raise_bug(test_path):
    with dump_yaml_context(
        test_path
        / "conf/demo/01_99_wf_test_wf_parallel_with_trigger-raise.yml",
        data="""
        tmp-wf-parallel-trigger-raise-task:
          type: Workflow
          params:
            branch: str
          jobs:
            first-job:
              stages:
                - name: "Echo"
                  id: raise-stage
                  raise: "Raise trigger with branch: ${{ params.branch }}"

        tmp-wf-parallel-trigger-raise:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Start run parallel stage"
                  id: parallel-stage
                  parallel:
                    branch01:
                      - name: "Stage trigger 1"
                        trigger: "tmp-wf-parallel-trigger-raise-task"
                        params:
                          branch: ${{ branch }}
                    branch02:
                      - name: "Stage trigger 2"
                        trigger: "tmp-wf-parallel-trigger-raise-task"
                        params:
                          branch: ${{ branch }}
        """,
    ):
        workflow = Workflow.from_conf("tmp-wf-parallel-trigger-raise")
        stage: Stage = workflow.job("first-job").stage("parallel-stage")
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
                        "2579951921": {
                            "outputs": {},
                            "errors": {
                                "name": "StageNestedError",
                                "message": "Trigger workflow was failed with:\nJob execution, 'first-job', was failed.",
                            },
                            "status": FAILED,
                        }
                    },
                    "errors": {
                        "name": "StageError",
                        "message": "Branch execution was break because its nested-stage, 'Stage trigger 1', failed.",
                    },
                },
                "branch02": {
                    "status": FAILED,
                    "branch": "branch02",
                    "stages": {
                        "4773288548": {
                            "outputs": {},
                            "errors": {
                                "name": "StageNestedError",
                                "message": "Trigger workflow was failed with:\nJob execution, 'first-job', was failed.",
                            },
                            "status": FAILED,
                        }
                    },
                    "errors": {
                        "name": "StageError",
                        "message": "Branch execution was break because its nested-stage, 'Stage trigger 2', failed.",
                    },
                },
            },
            "errors": {
                "branch01": {
                    "name": "StageError",
                    "message": "Branch execution was break because its nested-stage, 'Stage trigger 1', failed.",
                },
                "branch02": {
                    "name": "StageError",
                    "message": "Branch execution was break because its nested-stage, 'Stage trigger 2', failed.",
                },
            },
        }
