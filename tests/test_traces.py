import traceback

import pytest
from ddeutil.workflow import Result
from ddeutil.workflow.traces import (
    FileTrace,
    Message,
    TraceMeta,
)


def test_print_trace_exception():

    def nested_func():  # pragma: no cov
        return 1 / 0

    try:
        nested_func()
    except ZeroDivisionError:
        print(traceback.format_exc())


def test_trace_regex_message():
    msg: str = (
        "[STAGE]: Execute Empty-Stage: 'End trigger Priority Group': "
        "( End trigger Priority Group: 2 )"
    )
    prefix: Message = Message.from_str(msg)
    assert prefix.name == "STAGE"
    assert prefix.message == (
        "Execute Empty-Stage: 'End trigger Priority Group': "
        "( End trigger Priority Group: 2 )"
    )

    msg: str = (
        "[]: Execute Empty-Stage: 'End trigger Priority Group': "
        "( End trigger Priority Group: 2 )"
    )
    prefix: Message = Message.from_str(msg)
    assert prefix.name is None
    assert prefix.message == (
        "[]: Execute Empty-Stage: 'End trigger Priority Group': "
        "( End trigger Priority Group: 2 )"
    )

    msg: str = ""
    prefix: Message = Message.from_str(msg)
    assert prefix.name is None
    assert prefix.message == ""

    msg: str = (
        "[WORKFLOW]: Execute Empty-Stage:\n'End trigger Priority Group':\n"
        "( End trigger Priority Group: 2 )"
    )
    prefix: Message = Message.from_str(msg)
    assert prefix.name == "WORKFLOW"
    assert prefix.message == (
        "Execute Empty-Stage:\n'End trigger Priority Group':\n"
        "( End trigger Priority Group: 2 )"
    )
    assert prefix.prepare() == (
        "🏃 [WORKFLOW]: Execute Empty-Stage:\n'End trigger Priority Group':\n"
        "( End trigger Priority Group: 2 )"
    )
    assert prefix.prepare(extras={"log_add_emoji": False}) == (
        "[WORKFLOW]: Execute Empty-Stage:\n'End trigger Priority Group':\n"
        "( End trigger Priority Group: 2 )"
    )


def test_trace_meta():
    meta = TraceMeta.make(
        mode="stderr", message="Foo", level="info", cutting_id=""
    )
    assert meta.message == "Foo"

    meta = TraceMeta.make(
        mode="stderr",
        message="Foo",
        level="info",
        cutting_id="",
        extras={"logs_trace_frame_layer": 1},
    )
    assert meta.filename == "test_traces.py"

    meta = TraceMeta.make(
        mode="stderr",
        message="Foo",
        level="info",
        cutting_id="",
        extras={"logs_trace_frame_layer": 2},
    )
    assert meta.filename == "python.py"

    # NOTE: Raise because the maximum frame does not back to the set value.
    with pytest.raises(ValueError):
        TraceMeta.make(
            mode="stderr",
            message="Foo",
            level="info",
            cutting_id="",
            extras={"logs_trace_frame_layer": 100},
        )


def test_result_trace():
    rs: Result = Result(
        parent_run_id="foo_id_for_writing_log",
        extras={
            "enable_write_log": True,
            "logs_trace_frame_layer": 4,
        },
    )
    print(rs.trace.extras)
    rs.trace.info("[DEMO]: Test echo log from result trace argument!!!")
    print(rs.run_id)
    print(rs.parent_run_id)


def test_file_trace_find_traces():
    for log in FileTrace.find_traces():
        print(log.meta)
