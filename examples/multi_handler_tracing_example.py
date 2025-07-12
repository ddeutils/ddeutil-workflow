#!/usr/bin/env python3
"""
Multi-Handler Tracing Example

This example demonstrates how to use the multi-handler tracing system to
log to multiple destinations simultaneously (file, SQLite, REST API,
Elasticsearch, etc.).

Features demonstrated:
- Multi-destination logging
- Dynamic handler management
- Handler-specific configuration
- Error handling and fail-silently options
- Performance monitoring
- Handler inspection and management
"""

import asyncio

# Add the src directory to the path for imports
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ddeutil.workflow.traces import (
    MultiHandler,
    RestAPIHandler,
    SQLiteHandler,
    WorkflowFileHandler,
    get_trace,
)


def example_basic_multi_handler():
    """Example: Basic multi-handler with file and SQLite."""
    print("\n=== Basic Multi-Handler Example ===")

    # Configure multi-handler with file and SQLite
    extras = {
        "trace_type": "multi",
        "handlers": [
            {
                "type": "file",
                "path": "./logs/multi-example",
                "buffer_size": 8192,
                "flush_interval": 1.0,
            },
            {
                "type": "sqlite",
                "path": "./logs/multi_traces.db",
                "buffer_size": 100,
                "flush_interval": 2.0,
            },
        ],
        "fail_silently": True,
        "workflow_name": "multi-handler-workflow",
        "stage_name": "multi-stage",
        "job_name": "multi-job",
        "trace_id": str(uuid.uuid4()),
        "span_id": str(uuid.uuid4()),
        "user_id": "multi-user",
        "tenant_id": "multi-tenant",
        "environment": "development",
        "tags": ["service:multi", "team:platform"],
    }

    # Create trace instance
    trace = get_trace(
        run_id=f"multi-basic-{int(time.time())}",
        parent_run_id="multi-parent-001",
        extras=extras,
    )

    try:
        # Log workflow execution
        trace.info("🚀 Starting multi-handler workflow")
        trace.debug("📊 Initializing multiple handlers")

        # Check handler information
        print(f"📋 Handler count: {trace.handler_count}")
        print(f"🔧 Handler types: {trace.handler_types}")

        # Simulate some processing
        time.sleep(0.1)

        # Log with context
        trace.info("✅ Multi-handler workflow completed successfully")
        trace.debug(f"📈 Processed data with {trace.handler_count} handlers")

        # Simulate error scenario
        try:
            raise ValueError("Test error for multi-handler")
        except Exception as e:
            trace.error(f"❌ Multi-handler error: {e}")
            trace.exception("🔍 Stack trace for debugging")

        # Log completion
        trace.info("🏁 Multi-handler workflow execution completed")

    except Exception as e:
        trace.error(f"💥 Unexpected error: {e}")
    finally:
        trace.close()


