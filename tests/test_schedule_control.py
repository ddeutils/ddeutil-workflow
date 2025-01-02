from datetime import timedelta
from unittest import mock

from ddeutil.workflow.conf import config
from ddeutil.workflow.scheduler import schedule_control


@mock.patch.object(config, "stop_boundary_delta", timedelta(minutes=1))
def test_schedule_control():
    rs = schedule_control(["schedule-common-wf"])
    print(rs)


@mock.patch.object(config, "stop_boundary_delta", timedelta(minutes=1))
def test_schedule_control_stop():
    rs = schedule_control(["schedule-common-wf"])
    print(rs)
