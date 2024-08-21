from datetime import datetime

from ddeutil.workflow.log import FileLog


def test_log_file():
    log = FileLog.model_validate(
        obj={
            "name": "pipe-scheduling",
            "on": "*/2 * * * *",
            "release": datetime(2024, 1, 1, 1),
            "context": {
                "params": {"name": "foo"},
            },
            "parent_run_id": None,
            "run_id": "558851633820240817184358131811",
            "update": datetime.now(),
        },
    )
    log.save()


def test_log_file_latest():
    rs = FileLog.latest_point(
        name="pipe-scheduling",
        queue=[datetime(2024, 8, 21, 11, 5)],
    )
    assert rs == datetime(2024, 8, 21, 11, 5)

    rs = FileLog.latest_point(
        name="pipe-scheduling-not-exists",
        queue=[datetime(2024, 8, 21, 11, 5)],
    )
    assert rs == datetime(2024, 8, 21, 11, 5)
