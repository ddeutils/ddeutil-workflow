import time
from typing import Any, TypedDict, cast

import pytest
from ddeutil.workflow import SUCCESS, WAIT, Result, Status
from typing_extensions import NotRequired


class Context(TypedDict):
    params: dict[str, Any]
    status: Status
    jobs: dict[str, Any]
    errors: NotRequired[dict[str, Any]]


class StageContext(TypedDict):
    status: Status
    context: NotRequired[dict[str, Any]]


def stage_exec(params: Context, run_id: str) -> Result:
    stage_id = "stage-01"
    context: StageContext = {"status": WAIT}
    print(context)
    time.sleep(0.25)
    parent_run_id = run_id
    run_id = f"1001{parent_run_id}"
    params["jobs"].update({stage_id: {"outputs": {"records": 10}}})
    return Result(
        run_id=run_id,
        parent_run_id=parent_run_id,
        status=SUCCESS,
        context=cast(dict, params),
    )


@pytest.fixture(scope="function")
def params() -> Context:
    return {
        "params": {"foo": "bar"},
        "jobs": {},
        "status": WAIT,
    }


def test_stage_context(params):
    print()
    rs = stage_exec(params=params, run_id="A")
    print(rs)

    params["jobs"].update({"update": "baz"})
    print(rs)
