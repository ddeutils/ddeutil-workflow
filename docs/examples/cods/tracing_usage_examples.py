#!/usr/bin/env python3
"""
Comprehensive examples for using the optimized tracing system.

This file demonstrates various ways to use the new WorkflowFileHandler
and OptimizedFileTrace classes for high-performance logging.
"""

import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

# Set environment variables for the examples
os.environ["WORKFLOW_LOG_TRACE_ENABLE_WRITE"] = "true"
os.environ["WORKFLOW_LOG_TRACE_URL"] = "file:./example_logs"

try:
    from ddeutil.workflow.traces import (
        FileTrace,
        OptimizedFileTrace,
        WorkflowFileHandler,
        get_trace,
    )
except ImportError:
    print("Warning: Could not import ddeutil.workflow.traces")
    print("Make sure you're running this from the project root directory")
    exit(1)


def example_1_basic_usage():
    """Example 1: Basic usage with get_trace() - simplest approach."""
    print("\n" + "=" * 60)
    print("Example 1: Basic Usage with get_trace()")
    print("=" * 60)

    # This automatically uses OptimizedFileTrace now
    trace = get_trace(
        run_id="basic-example-123", parent_run_id="parent-workflow-456"
    )

    # Standard logging interface
    trace.info("🚀 Workflow execution started")
    trace.debug("🔍 Processing configuration")
    trace.warning("⚠️  High memory usage detected")
    trace.error("❌ Database connection failed")

    # Add context information
    trace.info("📊 Processing stage: data-extraction")
    trace.info("👤 User: john.doe@company.com")

    # Close when done
    trace.close()

    print(
        "✅ Basic example completed. Check ./example_logs/run_id=parent-workflow-456/"
    )


def example_2_direct_handler_usage():
    """Example 2: Direct usage of WorkflowFileHandler with Python logging."""
    print("\n" + "=" * 60)
    print("Example 2: Direct WorkflowFileHandler Usage")
    print("=" * 60)

    import logging

    # Create a custom logger
    logger = logging.getLogger("my_workflow_app")
    logger.setLevel(logging.DEBUG)

    # Create and configure the handler
    handler = WorkflowFileHandler(
        run_id="direct-handler-example",
        base_path=Path("./example_logs"),
        buffer_size=4096,  # 4KB buffer
        extras={"workflow_name": "data-pipeline", "environment": "production"},
    )

    # Add the handler to the logger
    logger.addHandler(handler)

    # Use standard Python logging
    logger.info("📈 Data pipeline started")
    logger.debug("🔧 Configuration loaded successfully")
    logger.warning("💾 Disk space running low")
    logger.error("🔥 Critical error in data processing")

    # Add custom context to log records
    extra_record = logging.LogRecord(
        name="custom",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Custom log with additional context",
        args=(),
        exc_info=None,
    )
    extra_record.user_id = "admin"
    extra_record.trace_id = "otel-123"
    handler.emit(extra_record)

    # Cleanup
    handler.close()

    print("✅ Direct handler example completed.")


def example_3_optimized_file_trace():
    """Example 3: Direct usage of OptimizedFileTrace class."""
    print("\n" + "=" * 60)
    print("Example 3: OptimizedFileTrace Direct Usage")
    print("=" * 60)

    # Create trace with custom configuration
    from urllib.parse import urlparse

    trace = OptimizedFileTrace(
        url=urlparse("file://./example_logs"),
        run_id="optimized-example",
        extras={
            "enable_write_log": True,
            "workflow_name": "etl-pipeline",
            "stage_name": "transform",
            "user_id": "data-engineer",
            "environment": "staging",
        },
    )

    # Log workflow stages
    trace.info("🔄 ETL Pipeline: Starting extraction phase")
    trace.info("📥 Extracted 10,000 records from source")

    # Simulate processing
    time.sleep(0.1)

    trace.info("🔄 ETL Pipeline: Starting transformation phase")
    trace.warning("⚠️  Found 50 records with missing values")

    # Simulate more processing
    time.sleep(0.1)

    trace.info("🔄 ETL Pipeline: Starting loading phase")
    trace.info("📤 Loaded 9,950 records to target database")
    trace.info("✅ ETL Pipeline completed successfully")

    # Close the trace
    trace.close()

    print("✅ OptimizedFileTrace example completed.")


