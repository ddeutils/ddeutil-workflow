# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
from __future__ import annotations

import time
from datetime import datetime
from functools import partial

from ddeutil.workflow import Result, tag
from ddeutil.workflow.__types import DictData

VERSION: str = "v1"
tag_v1 = partial(tag, name=VERSION)


@tag_v1(alias="get-stream-info")
def get_stream_info(name: str, result: Result) -> DictData:
    """Get Stream model information. This function use to validate an input
    stream name that exists on the config path.

    :param name: (str) A stream name
    :param result: (Result) A result dataclass for make logging.

    :rtype: DictData
    """
    result.trace.info(f"[CALLER]: Start getting stream: {name!r} info.")
    return {
        "name": name,
        "freq": {"mode": "daily"},
        "data_freq": {"mode": "daily"},
        "priority-groups": [1, 2],
    }


@tag_v1(alias="start-stream")
def start_stream(
    name: str, freq: dict[str, str], data_freq: dict[str, str], result: Result
) -> DictData:
    """Start stream workflow with update audit watermarking and generate starter
    stream log.

    :param name: (str) A stream name that want to get audit logs for generate
        the next audit date.
    :param freq: (dict[str, str]) A audit date frequency.
    :param data_freq: (dict[str, str]) A logical date frequency.
    :param result: (Result) A result dataclass for make logging.
    """
    result.trace.info(f"[CALLER]: Start running stream: {name!r}.")
    result.trace.info(f"[CALLER]: ... freq: {freq}")
    result.trace.info(f"[CALLER]: ... data_freq: {data_freq}")
    return {
        "audit-date": datetime(2025, 4, 1, 1),
        "logical-date": datetime(2025, 4, 1, 1),
    }


@tag_v1(alias="get-groups-from-priority")
def get_groups_from_priority(
    priority: int, stream: str, result: Result
) -> DictData:
    """Get groups from priority.

    :param priority: (int)
    :param stream: (str)
    :param result: (Result)
    """
    result.trace.info(
        f"[CALLER]: Get groups from priority: {priority} and stream: {stream!r}"
    )
    priority_group = {
        1: ["group-01"],
        2: ["group-02", "group-12"],
    }
    result.trace.info(f"[CALLER]: ... Return groups from {priority}")
    return {"groups": priority_group.get(priority)}


@tag_v1(alias="get-processes-from-group")
def get_processes_from_group(
    group: str, stream: str, result: Result
) -> DictData:
    result.trace.info(
        f"[CALLER]: Get processes from group: {group!r} and stream: {stream!r}"
    )
    processes = {
        "group-01": ["process-01"],
        "group-02": ["process-02"],
        "group-12": ["process-12"],
    }
    return {"processes": processes.get(group)}


@tag_v1(alias="start-process")
def start_process(name: str, result: Result) -> DictData:
    """Start process with an input process name."""
    result.trace.info(f"[CALLER]: Start process: {name!r}")
    routes = {
        "process-01": 1,
        "process-02": 2,
        "process-12": 2,
    }
    return {
        "routing": routes[name],
        "process": {
            "name": name,
            "extras": {
                "foo": "bar",
            },
        },
    }


@tag("v1", alias="routing-01")
def routing_ingest_file(
    process: str,
    audit_date: datetime,
    result: Result,
) -> DictData:
    """Routing file.

    :param process: (str)
    :param audit_date: (datetime)
    :param result: (Result)
    """
    result.trace.info(f"[CALLER]: Routing: 01 with process: {process!r}")
    result.trace.info(
        "[CALLER]: ... This routing is ingest data with file type."
    )
    result.trace.info(f"[CALLER]: ... Audit date: {audit_date}")
    time.sleep(5)
    return {
        "records": 1000,
    }


@tag("v1", alias="routing-02")
def routing_ingest_db(
    process: str,
    audit_date: datetime,
    result: Result,
) -> DictData:
    """Routing database.

    :param process: (str)
    :param audit_date: (datetime)
    :param result: (Result)
    """
    result.trace.info(f"[CALLER]: Routing: 02 with process: {process!r}")
    result.trace.info(
        "[CALLER]: ... This routing is ingest data with database type."
    )
    result.trace.info(f"[CALLER]: ... Audit date: {audit_date}")
    time.sleep(5)
    return {
        "records": 2000,
    }
