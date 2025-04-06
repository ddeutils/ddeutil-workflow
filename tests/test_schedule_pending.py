from datetime import timedelta
from unittest import mock

import pytest
from ddeutil.workflow.conf import Config
from ddeutil.workflow.scheduler import Schedule


@pytest.mark.schedule
@mock.patch.object(Config, "stop_boundary_delta", timedelta(minutes=1))
@mock.patch.object(Config, "enable_write_audit", False)
def test_schedule_pending():
    Schedule.from_conf("schedule-every-minute-wf").pending()
