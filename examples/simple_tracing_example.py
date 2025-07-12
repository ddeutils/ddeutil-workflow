#!/usr/bin/env python3
"""
Simple example demonstrating the optimized tracing system.

This example shows the basic usage patterns for the new high-performance
logging handler.
"""

import os
import time
from pathlib import Path

# Set up environment for logging
os.environ["WORKFLOW_LOG_TRACE_ENABLE_WRITE"] = "true"
os.environ["WORKFLOW_LOG_TRACE_URL"] = "file:./simple_logs"


def basic_usage_example():
    """Example 1: Basic usage with get_trace() - the simplest approach."""
    print("🚀 Example 1: Basic Usage")

    try:
        from ddeutil.workflow.traces import get_trace

        # This automatically uses the new OptimizedFileTrace
        trace = get_trace(
            run_id="simple-example-123", parent_run_id="parent-workflow-456"
        )

        # Standard logging interface
        trace.info("Workflow execution started")
        trace.debug("Processing configuration")
        trace.warning("High memory usage detected")
        trace.error("Database connection failed")

        # Add context information
        trace.info("Processing stage: data-extraction")
        trace.info("User: john.doe@company.com")

        print("✅ Basic example completed successfully")

    except ImportError:
        print("❌ Could not import ddeutil.workflow.traces")
        print("Make sure you're running this from the project root directory")


def performance_demo():
    """Example 2: Performance demonstration."""
    print("\n🚀 Example 2: Performance Demo")

    try:
        from ddeutil.workflow.traces import get_trace

        # Create trace for performance test
        trace = get_trace(
            run_id="performance-demo", extras={"enable_write_log": True}
        )

        # Log many messages quickly
        start_time = time.time()
        num_messages = 1000

        for i in range(num_messages):
            trace.info(f"Processing item {i}")

        duration = time.time() - start_time
        rate = num_messages / duration

        print(f"✅ Logged {num_messages} messages in {duration:.2f} seconds")
        print(f"📊 Rate: {rate:.0f} messages/second")

    except ImportError:
        print("❌ Could not import ddeutil.workflow.traces")


def context_aware_logging():
    """Example 3: Context-aware logging with rich metadata."""
    print("\n🚀 Example 3: Context-Aware Logging")

    try:
        from ddeutil.workflow.traces import get_trace

        # Create trace with rich context
        trace = get_trace(
            run_id="context-example",
            extras={
                "enable_write_log": True,
                "workflow_name": "customer-data-sync",
                "stage_name": "data-validation",
                "user_id": "data-analyst-001",
                "environment": "production",
                "trace_id": "otel-trace-123456",
                "tags": ["customer-data", "validation", "critical"],
            },
        )

        # Log with context
        trace.info("Starting customer data validation")
        trace.info("Validating 5,000 customer records")

        # Simulate validation process
        for i in range(1, 6):
            time.sleep(0.1)
            trace.info(f"Validated batch {i}/5 (1,000 records)")

        trace.warning("Found 23 records with validation issues")
        trace.info("Applying data quality rules")
        trace.info("Sending 4,977 valid records to target system")
        trace.info("Customer data validation completed successfully")

        print("✅ Context-aware logging example completed")

    except ImportError:
        print("❌ Could not import ddeutil.workflow.traces")


def error_handling_example():
    """Example 4: Error handling and exception logging."""
    print("\n🚀 Example 4: Error Handling")

    try:
        from ddeutil.workflow.traces import get_trace

        trace = get_trace(
            run_id="error-handling-example", extras={"enable_write_log": True}
        )

        try:
            trace.info("Starting risky operation")

            # Simulate an error
            raise ValueError("Simulated error for demonstration")

        except ValueError as e:
            trace.error(f"Operation failed: {str(e)}")
            trace.exception("Full exception details:")

            # Log additional error context
            trace.error("Attempting recovery...")
            trace.warning("Using fallback method")
            trace.info("Recovery successful")

        finally:
            trace.info("Operation cleanup completed")

        print("✅ Error handling example completed")

    except ImportError:
        print("❌ Could not import ddeutil.workflow.traces")


def batch_processing_example():
    """Example 5: Batch processing with efficient logging."""
    print("\n🚀 Example 5: Batch Processing")

    try:
        from ddeutil.workflow.traces import get_trace

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
            f"Starting batch processing: {total_items} items in batches of {batch_size}"
        )

        for batch_num in range(0, total_items, batch_size):
            start_idx = batch_num
            end_idx = min(batch_num + batch_size, total_items)

            trace.info(
                f"Processing batch {batch_num//batch_size + 1}: items {start_idx}-{end_idx}"
            )

            # Simulate processing time
            time.sleep(0.05)

            # Log batch results
            processed_count = end_idx - start_idx
            trace.info(
                f"Batch {batch_num//batch_size + 1} completed: {processed_count} items processed"
            )

        trace.info(f"Batch processing completed: {total_items} items processed")

        print("✅ Batch processing example completed")

    except ImportError:
        print("❌ Could not import ddeutil.workflow.traces")


def main():
    """Run all examples."""
    print("🚀 Optimized Tracing System - Simple Examples")
    print("=" * 60)

    # Create logs directory
    Path("./simple_logs").mkdir(exist_ok=True)

    # Run examples
    basic_usage_example()
    performance_demo()
    context_aware_logging()
    error_handling_example()
    batch_processing_example()

    print("\n" + "=" * 60)
    print("🎉 All examples completed!")
    print("📁 Check the ./simple_logs/ directory for generated log files")
    print("📖 See docs/optimized-tracing.md for detailed documentation")


if __name__ == "__main__":
    main()
