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
        workflow.on[0].next(current_date).date,
        params={"asat-dt": datetime(2024, 10, 1)},
        queue=queue,
    )
    print(rs)


@mock.patch.object(Config, "enable_write_log", False)
def test_workflow_release_with_start_date():
    workflow: Workflow = Workflow.from_loader(name="wf-scheduling-common")
    start_date: datetime = datetime(2024, 1, 1, 1, 1)
    queue: list[datetime] = []
    rs: Result = workflow.release(
        workflow.on[0].next(start_date).date,
        params={"asat-dt": datetime(2024, 10, 1)},
        queue=queue,
    )
    print(rs)
