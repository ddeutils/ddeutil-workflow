#!/usr/bin/env python3
"""
Elasticsearch Tracing Example

This example demonstrates how to use the Elasticsearch tracing system for
scalable, searchable log storage and aggregation.

Features demonstrated:
- Elasticsearch integration with proper indexing
- Bulk indexing for performance
- Search and query capabilities
- Index management and mapping
- Performance monitoring and comparison
- Context-aware logging with rich metadata
- Async logging support
"""

import asyncio

# Add the src directory to the path for imports
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ddeutil.workflow.traces import (
    ElasticsearchHandler,
    ElasticsearchTrace,
    get_trace,
)


def example_basic_elasticsearch():
    """Example: Basic Elasticsearch integration."""
    print("\n=== Basic Elasticsearch Integration Example ===")

    # Configure Elasticsearch tracing
    extras = {
        "trace_type": "elasticsearch",
        "es_hosts": "http://localhost:9200",
        "index_name": "workflow-traces-demo",
        "username": "elastic",  # Replace with actual credentials
        "password": "changeme",  # Replace with actual credentials
        "workflow_name": "data-processing-pipeline",
        "stage_name": "data-validation",
        "job_name": "validate-customer-data",
        "trace_id": str(uuid.uuid4()),
        "span_id": str(uuid.uuid4()),
        "user_id": "user-123",
        "tenant_id": "tenant-456",
        "environment": "production",
        "tags": ["service:workflow", "team:data-engineering"],
    }

    # Create trace instance
    trace = get_trace(
        run_id=f"es-basic-{int(time.time())}",
        parent_run_id="parent-workflow-001",
        extras=extras,
    )

    try:
        # Log workflow execution
        trace.info("🚀 Starting data processing workflow")
        trace.debug("📊 Initializing data validation stage")

        # Simulate some processing
        time.sleep(0.1)

        # Log with context
        trace.info("✅ Data validation completed successfully")
        trace.debug(f"📈 Processed {1000} records in {0.1:.2f}s")

        # Simulate error scenario
        try:
            raise ValueError("Invalid data format detected")
        except Exception as e:
            trace.error(f"❌ Data validation failed: {e}")
            trace.exception("🔍 Stack trace for debugging")

        # Log completion
        trace.info("🏁 Workflow execution completed")

    except Exception as e:
        trace.error(f"💥 Unexpected error: {e}")
    finally:
        if hasattr(trace, "close"):
            trace.close()


def example_elasticsearch_cluster():
    """Example: Elasticsearch cluster integration."""
    print("\n=== Elasticsearch Cluster Integration Example ===")

    # Configure Elasticsearch cluster tracing
    extras = {
        "trace_type": "elasticsearch",
        "es_hosts": [
            "http://es-node1:9200",
            "http://es-node2:9200",
            "http://es-node3:9200",
        ],
        "index_name": "workflow-traces-cluster",
        "username": "elastic",
        "password": "changeme",
        "workflow_name": "distributed-workflow",
        "stage_name": "distributed-processing",
        "job_name": "process-distributed-data",
        "trace_id": str(uuid.uuid4()),
        "span_id": str(uuid.uuid4()),
        "user_id": "distributed-user",
        "tenant_id": "distributed-tenant",
        "environment": "production",
        "tags": ["service:distributed", "team:platform"],
    }

    # Create trace instance
    trace = get_trace(
        run_id=f"es-cluster-{int(time.time())}",
        parent_run_id="distributed-workflow-001",
        extras=extras,
    )

    try:
        # Log distributed workflow execution
        trace.info("🌐 Starting distributed workflow")
        trace.debug("🔗 Connecting to Elasticsearch cluster")

        # Simulate distributed processing
        for node in range(3):
            time.sleep(0.1)
            trace.info(f"🖥️ Processing on node {node + 1}/3")
            trace.debug(
                f"📊 Node {node + 1} metrics: {{'cpu': 45, 'memory': 60}}"
            )

        # Log completion
        trace.info("✅ Distributed workflow completed successfully")

    except Exception as e:
        trace.error(f"💥 Distributed workflow failed: {e}")
    finally:
        if hasattr(trace, "close"):
            trace.close()


def example_direct_handler_usage():
    """Example: Direct handler usage for custom scenarios."""
    print("\n=== Direct Handler Usage Example ===")

    # Create handler directly
    handler = ElasticsearchHandler(
        run_id=f"direct-es-{int(time.time())}",
        parent_run_id="direct-parent-001",
        es_hosts="http://localhost:9200",
        index_name="direct-handler-test",
        username="elastic",
        password="changeme",
        buffer_size=5,  # Small buffer for testing
        timeout=30.0,
        max_retries=3,
        extras={
            "workflow_name": "direct-handler-test",
            "stage_name": "direct-test",
            "job_name": "test-job",
        },
    )

    # Create logger and add handler
    import logging

    logger = logging.getLogger("direct-es-test")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    try:
        # Log messages directly
        logger.info("📝 Direct Elasticsearch handler test message")
        logger.debug("🔍 Debug information for Elasticsearch")
        logger.warning("⚠️ Warning message in Elasticsearch")
        logger.error("❌ Error message in Elasticsearch")

        # Flush to send buffered messages
        handler.flush()

    except Exception as e:
        print(f"Error in direct handler test: {e}")
    finally:
        handler.close()