def example_advanced_multi_handler():
    """Example: Advanced multi-handler with all handler types."""
    print("\n=== Advanced Multi-Handler Example ===")

    # Configure multi-handler with all handler types
    extras = {
        "trace_type": "multi",
        "handlers": [
            {
                "type": "file",
                "path": "./logs/advanced-multi",
                "buffer_size": 8192,
                "flush_interval": 1.0,
            },
            {
                "type": "sqlite",
                "path": "./logs/advanced_multi_traces.db",
                "buffer_size": 100,
                "flush_interval": 2.0,
            },
            {
                "type": "restapi",
                "api_url": "https://httpbin.org/post",
                "service_type": "generic",
                "buffer_size": 50,
                "flush_interval": 2.0,
                "timeout": 10.0,
                "max_retries": 3,
            },
            {
                "type": "elasticsearch",
                "es_hosts": "http://localhost:9200",
                "index_name": "advanced-multi-traces",
                "username": "elastic",
                "password": "changeme",
                "buffer_size": 100,
                "flush_interval": 2.0,
                "timeout": 30.0,
                "max_retries": 3,
            },
        ],
        "fail_silently": True,
        "workflow_name": "advanced-multi-workflow",
        "stage_name": "advanced-stage",
        "job_name": "advanced-job",
        "trace_id": str(uuid.uuid4()),
        "span_id": str(uuid.uuid4()),
        "user_id": "advanced-user",
        "tenant_id": "advanced-tenant",
        "environment": "production",
        "tags": ["service:advanced", "team:engineering"],
    }

    # Create trace instance
    trace = get_trace(
        run_id=f"multi-advanced-{int(time.time())}",
        parent_run_id="advanced-parent-001",
        extras=extras,
    )

    try:
        # Log workflow execution
        trace.info("🚀 Starting advanced multi-handler workflow")
        trace.debug("📊 Initializing all handler types")

        # Check handler information
        print(f"📋 Handler count: {trace.handler_count}")
        print(f"🔧 Handler types: {trace.handler_types}")

        # Simulate different stages
        stages = ["validation", "processing", "transformation", "loading"]
        for stage in stages:
            time.sleep(0.1)
            trace.info(f"📋 Executing {stage} stage")
            trace.debug(
                "⚙️ Stage configuration: {'mode': 'batch', 'timeout': 30}"
            )

            # Simulate some work
            time.sleep(0.05)

            trace.info(f"✅ {stage.capitalize()} stage completed")

        # Log completion
        trace.info("🎉 Advanced multi-handler workflow completed successfully")

    except Exception as e:
        trace.error(f"💥 Advanced workflow failed: {e}")
    finally:
        trace.close()


def example_dynamic_handler_management():
    """Example: Dynamic handler management."""
    print("\n=== Dynamic Handler Management Example ===")

    # Start with basic configuration
    extras = {
        "trace_type": "multi",
        "handlers": [
            {
                "type": "file",
                "path": "./logs/dynamic-multi",
                "buffer_size": 8192,
                "flush_interval": 1.0,
            }
        ],
        "fail_silently": True,
        "workflow_name": "dynamic-multi-workflow",
        "stage_name": "dynamic-stage",
        "job_name": "dynamic-job",
    }

    # Create trace instance
    trace = get_trace(run_id=f"multi-dynamic-{int(time.time())}", extras=extras)

    try:
        # Log initial state
        trace.info("🚀 Starting dynamic handler management")
        print(f"📋 Initial handler count: {trace.handler_count}")

        # Add SQLite handler dynamically
        sqlite_handler = SQLiteHandler(
            run_id=trace.run_id,
            parent_run_id=trace.parent_run_id,
            db_path=Path("./logs/dynamic_multi_traces.db"),
            extras=extras,
            buffer_size=50,
            flush_interval=1.0,
        )
        trace.add_handler(sqlite_handler)

        trace.info("➕ Added SQLite handler")
        print(f"📋 Handler count after adding SQLite: {trace.handler_count}")

        # Add REST API handler dynamically
        restapi_handler = RestAPIHandler(
            run_id=trace.run_id,
            parent_run_id=trace.parent_run_id,
            api_url="https://httpbin.org/post",
            service_type="generic",
            extras=extras,
            buffer_size=25,
            flush_interval=1.0,
        )
        trace.add_handler(restapi_handler)

        trace.info("➕ Added REST API handler")
        print(f"📋 Handler count after adding REST API: {trace.handler_count}")

        # Log some messages
        trace.info("📝 Testing dynamic handlers")
        trace.debug("🔍 Debug message for all handlers")
        trace.warning("⚠️ Warning message for all handlers")

        # Remove a handler
        trace.remove_handler(sqlite_handler)
        trace.info("➖ Removed SQLite handler")
        print(f"📋 Handler count after removing SQLite: {trace.handler_count}")

        # Log final message
        trace.info("✅ Dynamic handler management completed")

    except Exception as e:
        trace.error(f"💥 Dynamic management failed: {e}")
    finally:
        trace.close()


