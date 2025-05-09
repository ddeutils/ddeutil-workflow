import pytest
from ddeutil.workflow import Result
from ddeutil.workflow.logs import (
    FileTrace,
    PrefixMsg,
    TraceMeta,
    extract_msg_prefix,
)


def test_trace_regex_message():
    msg: str = (
        "[STAGE]: Execute Empty-Stage: 'End trigger Priority Group': "
        "( End trigger Priority Group: 2 )"
    )
    prefix: PrefixMsg = extract_msg_prefix(msg)
    assert prefix.name == "STAGE"
    assert prefix.message == (
        "Execute Empty-Stage: 'End trigger Priority Group': "
        "( End trigger Priority Group: 2 )"
    )

    msg: str = (
        "[]: Execute Empty-Stage: 'End trigger Priority Group': "
        "( End trigger Priority Group: 2 )"
    )
    prefix: PrefixMsg = extract_msg_prefix(msg)
    assert prefix.name is None
    assert prefix.message == (
        "[]: Execute Empty-Stage: 'End trigger Priority Group': "
        "( End trigger Priority Group: 2 )"
    )

    msg: str = ""
    prefix: PrefixMsg = extract_msg_prefix(msg)
    assert prefix.name is None
    assert prefix.message == ""

    msg: str = (
        "[WORKFLOW]: Execute Empty-Stage:\n'End trigger Priority Group':\n"
        "( End trigger Priority Group: 2 )"
    )
    prefix: PrefixMsg = extract_msg_prefix(msg)
    assert prefix.name == "WORKFLOW"
    assert prefix.message == (
        "Execute Empty-Stage:\n'End trigger Priority Group':\n"
        "( End trigger Priority Group: 2 )"
    )


def test_trace_meta():
    meta = TraceMeta.make(mode="stderr", message="Foo", level="info")
    assert meta.message == "Foo"

    meta = TraceMeta.make(
        mode="stderr",
        message="Foo",
        level="info",
        extras={"logs_trace_frame_layer": 1},
    )
    assert meta.filename == "test_logs_trace.py"

    meta = TraceMeta.make(
        mode="stderr",
        message="Foo",
        level="info",
        extras={"logs_trace_frame_layer": 2},
    )
    assert meta.filename == "python.py"

    # NOTE: Raise because the maximum frame does not back to the set value.
    with pytest.raises(ValueError):
        TraceMeta.make(
            mode="stderr",
            message="Foo",
            level="info",
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