def example_4_async_logging():
    """Example 4: Async logging with the optimized handler."""
    print("\n" + "=" * 60)
    print("Example 4: Async Logging")
    print("=" * 60)

    async def async_workflow():
        trace = get_trace(
            run_id="async-example", extras={"enable_write_log": True}
        )

        # Async logging operations
        await trace.ainfo("🚀 Async workflow started")

        # Simulate async operations
        await asyncio.sleep(0.1)
        await trace.ainfo("📊 Processing batch 1")

        await asyncio.sleep(0.1)
        await trace.awarning("⚠️  Batch 1 took longer than expected")

        await asyncio.sleep(0.1)
        await trace.ainfo("📊 Processing batch 2")

        await trace.ainfo("✅ Async workflow completed")

        trace.close()

    # Run the async workflow
    asyncio.run(async_workflow())

    print("✅ Async logging example completed.")


def example_5_concurrent_logging():
    """Example 5: Concurrent logging with thread safety."""
    print("\n" + "=" * 60)
    print("Example 5: Concurrent Logging")
    print("=" * 60)

    def worker(worker_id: int, num_messages: int = 10):
        """Worker function that logs messages concurrently."""
        trace = get_trace(
            run_id=f"concurrent-worker-{worker_id}",
            extras={"enable_write_log": True},
        )

        for i in range(num_messages):
            trace.info(f"👷 Worker {worker_id}: Processing item {i}")
            time.sleep(0.01)  # Simulate work

        trace.info(f"✅ Worker {worker_id}: Completed")
        trace.close()

    # Run multiple workers concurrently
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(worker, i, 5) for i in range(4)]

        # Wait for all workers to complete
        for future in futures:
            future.result()

    print("✅ Concurrent logging example completed.")


def example_6_performance_comparison():
    """Example 6: Performance comparison between old and new approaches."""
    print("\n" + "=" * 60)
    print("Example 6: Performance Comparison")
    print("=" * 60)

    num_messages = 1000

    # Test old FileTrace approach
    print("Testing old FileTrace approach...")
    start_time = time.time()

    old_trace = FileTrace(
        url=urlparse("file://./example_logs"),
        run_id="old-approach",
        extras={"enable_write_log": True},
    )

    for i in range(num_messages):
        old_trace.info(f"Old approach message {i}")

    old_time = time.time() - start_time
    print(f"Old FileTrace: {old_time:.4f} seconds")

    # Test new OptimizedFileTrace approach
    print("Testing new OptimizedFileTrace approach...")
    start_time = time.time()

    new_trace = OptimizedFileTrace(
        url=urlparse("file://./example_logs"),
        run_id="new-approach",
        extras={"enable_write_log": True},
    )

    for i in range(num_messages):
        new_trace.info(f"New approach message {i}")

    new_time = time.time() - start_time
    print(f"New OptimizedFileTrace: {new_time:.4f} seconds")

    # Calculate improvement
    improvement = old_time / new_time
    print(f"Performance improvement: {improvement:.2f}x faster")

    print("✅ Performance comparison completed.")


def example_7_context_aware_logging():
    """Example 7: Context-aware logging with rich metadata."""
    print("\n" + "=" * 60)
    print("Example 7: Context-Aware Logging")
    print("=" * 60)

    # Create trace with rich context
    trace = get_trace(
        run_id="context-example",
        extras={
            "enable_write_log": True,
            "workflow_name": "customer-data-sync",
            "stage_name": "data-validation",
            "job_name": "validate-customer-records",
            "user_id": "data-analyst-001",
            "tenant_id": "company-abc",
            "environment": "production",
            "trace_id": "otel-trace-123456",
            "span_id": "span-789",
            "tags": ["customer-data", "validation", "critical"],
            "metadata": {
                "source_system": "CRM",
                "target_system": "DataWarehouse",
                "batch_size": 5000,
            },
        },
    )

    # Log with context
    trace.info("🔍 Starting customer data validation")
    trace.info("📊 Validating 5,000 customer records")

    # Simulate validation process
    for i in range(1, 6):
        time.sleep(0.1)
        trace.info(f"✅ Validated batch {i}/5 (1,000 records)")

    trace.warning("⚠️  Found 23 records with validation issues")
    trace.info("🔧 Applying data quality rules")
    trace.info("📤 Sending 4,977 valid records to target system")
    trace.info("🎉 Customer data validation completed successfully")

    trace.close()

    print("✅ Context-aware logging example completed.")


