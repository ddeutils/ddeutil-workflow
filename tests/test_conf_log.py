from datetime import datetime

from ddeutil.workflow.conf import FileLog


def test_log_file():
    log = FileLog.model_validate(
        obj={
            "name": "wf-scheduling",
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
    log.save(excluded=None)


def test_log_find_logs():
    print(next(FileLog.find_logs(name="wf-scheduling")))