def example_handler_inspection():
    """Example: Handler inspection and management."""
    print("\n=== Handler Inspection Example ===")

    # Configure multi-handler
    extras = {
        "trace_type": "multi",
        "handlers": [
            {
                "type": "file",
                "path": "./logs/inspect-multi",
                "buffer_size": 8192,
                "flush_interval": 1.0,
            },
            {
                "type": "sqlite",
                "path": "./logs/inspect_multi_traces.db",
                "buffer_size": 100,
                "flush_interval": 2.0,
            },
            {
                "type": "restapi",
                "api_url": "https://httpbin.org/post",
                "service_type": "generic",
                "buffer_size": 50,
                "flush_interval": 2.0,
            },
        ],
        "fail_silently": True,
        "workflow_name": "inspect-multi-workflow",
        "stage_name": "inspect-stage",
        "job_name": "inspect-job",
    }

    # Create trace instance
    trace = get_trace(run_id=f"multi-inspect-{int(time.time())}", extras=extras)

    try:
        # Log workflow execution
        trace.info("🔍 Starting handler inspection")

        # Inspect handlers
        print(f"📋 Total handlers: {trace.handler_count}")
        print(f"🔧 Handler types: {trace.handler_types}")

        # Get specific handlers
        file_handlers = trace.get_handlers_by_type(WorkflowFileHandler)
        sqlite_handlers = trace.get_handlers_by_type(SQLiteHandler)
        restapi_handlers = trace.get_handlers_by_type(RestAPIHandler)

        print(f"📁 File handlers: {len(file_handlers)}")
        print(f"🗄️ SQLite handlers: {len(sqlite_handlers)}")
        print(f"🌐 REST API handlers: {len(restapi_handlers)}")

        # Get specific handler
        file_handler = trace.get_handler_by_type(WorkflowFileHandler)
        if file_handler:
            print(f"📁 File handler path: {file_handler.log_dir}")

        # Log some messages
        trace.info("📝 Testing handler inspection")
        trace.debug("🔍 Debug message")
        trace.warning("⚠️ Warning message")
        trace.error("❌ Error message")

        # Log completion
        trace.info("✅ Handler inspection completed")

    except Exception as e:
        trace.error(f"💥 Handler inspection failed: {e}")
    finally:
        trace.close()


def example_fail_silently_behavior():
    """Example: Fail-silently behavior with invalid handlers."""
    print("\n=== Fail-Silently Behavior Example ===")

    # Configure multi-handler with some invalid configurations
    extras = {
        "trace_type": "multi",
        "handlers": [
            {
                "type": "file",
                "path": "./logs/fail-silent-multi",
                "buffer_size": 8192,
                "flush_interval": 1.0,
            },
            {
                "type": "invalid_handler",  # This will fail
                "path": "./logs/invalid",
            },
            {
                "type": "restapi",
                "api_url": "https://invalid-url-that-will-fail.com",
                "service_type": "generic",
                "buffer_size": 50,
                "flush_interval": 2.0,
            },
        ],
        "fail_silently": True,  # Continue even if some handlers fail
        "workflow_name": "fail-silent-workflow",
        "stage_name": "fail-silent-stage",
        "job_name": "fail-silent-job",
    }

    # Create trace instance
    trace = get_trace(
        run_id=f"multi-fail-silent-{int(time.time())}", extras=extras
    )

    try:
        # Log workflow execution
        trace.info("🚀 Starting fail-silently test")
        trace.debug("📊 Testing handler failure tolerance")

        # Check which handlers actually worked
        print(f"📋 Working handlers: {trace.handler_count}")
        print(f"🔧 Handler types: {trace.handler_types}")

        # Log messages (should work even with failed handlers)
        trace.info("📝 This should work despite some failed handlers")
        trace.debug("🔍 Debug message")
        trace.warning("⚠️ Warning message")
        trace.error("❌ Error message")

        # Log completion
        trace.info("✅ Fail-silently test completed")

    except Exception as e:
        trace.error(f"💥 Fail-silently test failed: {e}")
    finally:
        trace.close()