def example_8_error_handling():
    """Example 8: Error handling and exception logging."""
    print("\n" + "=" * 60)
    print("Example 8: Error Handling")
    print("=" * 60)

    trace = get_trace(
        run_id="error-handling-example", extras={"enable_write_log": True}
    )

    try:
        trace.info("🚀 Starting risky operation")

        # Simulate an error
        raise ValueError("Simulated error for demonstration")

    except ValueError as e:
        trace.error(f"❌ Operation failed: {str(e)}")
        trace.exception("🔍 Full exception details:")

        # Log additional error context
        trace.error("🔧 Attempting recovery...")
        trace.warning("⚠️  Using fallback method")
        trace.info("✅ Recovery successful")

    finally:
        trace.info("🏁 Operation cleanup completed")
        trace.close()

    print("✅ Error handling example completed.")


def example_9_custom_formatter():
    """Example 9: Using custom log formats."""
    print("\n" + "=" * 60)
    print("Example 9: Custom Log Format")
    print("=" * 60)

    # Set custom format via environment variable
    os.environ["WORKFLOW_LOG_FORMAT_FILE"] = (
        "[{datetime}] [{level}] {message} | {filename}:{lineno}"
    )

    trace = get_trace(
        run_id="custom-format-example", extras={"enable_write_log": True}
    )

    trace.info("📝 This message uses custom formatting")
    trace.warning("⚠️  Custom format makes logs more readable")
    trace.error("❌ Error messages also use custom format")

    trace.close()

    print("✅ Custom format example completed.")


def example_10_batch_processing():
    """Example 10: Batch processing with efficient logging."""
    print("\n" + "=" * 60)
    print("Example 10: Batch Processing")
    print("=" * 60)

    trace = get_trace(
        run_id="batch-processing-example",
        extras={
            "enable_write_log": True,
            "workflow_name": "batch-data-processor",
        },
    )

    # Simulate batch processing
    batch_size = 100
    total_items = 1000

    trace.info(
        f"🚀 Starting batch processing: {total_items} items in batches of {batch_size}"
    )

    for batch_num in range(0, total_items, batch_size):
        start_idx = batch_num
        end_idx = min(batch_num + batch_size, total_items)

        trace.info(
            f"📦 Processing batch {batch_num//batch_size + 1}: items {start_idx}-{end_idx}"
        )

        # Simulate processing time
        time.sleep(0.05)

        # Log batch results
        processed_count = end_idx - start_idx
        trace.info(
            f"✅ Batch {batch_num//batch_size + 1} completed: {processed_count} items processed"
        )

    trace.info(f"🎉 Batch processing completed: {total_items} items processed")
    trace.close()

    print("✅ Batch processing example completed.")


def main():
    """Run all examples."""
    print("🚀 Optimized Tracing System - Usage Examples")
    print("=" * 80)

    # Create logs directory
    Path("./example_logs").mkdir(exist_ok=True)

    # Run all examples
    examples = [
        example_1_basic_usage,
        example_2_direct_handler_usage,
        example_3_optimized_file_trace,
        example_4_async_logging,
        example_5_concurrent_logging,
        example_6_performance_comparison,
        example_7_context_aware_logging,
        example_8_error_handling,
        example_9_custom_formatter,
        example_10_batch_processing,
    ]

    for i, example in enumerate(examples, 1):
        try:
            example()
        except Exception as e:
            print(f"❌ Example {i} failed: {e}")

    print("\n" + "=" * 80)
    print("🎉 All examples completed!")
    print("📁 Check the ./example_logs/ directory for generated log files")
    print("📖 See docs/optimized-tracing.md for detailed documentation")


if __name__ == "__main__":
    main()
