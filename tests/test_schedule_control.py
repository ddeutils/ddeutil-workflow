from datetime import timedelta
from unittest import mock

from ddeutil.workflow.conf import Config, config
from ddeutil.workflow.scheduler import schedule_control


@mock.patch.object(config, "stop_boundary_delta", timedelta(minutes=1))
@mock.patch.object(Config, "enable_write_log", False)
def test_schedule_control():
    rs = schedule_control(["schedule-every-minute-wf"])
    assert rs == ["schedule-every-minute-wf"]


@mock.patch.object(config, "stop_boundary_delta", timedelta(minutes=3))
@mock.patch.object(Config, "enable_write_log", False)
def test_schedule_control_multi_on():
    rs = schedule_control(["schedule-multi-on-wf"])
    assert rs == ["schedule-multi-on-wf"]


@mock.patch.object(config, "stop_boundary_delta", timedelta(minutes=0))
def test_schedule_control_stop():
    rs = schedule_control(["schedule-every-minute-wf"])
    assert rs == ["schedule-every-minute-wf"]


@mock.patch.object(config, "stop_boundary_delta", timedelta(minutes=2))
@mock.patch.object(Config, "enable_write_log", False)
def test_schedule_control_parallel():
    rs = schedule_control(["schedule-every-minute-wf-parallel"])
    assert rs == ["schedule-every-minute-wf-parallel"]
