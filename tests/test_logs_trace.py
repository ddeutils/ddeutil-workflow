import pytest
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
    assert meta.filename == "logs.py"

    meta = TraceMeta.make(
        mode="stderr",
        message="Foo",
        level="info",
        extras={"logs_trace_frame_layer": 2},
    )
    assert meta.filename == "test_logs_trace.py"

    # NOTE: Raise because the maximum frame does not back to the set value.
    with pytest.raises(ValueError):
        TraceMeta.make(
            mode="stderr",
            message="Foo",
            level="info",
            extras={"logs_trace_frame_layer": 100},
        )


def test_file_trace_find_traces():
    for log in FileTrace.find_traces():
        print(log.meta)
