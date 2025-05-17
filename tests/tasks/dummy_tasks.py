# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ddeutil.workflow.result import Result
from ddeutil.workflow.reusables import tag
from pydantic import BaseModel


@tag("demo", alias="simple-task")
def simple_task(
    source: str,
    sink: str,
    result: Result,
    conversion: Optional[dict[str, Any]] = None,
) -> dict[str, int]:
    """Simple Task function."""
    result.trace.info("[CALLER]: Start Simple Task")
    conversion: dict[str, Any] = conversion or {}
    result.trace.info(
        f"Information||>source: {source}||>sink: {sink}||"
        f">conversion: {conversion}"
    )
    return {"records": 1}


@tag("demo", alias="simple-task-async")
async def simple_task_async(
    source: str,
    sink: str,
    result: Result,
    conversion: Optional[dict[str, Any]] = None,
) -> dict[str, int]:
    result.trace.info("[CALLER]: Start Simple Task with Async")
    await asyncio.sleep(0.1)
    conversion: dict[str, Any] = conversion or {}
    result.trace.info(
        f"Information||>source: {source}||>sink: {sink}||"
        f">conversion: {conversion}"
    )
    return {"records": 1}


@tag("demo", alias="private-args-task")
def private_args(_exec: str, params: dict[str, Any], result: Result):
    result.trace.info(
        f"Private args: `_exec` receive from `exec` params||"
        f"> exec: {_exec!r}"
    )
    return {"exec": _exec, "params": params}


@tag("raise", alias="return-type-not-valid")
def raise_returned_type():
    return True


@tag("demo", alias="get-items")
def get_items():
    return {"items": [1, 2, 3, 4]}


class MockModel(BaseModel):  # pragma: no cov
    name: str
    data: dict[str, Any]


@tag("demo", alias="gen-type")
def get_types(
    args1: str,
    args2: Path,
    args3: MockModel,
    *args,
    kwargs1: Optional[datetime] = None,
    kwargs2: Optional[Result] = None,
    **kwargs,
) -> MockModel:
    _ = args1
    _ = args2
    _ = args
    _ = kwargs1
    _ = kwargs2
    result = kwargs["result"]
    result.trace.info("[CALLER]: Test task type.")
    result.trace.info(f"[CALLER]: ... {type(args3)}: {args3}")
    return MockModel(name="foo", data={"key": "value"})
