import pytest
from ddeutil.workflow import Result
from ddeutil.workflow.logs import FileTrace, TraceMeta


def test_trace_meta():
    meta = TraceMeta.make(mode="stderr", message="Foo", level="info")
    assert meta.message == "Foo"
    print(meta)

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
