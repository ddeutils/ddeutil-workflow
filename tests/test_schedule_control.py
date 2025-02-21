from datetime import timedelta
from unittest import mock

import pytest
from ddeutil.workflow.conf import Config
from ddeutil.workflow.scheduler import schedule_control


@pytest.mark.schedule
@mock.patch.object(Config, "stop_boundary_delta", timedelta(minutes=1))
@mock.patch.object(Config, "enable_write_log", False)
def test_schedule_control():
    rs = schedule_control(["schedule-every-minute-wf"])
    assert rs == ["schedule-every-minute-wf"]


@pytest.mark.schedule
@mock.patch.object(Config, "stop_boundary_delta", timedelta(minutes=3))
@mock.patch.object(Config, "enable_write_log", False)
def test_schedule_control_multi_on():
    rs = schedule_control(["schedule-multi-on-wf"])
    assert rs == ["schedule-multi-on-wf"]


# FIXME: This testcase raise some problem.
@pytest.mark.schedule
@mock.patch.object(Config, "stop_boundary_delta", timedelta(minutes=0))
def test_schedule_control_stop():
    rs = schedule_control(["schedule-every-minute-wf"])
    assert rs == ["schedule-every-minute-wf"]


@pytest.mark.schedule
@mock.patch.object(Config, "stop_boundary_delta", timedelta(minutes=2))
@mock.patch.object(Config, "enable_write_log", False)
def test_schedule_control_parallel():
    rs = schedule_control(["schedule-every-minute-wf-parallel"])
    assert rs == ["schedule-every-minute-wf-parallel"]
