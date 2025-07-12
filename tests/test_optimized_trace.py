"""Test module for optimized trace logging handler."""

import tempfile
import time
from pathlib import Path

from ddeutil.workflow.traces import (
    OptimizedFileTrace,
    WorkflowFileHandler,
    get_trace,
)


def test_workflow_file_handler_performance():
    """Test the performance of WorkflowFileHandler vs traditional file writing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Test traditional approach (simulated)
        start_time = time.time()
        for i in range(1000):
            with open(temp_path / f"traditional_{i}.txt", "w") as f:
                f.write(f"Log message {i}\n")
        traditional_time = time.time() - start_time

        # Test WorkflowFileHandler
        handler = WorkflowFileHandler(
            run_id="test-run-123",
            base_path=temp_path,
            buffer_size=4096,
        )

        start_time = time.time()
        for i in range(1000):
            # Create a mock log record
            import logging

            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg=f"Log message {i}",
                args=(),
                exc_info=None,
            )
            handler.emit(record)

        handler.flush()
        handler.close()
        handler_time = time.time() - start_time

        print(f"Traditional approach: {traditional_time:.4f} seconds")
        print(f"WorkflowFileHandler: {handler_time:.4f} seconds")
        print(
            f"Performance improvement: {traditional_time/handler_time:.2f}x faster"
        )


def test_optimized_file_trace():
    """Test the OptimizedFileTrace class."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create trace instance
        trace = OptimizedFileTrace(
            url=f"file://{temp_path}",
            run_id="test-run-456",
            extras={"enable_write_log": True},
        )

        # Test logging
        trace.info("Test info message")
        trace.warning("Test warning message")
        trace.error("Test error message")

        # Close the trace
        trace.close()

        # Verify files were created
        log_dir = temp_path / "run_id=test-run-456"
        assert log_dir.exists()
        assert (log_dir / "stdout.txt").exists()
        assert (log_dir / "stderr.txt").exists()
        assert (log_dir / "metadata.json").exists()


def test_get_trace_uses_optimized():
    """Test that get_trace now uses OptimizedFileTrace by default."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Get trace instance
        trace = get_trace(
            run_id="test-run-789", extras={"enable_write_log": True}
        )

        # Verify it's an OptimizedFileTrace
        assert isinstance(trace, OptimizedFileTrace)

        # Test logging
        trace.info("Test message from get_trace")
        trace.close()


if __name__ == "__main__":
    print("Testing WorkflowFileHandler performance...")
    test_workflow_file_handler_performance()

    print("\nTesting OptimizedFileTrace...")
    test_optimized_file_trace()

    print("\nTesting get_trace with optimized handler...")
    test_get_trace_uses_optimized()

    print("\nAll tests passed!")