def example_direct_multi_handler():
    """Example: Direct multi-handler usage."""
    print("\n=== Direct Multi-Handler Usage Example ===")

    # Create handlers directly
    file_handler = WorkflowFileHandler(
        run_id=f"direct-multi-{int(time.time())}",
        parent_run_id="direct-parent-001",
        base_path=Path("./logs/direct-multi"),
        extras={"workflow_name": "direct-multi-test"},
        buffer_size=8192,
        flush_interval=1.0,
    )

    sqlite_handler = SQLiteHandler(
        run_id=f"direct-multi-{int(time.time())}",
        parent_run_id="direct-parent-001",
        db_path=Path("./logs/direct_multi_traces.db"),
        extras={"workflow_name": "direct-multi-test"},
        buffer_size=50,
        flush_interval=1.0,
    )

    # Create multi-handler
    multi_handler = MultiHandler(
        run_id=f"direct-multi-{int(time.time())}",
        parent_run_id="direct-parent-001",
        handlers=[file_handler, sqlite_handler],
        extras={"workflow_name": "direct-multi-test"},
        fail_silently=True,
    )

    # Create logger and add handler
    import logging

    logger = logging.getLogger("direct-multi-test")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(multi_handler)

    try:
        # Log messages directly
        logger.info("📝 Direct multi-handler test message")
        logger.debug("🔍 Debug information for multi-handler")
        logger.warning("⚠️ Warning message for multi-handler")
        logger.error("❌ Error message for multi-handler")

        # Check handler information
        print(f"📋 Handler count: {multi_handler.handler_count}")
        print(f"🔧 Handler types: {multi_handler.handler_types}")

        # Flush to send buffered messages
        multi_handler.flush()

    except Exception as e:
        print(f"Error in direct multi-handler test: {e}")
    finally:
        multi_handler.close()


def example_performance_comparison():
    """Compare performance of single vs multi-handler."""
    print("\n=== Performance Comparison ===")

    # Test single handler (file)
    print("\nTesting: Single File Handler")
    single_extras = {
        "trace_type": "file",
        "workflow_name": "single-handler-test",
    }

    single_trace = get_trace(
        run_id=f"single-perf-{int(time.time())}", extras=single_extras
    )

    start_time = time.time()
    for i in range(100):
        single_trace.info(f"Single handler message {i + 1}")
    single_trace.close()
    single_duration = time.time() - start_time

    print(f"  Duration: {single_duration:.3f}s")
    print(f"  Messages per second: {100 / single_duration:.1f}")

    # Test multi-handler (file + SQLite)
    print("\nTesting: Multi-Handler (File + SQLite)")
    multi_extras = {
        "trace_type": "multi",
        "handlers": [
            {
                "type": "file",
                "path": "./logs/perf-multi",
                "buffer_size": 8192,
                "flush_interval": 1.0,
            },
            {
                "type": "sqlite",
                "path": "./logs/perf_multi_traces.db",
                "buffer_size": 100,
                "flush_interval": 2.0,
            },
        ],
        "workflow_name": "multi-handler-test",
    }

    multi_trace = get_trace(
        run_id=f"multi-perf-{int(time.time())}", extras=multi_extras
    )

    start_time = time.time()
    for i in range(100):
        multi_trace.info(f"Multi handler message {i + 1}")
    multi_trace.close()
    multi_duration = time.time() - start_time

    print(f"  Duration: {multi_duration:.3f}s")
    print(f"  Messages per second: {100 / multi_duration:.1f}")
    print(f"  Performance ratio: {single_duration / multi_duration:.2f}x")


