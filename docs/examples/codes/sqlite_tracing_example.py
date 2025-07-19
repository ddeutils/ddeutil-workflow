#!/usr/bin/env python3
"""
SQLite Tracing System Example

This example demonstrates how to use the new SQLite-based tracing system
that writes logs to a SQLite database instead of files.
"""

import os
import sqlite3
import time
from pathlib import Path

# Set up environment for SQLite logging
os.environ["WORKFLOW_LOG_TRACE_ENABLE_WRITE"] = "true"
os.environ["WORKFLOW_LOG_TRACE_URL"] = "sqlite:./sqlite_logs/workflow_traces.db"


def basic_sqlite_usage():
    """Example 1: Basic SQLite usage with get_trace()."""
    print("🚀 Example 1: Basic SQLite Usage")

    try:
        from ddeutil.workflow.traces import get_trace

        # This will automatically use SQLiteTrace when URL scheme is "sqlite"
        trace = get_trace(
            run_id="sqlite-example-123", parent_run_id="parent-workflow-456"
        )

        # Standard logging interface
        trace.info("Workflow execution started")
        trace.debug("Processing configuration")
        trace.warning("High memory usage detected")
        trace.error("Database connection failed")

        # Add context information
        trace.info("Processing stage: data-extraction")
        trace.info("User: john.doe@company.com")

        # Close when done
        trace.close()

        print("✅ Basic SQLite example completed")

    except ImportError:
        print("❌ Could not import ddeutil.workflow.traces")
        print("Make sure you're running this from the project root directory")


