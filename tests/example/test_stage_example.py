import os
import shutil
from datetime import datetime

from ddeutil.workflow import SUCCESS, Result, Workflow


def test_example_stage_exec_nested_trigger(test_path):
    if (test_path / "example/logs").exists():
        shutil.rmtree(test_path / "example/logs")

    workflow = Workflow.from_conf(
        "stream-workflow",
        extras={
            "trace_path": test_path / "example/logs/trace",
            "audit_path": test_path / "example/logs/audit",
            "enable_write_log": True,
            "enable_write_audit": True,
        },
    )

    os.environ["EXAMPLE_SECRET_TOKEN"] = "very-secret-value"

    rs: Result = workflow.release(
        datetime(2025, 5, 10, 12, 35),
        params={
            "run-mode": "N",
            "name": "starter-stream-name",
        },
    )
    assert rs.status == SUCCESS
    print(rs)