def example_search_and_query():
    """Example: Search and query capabilities."""
    print("\n=== Search and Query Example ===")

    # First, create some test data
    extras = {
        "trace_type": "elasticsearch",
        "es_hosts": "http://localhost:9200",
        "index_name": "search-test-index",
        "username": "elastic",
        "password": "changeme",
        "workflow_name": "search-test-workflow",
        "stage_name": "search-test-stage",
        "job_name": "search-test-job",
    }

    # Create trace and add some data
    trace = get_trace(run_id=f"search-test-{int(time.time())}", extras=extras)

    try:
        # Add test data
        trace.info("🔍 Creating test data for search")
        trace.debug("📊 Test debug message")
        trace.warning("⚠️ Test warning message")
        trace.error("❌ Test error message")

        # Wait for indexing
        time.sleep(2)

        # Now search for traces
        print("🔍 Searching for traces...")

        # Find all traces
        traces = list(ElasticsearchTrace.find_traces(extras=extras))
        print(f"📊 Found {len(traces)} trace sessions")

        # Find specific trace
        if traces:
            run_id = traces[0].meta[0].run_id if traces[0].meta else None
            if run_id:
                specific_trace = ElasticsearchTrace.find_trace_with_id(
                    run_id=run_id, extras=extras
                )
                print(
                    f"📋 Found specific trace with {len(specific_trace.meta)} log entries"
                )

    except Exception as e:
        print(f"Error in search example: {e}")
    finally:
        if hasattr(trace, "close"):
            trace.close()


def performance_comparison():
    """Compare performance of different Elasticsearch configurations."""
    print("\n=== Performance Comparison ===")

    configurations = [
        {
            "name": "Small Buffer (10)",
            "buffer_size": 10,
            "flush_interval": 1.0,
        },
        {
            "name": "Medium Buffer (50)",
            "buffer_size": 50,
            "flush_interval": 2.0,
        },
        {
            "name": "Large Buffer (100)",
            "buffer_size": 100,
            "flush_interval": 5.0,
        },
    ]

    for config in configurations:
        print(f"\nTesting: {config['name']}")

        # Create handler with configuration
        handler = ElasticsearchHandler(
            run_id=f"perf-test-{int(time.time())}",
            es_hosts="http://localhost:9200",
            index_name=f"perf-test-{config['name'].lower().replace(' ', '-')}",
            username="elastic",
            password="changeme",
            buffer_size=config["buffer_size"],
            flush_interval=config["flush_interval"],
            extras={"workflow_name": "performance-test"},
        )

        # Create logger
        import logging

        logger = logging.getLogger(f"perf-test-{config['name']}")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        # Measure performance
        start_time = time.time()

        # Send multiple messages
        for i in range(100):
            logger.info(f"Performance test message {i + 1}")

        # Flush remaining messages
        handler.flush()

        end_time = time.time()
        duration = end_time - start_time

        print(f"  Duration: {duration:.3f}s")
        print(f"  Messages per second: {100 / duration:.1f}")

        handler.close()


def example_context_aware_logging():
    """Example: Context-aware logging with rich metadata."""
    print("\n=== Context-Aware Logging Example ===")

    # Create trace with rich context
    extras = {
        "trace_type": "elasticsearch",
        "es_hosts": "http://localhost:9200",
        "index_name": "context-aware-traces",
        "username": "elastic",
        "password": "changeme",
        "workflow_name": "context-aware-workflow",
        "stage_name": "data-processing",
        "job_name": "process-user-data",
        "trace_id": str(uuid.uuid4()),
        "span_id": str(uuid.uuid4()),
        "user_id": "admin-user",
        "tenant_id": "enterprise-tenant",
        "environment": "production",
        "tags": ["service:workflow", "team:platform", "priority:high"],
        "metadata": {
            "deployment_id": "deploy-123",
            "version": "1.2.3",
            "region": "us-west-2",
            "instance_type": "t3.medium",
        },
    }

    trace = get_trace(
        run_id=f"context-es-{int(time.time())}",
        parent_run_id="context-parent-001",
        extras=extras,
    )

    try:
        # Log with different contexts
        trace.info("🔧 Starting context-aware workflow")

        # Simulate different stages with context changes
        for stage in ["validation", "transformation", "loading"]:
            # Update context for this stage
            trace.extras["stage_name"] = stage
            trace.extras["metadata"]["current_stage"] = stage

            trace.info(f"📋 Executing {stage} stage")
            trace.debug(
                "⚙️ Stage configuration: {'mode': 'batch', 'timeout': 30}"
            )

            # Simulate processing
            time.sleep(0.1)

            trace.info(f"✅ {stage.capitalize()} stage completed")

        # Log final completion
        trace.info("🎉 Context-aware workflow completed successfully")

    except Exception as e:
        trace.error(f"💥 Context-aware workflow failed: {e}")
    finally:
        if hasattr(trace, "close"):
            trace.close()


