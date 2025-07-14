import shutil
import traceback
from pathlib import Path
from unittest import mock

import pytest
from ddeutil.workflow import Result
from ddeutil.workflow.traces import (
    BaseHandler,
    ConsoleHandler,
    FileHandler,
    Message,
    Metadata,
    TraceManager,
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
    meta = Metadata.make(
        run_id="100",
        parent_run_id="01",
        error_flag=True,
        message="Foo",
        level="info",
        cutting_id="",
    )
    assert meta.message == "Foo"

    meta = Metadata.make(
        run_id="100",
        parent_run_id="01",
        error_flag=True,
        message="Foo",
        level="info",
        cutting_id="",
        extras={"logs_trace_frame_layer": 1},
    )
    assert meta.filename == "test_traces.py"

    meta = Metadata.make(
        run_id="100",
        parent_run_id="01",
        error_flag=True,
        message="Foo",
        level="info",
        cutting_id="",
        extras={"logs_trace_frame_layer": 2},
    )
    assert meta.filename == "python.py"

    # NOTE: Raise because the maximum frame does not back to the set value.
    with pytest.raises(ValueError):
        Metadata.make(
            run_id="100",
            parent_run_id="01",
            error_flag=True,
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


def test_file_trace_find_traces(test_path):
    for log in FileHandler(path=str(test_path.parent / "logs")).find_traces():
        print(log.meta)


@pytest.mark.asyncio
@mock.patch.multiple(BaseHandler, __abstractmethods__=set())
async def test_trace_handler_base():
    meta = Metadata.make(
        run_id="100",
        parent_run_id="01",
        error_flag=True,
        message="Foo",
        level="info",
        cutting_id="",
    )

    handler = BaseHandler()
    assert handler.emit(meta) is None
    assert await handler.amit(meta) is None
    assert handler.flush([meta]) is None


@pytest.mark.asyncio
async def test_trace_handler_console():
    meta = Metadata.make(
        run_id="100",
        parent_run_id="01",
        error_flag=True,
        message="Foo",
        level="info",
        cutting_id="",
    )
    handler = ConsoleHandler()
    assert handler.emit(meta) is None
    assert await handler.amit(meta) is None
    assert handler.flush([meta]) is None


@pytest.mark.asyncio
async def test_trace_handler_file():
    meta = Metadata.make(
        run_id="100",
        parent_run_id="01",
        error_flag=True,
        message="Foo",
        level="info",
        cutting_id="",
    )
    handler = FileHandler(path="./logs")
    assert handler.emit(meta) is None
    assert await handler.amit(meta) is None
    assert handler.flush([meta]) is None
    assert handler.pre() is None

    meta = Metadata.make(
        run_id="100",
        parent_run_id="01",
        error_flag=False,
        message="Bar",
        level="info",
        cutting_id="",
    )
    handler = FileHandler(path="./logs")
    assert handler.emit(meta) is None
    assert handler.flush([meta]) is None

    if Path("./logs/run_id=01").exists():
        shutil.rmtree(Path("./logs/run_id=01"))


def test_trace_manager():
    trace = TraceManager(
        run_id="01",
        parent_run_id="1001",
        handlers=[{"type": "console"}],
    )
    trace.debug("This is debug message from test_trace")
    trace.info("This is info message from test_trace")
    trace.warning("This is warning message from test_trace")
    trace.error("This is error message from test_trace")
    trace.exception("This is exception message from test_trace")
