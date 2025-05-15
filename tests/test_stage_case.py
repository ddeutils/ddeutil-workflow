from ddeutil.workflow import (
    FAILED,
    Result,
    Workflow,
)
from ddeutil.workflow.stages import Stage

from .utils import dump_yaml_context


def test_case_stage_exec(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_case_match.yml",
        data="""
        tmp-wf-case-match:
          type: Workflow
          params: { name: str }
          jobs:
            first-job:
              stages:
                - name: "Start run case-match stage"
                  id: case-stage
                  case: ${{ params.name }}
                  match:
                    - case: "bar"
                      stages:
                        - name: Match name with Bar
                          echo: Hello ${{ params.name }}

                    - case: "foo"
                      stages:
                        - name: Match name with For
                          echo: Hello ${{ params.name }}

                    - case: "_"
                      stages:
                        - name: Else stage
                          echo: Not match any case.
                - name: "Stage raise not has else condition"
                  id: raise-else
                  case: ${{ params.name }}
                  match:
                    - case: "bar"
                      stages:
                        - name: Match name with Bar
                          echo: Hello ${{ params.name }}
                - name: "Stage skip not has else condition"
                  id: not-else
                  case: ${{ params.name }}
                  skip-not-match: true
                  match:
                    - case: "bar"
                      stages:
                        - name: Match name with Bar
                          echo: Hello ${{ params.name }}
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-case-match")
        stage: Stage = workflow.job("first-job").stage("case-stage")
        rs = stage.set_outputs(
            stage.handler_execute({"params": {"name": "bar"}}).context, to={}
        )
        assert rs == {
            "stages": {
                "case-stage": {
                    "outputs": {
                        "case": "bar",
                        "stages": {"3616274431": {"outputs": {}}},
                    },
                },
            },
        }

        rs = stage.set_outputs(
            stage.handler_execute({"params": {"name": "foo"}}).context, to={}
        )
        assert rs == {
            "stages": {
                "case-stage": {
                    "outputs": {
                        "case": "foo",
                        "stages": {"4740784512": {"outputs": {}}},
                    }
                }
            }
        }

        rs = stage.set_outputs(
            stage.handler_execute({"params": {"name": "test"}}).context, to={}
        )
        assert rs == {
            "stages": {
                "case-stage": {
                    "outputs": {
                        "case": "_",
                        "stages": {"5883888894": {"outputs": {}}},
                    }
                }
            }
        }

        # NOTE: Raise because else condition does not set.
        stage: Stage = workflow.job("first-job").stage("raise-else")
        rs: Result = stage.handler_execute({"params": {"name": "test"}})
        assert rs.status == FAILED
        assert rs.context == {
            "errors": {
                "name": "StageError",
                "message": "This stage does not set else for support not match any case.",
            }
        }

        stage: Stage = workflow.job("first-job").stage("not-else")
        rs = stage.set_outputs(
            stage.handler_execute({"params": {"name": "test"}}).context, to={}
        )
        assert rs == {
            "stages": {
                "not-else": {
                    "outputs": {},
                    "errors": {
                        "name": "StageError",
                        "message": (
                            "Case-Stage was canceled because it does not match "
                            "any case and else condition does not set too."
                        ),
                    },
                }
            }
        }
