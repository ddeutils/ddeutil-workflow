from datetime import datetime
from unittest import mock

from ddeutil.workflow import Workflow
from ddeutil.workflow.conf import Config
from ddeutil.workflow.utils import Result


def test_workflow_release():
    workflow: Workflow = Workflow.from_loader(name="wf-scheduling-common")
    current_date: datetime = datetime.now().replace(second=0, microsecond=0)
    queue: list[datetime] = [workflow.on[0].generate(current_date).next]

    rs: Result = workflow.release(
        workflow.on[0].next(current_date),
        params={"asat-dt": datetime(2024, 10, 1)},
        queue=queue,
    )
    assert rs.status == 0
    assert len(queue) == 1


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_release_with_start_date():
    workflow: Workflow = Workflow.from_loader(name="wf-scheduling-common")
    start_date: datetime = datetime(2024, 1, 1, 1, 1)
    queue: list[datetime] = []
    rs: Result = workflow.release(
        workflow.on[0].next(start_date),
        params={"asat-dt": datetime(2024, 10, 1)},
        queue=queue,
    )
    assert rs.status == 0
    assert len(queue) == 0


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_poke():
    workflow = Workflow.from_loader(name="wf-scheduling-with-name")

    # NOTE: Poking with the current datetime.
    results: list[Result] = workflow.poke(params={"name": "FOO"})
    for rs in results:
        assert "status" in rs.context["release"]
        assert "cron" in rs.context["release"]


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_poke_with_start_date():
    workflow = Workflow.from_loader(name="wf-scheduling-with-name")

    # NOTE: Poking with specific start datetime.
    results: list[Result] = workflow.poke(
        start_date=datetime(2024, 1, 1, 0),
        params={"name": "FOO"},
    )
    for rs in results:
        assert "status" in rs.context["release"]
        assert "cron" in rs.context["release"]


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_poke_no_on():
    workflow = Workflow.from_loader(name="wf-params-required")
    assert [] == workflow.poke(params={"name": "FOO"})


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_poke_with_release_params():
    wf = Workflow.from_loader(name="wf-scheduling", externals={})
    wf.poke(params={"asat-dt": "${{ release.logical_date }}"})
