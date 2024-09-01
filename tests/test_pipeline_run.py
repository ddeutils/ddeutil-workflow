import ddeutil.workflow as wf
from ddeutil.workflow.utils import Result


def test_pipe_run_py():
    workflow = wf.Workflow.from_loader(
        name="wf-run-python",
        externals={},
    )
    rs: Result = workflow.execute(
        params={
            "author-run": "Local Workflow",
            "run-date": "2024-01-01",
        }
    )
    assert 0 == rs.status
    assert {"final-job", "first-job", "second-job"} == set(
        rs.context["jobs"].keys()
    )
    assert {"printing", "setting-x"} == set(
        rs.context["jobs"]["first-job"]["stages"].keys()
    )
