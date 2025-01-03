from datetime import timedelta
from unittest import mock

from ddeutil.workflow.conf import Config, config
from ddeutil.workflow.scheduler import schedule_control


@mock.patch.object(config, "stop_boundary_delta", timedelta(minutes=2))
@mock.patch.object(Config, "enable_write_log", False)
def test_schedule_control():
    rs = schedule_control(["schedule-every-minute-wf"])
    print(rs)
