from ddeutil.workflow.scheduler import Schedule
from ddeutil.workflow.utils import Loader


def test_scheduler_model():
    schedule = Schedule.from_loader("schedule-pipe")
    print(schedule)


def test_loader_find_schedule():
    for finding in Loader.find(Schedule, excluded=[]):
        print(finding)
