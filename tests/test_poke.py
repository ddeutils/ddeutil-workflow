from ddeutil.workflow import Workflow


def test_pipeline_poke():
    wf = Workflow.from_loader(name="wf-run-matrix-fail-fast", externals={})
    results = wf.poke(params={"name": "FOO"})
    for rs in results:
        print(rs.context["poking"])


def test_pipe_poke_with_release_params():
    wf = Workflow.from_loader(name="wf-scheduling", externals={})
    wf.poke(params={"asat-dt": "${{ release.logical_date }}"})
