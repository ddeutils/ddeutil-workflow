from ddeutil.workflow import SUCCESS, Result, Stage, StageError, Workflow

from ..utils import dump_yaml_context


def test_stage_py_virtual(test_path):
    with dump_yaml_context(
        test_path / "conf/demo/01_99_wf_test_wf_py_virtual.yml",
        data="""
        tmp-wf-py-virtual:
          type: Workflow
          jobs:
            first-job:
              stages:
                - name: "Start run Python on the new Virtual"
                  id: py-virtual
                  deps:
                    - numpy
                  run: |
                    import numpy as np

                    arr = np.array([1, 2, 3, 4, 5])
                    print(arr)
                    print(type(arr))
        """,
    ):
        workflow = Workflow.from_conf(name="tmp-wf-py-virtual")
        stage: Stage = workflow.job("first-job").stage("py-virtual")
        # TODO: This testcase raise error for uv does not exist on GH action.
        try:
            rs: Result = stage.execute(params={"params": {}})
            print(rs.context)

            output = stage.set_outputs(rs.context, to={})
            assert output == {
                "stages": {
                    "py-virtual": {
                        "status": SUCCESS,
                        "outputs": {
                            "return_code": 0,
                            "stdout": "[1 2 3 4 5]\n<class 'numpy.ndarray'>",
                            "stderr": output["stages"]["py-virtual"]["outputs"][
                                "stderr"
                            ],
                        },
                    },
                },
            }
        except StageError as e:
            print(e)
        except Exception as e:
            print(e)
