from unittest import mock

from ddeutil.workflow import Workflow
from ddeutil.workflow.conf import Config
from ddeutil.workflow.utils import Result


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_poke():
    wf = Workflow.from_loader(name="wf-scheduling-with-name", externals={})
    results: list[Result] = wf.poke(params={"name": "FOO"})
    for rs in results:
        assert "status" in rs.context["release"]
        assert "cron" in rs.context["release"]


def test_workflow_poke_no_on():
    workflow = Workflow.from_loader(name="wf-params-required")
    assert [] == workflow.poke(params={"name": "FOO"})


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_poke_with_release_params():
    wf = Workflow.from_loader(name="wf-scheduling", externals={})
    wf.poke(params={"asat-dt": "${{ release.logical_date }}"})
