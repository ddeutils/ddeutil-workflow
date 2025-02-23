from datetime import timedelta
from unittest import mock

import pytest
from ddeutil.workflow.conf import Config
from ddeutil.workflow.result import Result
from ddeutil.workflow.scheduler import schedule_control


@pytest.mark.schedule
@mock.patch.object(Config, "stop_boundary_delta", timedelta(minutes=1))
@mock.patch.object(Config, "enable_write_log", False)
def test_scheduler_control():
    result: Result = schedule_control(["schedule-every-minute-wf"])
    assert result.status == 0
    assert result.context == {
        "schedules": ["schedule-every-minute-wf"],
        "threads": [
            {
                "name": "wf-scheduling-agent|202502231106",
                "start_date": result.context["threads"][0]["start_date"],
                "release_date": result.context["threads"][0]["release_date"],
            },
        ],
    }


@pytest.mark.schedule
@mock.patch.object(Config, "stop_boundary_delta", timedelta(minutes=3))
@mock.patch.object(Config, "enable_write_log", False)
def test_scheduler_control_multi_on():
    result: Result = schedule_control(["schedule-multi-on-wf"])
    assert result.status == 0
    print(result.context)


# FIXME: This testcase raise some problem.
@pytest.mark.schedule
@mock.patch.object(Config, "stop_boundary_delta", timedelta(minutes=0))
def test_scheduler_control_stop():
    result: Result = schedule_control(["schedule-every-minute-wf"])
    assert result.status == 0
    assert result.context == {
        "schedules": ["schedule-every-minute-wf"],
        "threads": [],
    }


@pytest.mark.schedule
@mock.patch.object(Config, "stop_boundary_delta", timedelta(minutes=2))
@mock.patch.object(Config, "enable_write_log", False)
def test_scheduler_control_parallel():
    result: Result = schedule_control(["schedule-every-minute-wf-parallel"])
    assert result.status == 0
    print(result.context)
