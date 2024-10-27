from ddeutil.workflow import Workflow
from ddeutil.workflow.utils import Result


def test_workflow_poke_no_on():
    workflow = Workflow.from_loader(name="wf-params-required")
    assert [] == workflow.poke(params={"name": "FOO"})


def test_workflow_poke():
    wf = Workflow.from_loader(name="wf-run-matrix-fail-fast", externals={})
    results: list[Result] = wf.poke(params={"name": "FOO"})
    for rs in results:
        assert "status" in rs.context["release"]
        assert "cron" in rs.context["release"]

    wf.poke(params={"name": "FOO"})


def test_workflow_poke_with_release_params():
    wf = Workflow.from_loader(name="wf-scheduling", externals={})
    wf.poke(params={"asat-dt": "${{ release.logical_date }}"})