async def example_async_logging():
    """Example: Async logging with Elasticsearch handler."""
    print("\n=== Async Logging Example ===")

    extras = {
        "trace_type": "elasticsearch",
        "es_hosts": "http://localhost:9200",
        "index_name": "async-traces",
        "username": "elastic",
        "password": "changeme",
        "workflow_name": "async-workflow",
        "stage_name": "async-processing",
        "job_name": "async-job",
    }

    trace = get_trace(run_id=f"async-es-{int(time.time())}", extras=extras)

    try:
        # Async logging
        await trace.ainfo("🚀 Starting async workflow")
        await trace.adebug("⚙️ Initializing async components")

        # Simulate async operations
        await asyncio.sleep(0.1)
        await trace.ainfo("📊 Processing async data")

        await asyncio.sleep(0.1)
        await trace.ainfo("✅ Async workflow completed")

    except Exception as e:
        await trace.aerror(f"💥 Async workflow failed: {e}")
    finally:
        if hasattr(trace, "close"):
            trace.close()


def example_index_management():
    """Example: Index management and mapping."""
    print("\n=== Index Management Example ===")

    try:
        from elasticsearch import Elasticsearch

        # Create Elasticsearch client
        client = Elasticsearch(
            hosts=["http://localhost:9200"], basic_auth=("elastic", "changeme")
        )

        # Test connection
        if client.ping():
            print("✅ Connected to Elasticsearch")

            # Get cluster info
            info = client.info()
            print(f"📊 Cluster: {info['cluster_name']}")
            print(f"🔢 Version: {info['version']['number']}")

            # List indices
            indices = client.cat.indices(format="json")
            print(f"📁 Found {len(indices)} indices")

            # Show workflow trace indices
            workflow_indices = [
                idx for idx in indices if "workflow" in idx["index"]
            ]
            for idx in workflow_indices:
                print(f"  - {idx['index']}: {idx['docs.count']} documents")

        else:
            print("❌ Failed to connect to Elasticsearch")

    except ImportError:
        print("❌ Elasticsearch package not installed")
    except Exception as e:
        print(f"❌ Error in index management: {e}")


def example_bulk_operations():
    """Example: Bulk operations for high-volume logging."""
    print("\n=== Bulk Operations Example ===")

    extras = {
        "trace_type": "elasticsearch",
        "es_hosts": "http://localhost:9200",
        "index_name": "bulk-operations-test",
        "username": "elastic",
        "password": "changeme",
        "workflow_name": "bulk-workflow",
        "stage_name": "bulk-processing",
        "job_name": "bulk-job",
    }

    trace = get_trace(run_id=f"bulk-{int(time.time())}", extras=extras)

    try:
        # Log high volume of messages
        trace.info("🚀 Starting bulk operations test")

        start_time = time.time()

        # Send many messages quickly
        for i in range(1000):
            trace.info(f"📝 Bulk message {i + 1}/1000")

            if i % 100 == 0:
                trace.debug(f"📊 Progress: {i + 1}/1000 messages processed")

        end_time = time.time()
        duration = end_time - start_time

        trace.info(f"✅ Bulk operations completed in {duration:.3f}s")
        trace.debug(f"📈 Average: {1000 / duration:.1f} messages/second")

    except Exception as e:
        trace.error(f"💥 Bulk operations failed: {e}")
    finally:
        if hasattr(trace, "close"):
            trace.close()


def main():
    """Run all Elasticsearch tracing examples."""
    print("🔍 Elasticsearch Tracing Examples")
    print("=" * 50)

    # Note: These examples assume Elasticsearch is running on localhost:9200
    # Replace with actual Elasticsearch cluster details for real usage

    try:
        # Run examples
        example_basic_elasticsearch()
        example_elasticsearch_cluster()
        example_direct_handler_usage()
        example_search_and_query()
        performance_comparison()
        example_context_aware_logging()
        example_index_management()
        example_bulk_operations()

        # Run async example
        asyncio.run(example_async_logging())

        print("\n✅ All Elasticsearch tracing examples completed!")

    except Exception as e:
        print(f"❌ Error running examples: {e}")


if __name__ == "__main__":
    main()
