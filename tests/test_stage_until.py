from ddeutil.workflow import Stage, Workflow

from .utils import dump_yaml_context


def test_until_stage_exec(test_path):
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
        rs = stage.set_outputs(stage.handler_execute({}).context, to={})
        assert rs == {
            "stages": {
                "until-stage": {
                    "outputs": {
                        "until": {
                            1: {
                                "loop": 1,
                                "item": 1,
                                "stages": {
                                    "2709471980": {"outputs": {}},
                                    "9263488742": {
                                        "outputs": {},
                                        "skipped": True,
                                    },
                                    "3635623619": {"outputs": {"item": 2}},
                                },
                            },
                            2: {
                                "loop": 2,
                                "item": 2,
                                "stages": {
                                    "2709471980": {"outputs": {}},
                                    "9263488742": {
                                        "outputs": {},
                                        "skipped": True,
                                    },
                                    "3635623619": {"outputs": {"item": 3}},
                                },
                            },
                            3: {
                                "loop": 3,
                                "item": 3,
                                "stages": {
                                    "2709471980": {"outputs": {}},
                                    "9263488742": {
                                        "outputs": {},
                                        "skipped": True,
                                    },
                                    "3635623619": {"outputs": {"item": 4}},
                                },
                            },
                            4: {
                                "loop": 4,
                                "item": 4,
                                "stages": {
                                    "2709471980": {"outputs": {}},
                                    "9263488742": {"outputs": {}},
                                    "3635623619": {"outputs": {"item": 5}},
                                },
                            },
                        }
                    }
                }
            }
        }