def direct_sqlite_trace():
    """Example 2: Direct usage of SQLiteTrace class."""
    print("\n🚀 Example 2: Direct SQLiteTrace Usage")

    try:
        from urllib.parse import urlparse

        from ddeutil.workflow.traces import SQLiteTrace

        # Create SQLite trace directly
        trace = SQLiteTrace(
            url=urlparse("sqlite:./sqlite_logs/custom_traces.db"),
            run_id="direct-sqlite-example",
            extras={
                "enable_write_log": True,
                "workflow_name": "etl-pipeline",
                "stage_name": "transform",
                "user_id": "data-engineer",
                "environment": "production",
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

        print("✅ Direct SQLiteTrace example completed")

    except ImportError:
        print("❌ Could not import ddeutil.workflow.traces")


def sqlite_handler_direct():
    """Example 3: Direct usage of SQLiteHandler with Python logging."""
    print("\n🚀 Example 3: Direct SQLiteHandler Usage")

    try:
        import logging

        from ddeutil.workflow.traces import SQLiteHandler

        # Create a custom logger
        logger = logging.getLogger("my_sqlite_app")
        logger.setLevel(logging.DEBUG)

        # Create and configure the SQLite handler
        handler = SQLiteHandler(
            run_id="direct-handler-example",
            db_path=Path("./sqlite_logs/handler_traces.db"),
            buffer_size=50,  # Buffer 50 records before writing
            extras={
                "workflow_name": "data-pipeline",
                "environment": "production",
            },
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

        print("✅ Direct SQLiteHandler example completed")

    except ImportError:
        print("❌ Could not import ddeutil.workflow.traces")


def performance_comparison():
    """Example 4: Performance comparison between file and SQLite tracing."""
    print("\n🚀 Example 4: Performance Comparison")

    try:
        from ddeutil.workflow.traces import get_trace

        num_messages = 1000

        # Test file-based tracing
        print("Testing file-based tracing...")
        os.environ["WORKFLOW_LOG_TRACE_URL"] = "file:./sqlite_logs/file_traces"

        start_time = time.time()
        file_trace = get_trace("file-performance-test")

        for i in range(num_messages):
            file_trace.info(f"File message {i}")

        file_trace.close()
        file_time = time.time() - start_time
        print(f"File-based: {file_time:.4f} seconds")

        # Test SQLite-based tracing
        print("Testing SQLite-based tracing...")
        os.environ["WORKFLOW_LOG_TRACE_URL"] = (
            "sqlite:./sqlite_logs/sqlite_traces.db"
        )

        start_time = time.time()
        sqlite_trace = get_trace("sqlite-performance-test")

        for i in range(num_messages):
            sqlite_trace.info(f"SQLite message {i}")

        sqlite_trace.close()
        sqlite_time = time.time() - start_time
        print(f"SQLite-based: {sqlite_time:.4f} seconds")

        # Calculate improvement
        if file_time > 0:
            improvement = file_time / sqlite_time
            print(f"SQLite performance: {improvement:.2f}x faster")

        print("✅ Performance comparison completed")

    except ImportError:
        print("❌ Could not import ddeutil.workflow.traces")


def database_queries():
    """Example 5: Querying the SQLite database directly."""
    print("\n🚀 Example 5: Database Queries")

    try:
        # First, create some logs
        from ddeutil.workflow.traces import get_trace

        trace = get_trace(
            run_id="query-example",
            extras={
                "enable_write_log": True,
                "workflow_name": "query-test",
                "user_id": "tester",
            },
        )

        trace.info("Query test started")
        trace.warning("This is a warning message")
        trace.error("This is an error message")
        trace.info("Query test completed")

        trace.close()

        # Now query the database
        db_path = Path("./sqlite_logs/workflow_traces.db")

        if db_path.exists():
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                # Get all logs for our run
                cursor.execute(
                    """
                    SELECT level, message, datetime, workflow_name, user_id
                    FROM traces
                    WHERE run_id = 'query-example'
                    ORDER BY created_at
                """
                )

                print("\n📊 Database Query Results:")
                print("-" * 80)
                for row in cursor.fetchall():
                    level, message, datetime, workflow_name, user_id = row
                    print(f"[{level.upper()}] {datetime} | {message}")

                # Get statistics
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) as total_logs,
                        COUNT(CASE WHEN level = 'error' THEN 1 END) as errors,
                        COUNT(CASE WHEN level = 'warning' THEN 1 END) as warnings,
                        COUNT(CASE WHEN level = 'info' THEN 1 END) as info
                    FROM traces
                    WHERE run_id = 'query-example'
                """
                )

                stats = cursor.fetchone()
                print("\n📈 Statistics:")
                print(f"  Total logs: {stats[0]}")
                print(f"  Errors: {stats[1]}")
                print(f"  Warnings: {stats[2]}")
                print(f"  Info: {stats[3]}")

        print("✅ Database queries completed")

    except ImportError:
        print("❌ Could not import ddeutil.workflow.traces")


def find_traces_example():
    """Example 6: Using find_traces and find_trace_with_id with SQLite."""
    print("\n🚀 Example 6: Finding Traces")

    try:
        from ddeutil.workflow.traces import SQLiteTrace, get_trace

        # Create some test traces
        for i in range(3):
            trace = get_trace(f"find-example-{i}")
            trace.info(f"Test message {i}")
            trace.close()

        # Find all traces
        print("📋 All traces in database:")
        traces = list(SQLiteTrace.find_traces())
        for i, trace_data in enumerate(traces):
            print(
                f"  {i+1}. Run ID: {trace_data.meta[0].run_id if trace_data.meta else 'Unknown'}"
            )
            print(f"     Messages: {len(trace_data.meta)}")

        # Find specific trace
        print("\n🔍 Finding specific trace:")
        specific_trace = SQLiteTrace.find_trace_with_id("find-example-1")
        print(f"  Found trace with {len(specific_trace.meta)} messages")
        for meta in specific_trace.meta:
            print(f"    [{meta.level}] {meta.message}")

        print("✅ Find traces example completed")

    except ImportError:
        print("❌ Could not import ddeutil.workflow.traces")


def context_aware_sqlite():
    """Example 7: Context-aware logging with SQLite."""
    print("\n🚀 Example 7: Context-Aware SQLite Logging")

    try:
        from ddeutil.workflow.traces import get_trace

        # Create trace with rich context
        trace = get_trace(
            run_id="context-sqlite-example",
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

        print("✅ Context-aware SQLite logging completed")

    except ImportError:
        print("❌ Could not import ddeutil.workflow.traces")


def main():
    """Run all SQLite examples."""
    print("🚀 SQLite Tracing System - Examples")
    print("=" * 60)

    # Create logs directory
    Path("./sqlite_logs").mkdir(exist_ok=True)

    # Run examples
    basic_sqlite_usage()
    direct_sqlite_trace()
    sqlite_handler_direct()
    performance_comparison()
    database_queries()
    find_traces_example()
    context_aware_sqlite()

    print("\n" + "=" * 60)
    print("🎉 All SQLite examples completed!")
    print("📁 Check the ./sqlite_logs/ directory for SQLite database files")
    print("💡 You can use SQLite tools to explore the database:")
    print("   sqlite3 ./sqlite_logs/workflow_traces.db")
    print("   .tables")
    print("   SELECT * FROM traces LIMIT 5;")


if __name__ == "__main__":
    main()