async def example_async_multi_handler():
    """Example: Async multi-handler usage."""
    print("\n=== Async Multi-Handler Example ===")

    extras = {
        "trace_type": "multi",
        "handlers": [
            {
                "type": "file",
                "path": "./logs/async-multi",
                "buffer_size": 8192,
                "flush_interval": 1.0,
            },
            {
                "type": "restapi",
                "api_url": "https://httpbin.org/post",
                "service_type": "generic",
                "buffer_size": 50,
                "flush_interval": 2.0,
            },
        ],
        "fail_silently": True,
        "workflow_name": "async-multi-workflow",
        "stage_name": "async-stage",
        "job_name": "async-job",
    }

    trace = get_trace(run_id=f"async-multi-{int(time.time())}", extras=extras)

    try:
        # Async logging
        await trace.ainfo("🚀 Starting async multi-handler workflow")
        await trace.adebug("⚙️ Initializing async handlers")

        # Simulate async operations
        await asyncio.sleep(0.1)
        await trace.ainfo("📊 Processing async data with multiple handlers")

        await asyncio.sleep(0.1)
        await trace.ainfo("✅ Async multi-handler workflow completed")

    except Exception as e:
        await trace.aerror(f"💥 Async multi-handler failed: {e}")
    finally:
        trace.close()


def example_conditional_handlers():
    """Example: Conditional handler configuration based on environment."""
    print("\n=== Conditional Handlers Example ===")

    # Simulate different environments
    environments = ["development", "staging", "production"]

    for env in environments:
        print(f"\nTesting environment: {env}")

        # Configure handlers based on environment
        handlers = [
            {
                "type": "file",
                "path": f"./logs/conditional-{env}",
                "buffer_size": 8192,
                "flush_interval": 1.0,
            }
        ]

        # Add environment-specific handlers
        if env == "development":
            handlers.append(
                {
                    "type": "sqlite",
                    "path": f"./logs/conditional_{env}_traces.db",
                    "buffer_size": 50,
                    "flush_interval": 1.0,
                }
            )

        elif env == "staging":
            handlers.extend(
                [
                    {
                        "type": "sqlite",
                        "path": f"./logs/conditional_{env}_traces.db",
                        "buffer_size": 100,
                        "flush_interval": 2.0,
                    },
                    {
                        "type": "restapi",
                        "api_url": "https://httpbin.org/post",
                        "service_type": "generic",
                        "buffer_size": 50,
                        "flush_interval": 2.0,
                    },
                ]
            )

        elif env == "production":
            handlers.extend(
                [
                    {
                        "type": "sqlite",
                        "path": f"./logs/conditional_{env}_traces.db",
                        "buffer_size": 200,
                        "flush_interval": 5.0,
                    },
                    {
                        "type": "restapi",
                        "api_url": "https://httpbin.org/post",
                        "service_type": "generic",
                        "buffer_size": 100,
                        "flush_interval": 5.0,
                    },
                    {
                        "type": "elasticsearch",
                        "es_hosts": "http://localhost:9200",
                        "index_name": f"conditional-{env}-traces",
                        "username": "elastic",
                        "password": "changeme",
                        "buffer_size": 200,
                        "flush_interval": 5.0,
                    },
                ]
            )

        extras = {
            "trace_type": "multi",
            "handlers": handlers,
            "fail_silently": True,
            "workflow_name": f"conditional-{env}-workflow",
            "stage_name": "conditional-stage",
            "job_name": "conditional-job",
            "environment": env,
        }

        trace = get_trace(
            run_id=f"conditional-{env}-{int(time.time())}", extras=extras
        )

        try:
            trace.info(f"🚀 Starting {env} environment workflow")
            trace.debug(
                f"📊 Environment: {env}, Handlers: {trace.handler_count}"
            )

            # Simulate some work
            time.sleep(0.1)

            trace.info(f"✅ {env.capitalize()} environment workflow completed")

        except Exception as e:
            trace.error(f"💥 {env} workflow failed: {e}")
        finally:
            trace.close()


def main():
    """Run all multi-handler tracing examples."""
    print("🔄 Multi-Handler Tracing Examples")
    print("=" * 50)

    try:
        # Run examples
        example_basic_multi_handler()
        example_advanced_multi_handler()
        example_dynamic_handler_management()
        example_handler_inspection()
        example_fail_silently_behavior()
        example_direct_multi_handler()
        example_performance_comparison()
        example_conditional_handlers()

        # Run async example
        asyncio.run(example_async_multi_handler())

        print("\n✅ All multi-handler tracing examples completed!")

    except Exception as e:
        print(f"❌ Error running examples: {e}")


if __name__ == "__main__":
    main()
