from ddeutil.workflow import Workflow


def test_workflow_poke_no_on():
    workflow = Workflow.from_loader(name="wf-params-required")
    assert [] == workflow.poke(params={"name": "FOO"})


def test_workflow_poke():
    wf = Workflow.from_loader(name="wf-run-matrix-fail-fast", externals={})
    results = wf.poke(params={"name": "FOO"})
    for rs in results:
        print(rs.context["poking"])


def test_workflow_poke_with_release_params():
    wf = Workflow.from_loader(name="wf-scheduling", externals={})
    wf.poke(params={"asat-dt": "${{ release.logical_date }}"})