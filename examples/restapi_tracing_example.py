#!/usr/bin/env python3
"""
REST API Tracing Example

This example demonstrates how to use the REST API tracing system for
external monitoring services like Datadog, Grafana, AWS CloudWatch,
and generic REST APIs.

Features demonstrated:
- Datadog integration with proper tagging and metadata
- Grafana Loki integration with structured logging
- AWS CloudWatch integration with log groups and streams
- Generic REST API integration
- Batch sending and retry logic
- Performance monitoring and comparison
- Context-aware logging with workflow metadata
"""

import asyncio

# Add the src directory to the path for imports
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ddeutil.workflow.traces import (
    RestAPIHandler,
    get_trace,
)


def example_datadog_integration():
    """Example: Datadog integration with proper tagging and metadata."""
    print("\n=== Datadog Integration Example ===")

    # Configure Datadog tracing
    extras = {
        "trace_type": "restapi",
        "api_url": "https://http-intake.logs.datadoghq.com/v1/input",
        "api_key": "your-datadog-api-key",  # Replace with actual key
        "service_type": "datadog",
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
        run_id=f"datadog-example-{int(time.time())}",
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
        trace.close()


def example_grafana_integration():
    """Example: Grafana Loki integration with structured logging."""
    print("\n=== Grafana Loki Integration Example ===")

    # Configure Grafana tracing
    extras = {
        "trace_type": "restapi",
        "api_url": "http://localhost:3100/loki/api/v1/push",
        "api_key": "your-grafana-api-key",  # Replace with actual key
        "service_type": "grafana",
        "workflow_name": "ml-training-pipeline",
        "stage_name": "model-training",
        "job_name": "train-neural-network",
        "trace_id": str(uuid.uuid4()),
        "span_id": str(uuid.uuid4()),
        "user_id": "ml-engineer-001",
        "tenant_id": "ai-team",
        "environment": "staging",
        "tags": ["service:ml-pipeline", "team:ai"],
    }

    # Create trace instance
    trace = get_trace(
        run_id=f"grafana-example-{int(time.time())}",
        parent_run_id="ml-pipeline-001",
        extras=extras,
    )

    try:
        # Log ML pipeline execution
        trace.info("🧠 Starting ML model training pipeline")
        trace.debug("📊 Loading training dataset")

        # Simulate training steps
        for epoch in range(3):
            time.sleep(0.1)
            trace.info(f"🔄 Training epoch {epoch + 1}/3")
            trace.debug(
                f"📈 Loss: {0.1 + epoch * 0.05:.3f}, Accuracy: {0.8 + epoch * 0.05:.3f}"
            )

        # Log model evaluation
        trace.info("📊 Evaluating model performance")
        trace.debug("🎯 Validation accuracy: 0.92")

        # Log completion
        trace.info("✅ Model training completed successfully")

    except Exception as e:
        trace.error(f"💥 Training failed: {e}")
    finally:
        trace.close()


def example_cloudwatch_integration():
    """Example: AWS CloudWatch integration with log groups and streams."""
    print("\n=== AWS CloudWatch Integration Example ===")

    # Configure CloudWatch tracing
    extras = {
        "trace_type": "restapi",
        "api_url": "https://logs.us-east-1.amazonaws.com",
        "api_key": "your-aws-credentials",  # Replace with actual credentials
        "service_type": "cloudwatch",
        "workflow_name": "etl-pipeline",
        "stage_name": "data-extraction",
        "job_name": "extract-customer-data",
        "trace_id": str(uuid.uuid4()),
        "span_id": str(uuid.uuid4()),
        "user_id": "etl-user",
        "tenant_id": "analytics-team",
        "environment": "production",
        "tags": ["service:etl", "team:analytics"],
    }

    # Create trace instance
    trace = get_trace(
        run_id=f"cloudwatch-example-{int(time.time())}",
        parent_run_id="etl-pipeline-001",
        extras=extras,
    )

    try:
        # Log ETL pipeline execution
        trace.info("🔄 Starting ETL pipeline execution")
        trace.debug("📥 Connecting to source database")

        # Simulate ETL steps
        trace.info("📊 Extracting data from source")
        time.sleep(0.1)

        trace.info("🔄 Transforming data")
        time.sleep(0.1)

        trace.info("📤 Loading data to destination")
        time.sleep(0.1)

        # Log metrics
        trace.info("📈 ETL completed: 10,000 records processed")
        trace.debug("⏱️ Total execution time: 0.3s")

        # Log completion
        trace.info("✅ ETL pipeline completed successfully")

    except Exception as e:
        trace.error(f"💥 ETL pipeline failed: {e}")
    finally:
        trace.close()


def example_generic_rest_api():
    """Example: Generic REST API integration."""
    print("\n=== Generic REST API Integration Example ===")

    # Configure generic REST API tracing
    extras = {
        "trace_type": "restapi",
        "api_url": "https://api.example.com/logs",
        "api_key": "your-api-key",  # Replace with actual key
        "service_type": "generic",
        "workflow_name": "custom-workflow",
        "stage_name": "custom-stage",
        "job_name": "custom-job",
        "trace_id": str(uuid.uuid4()),
        "span_id": str(uuid.uuid4()),
        "user_id": "custom-user",
        "tenant_id": "custom-tenant",
        "environment": "development",
        "tags": ["service:custom", "team:development"],
    }

    # Create trace instance
    trace = get_trace(
        run_id=f"generic-example-{int(time.time())}",
        parent_run_id="custom-workflow-001",
        extras=extras,
    )

    try:
        # Log custom workflow execution
        trace.info("🚀 Starting custom workflow")
        trace.debug("⚙️ Initializing custom components")

        # Simulate custom processing
        for step in range(3):
            time.sleep(0.1)
            trace.info(f"📋 Executing step {step + 1}/3")
            trace.debug(
                f"🔧 Step {step + 1} configuration: {{'param': 'value'}}"
            )

        # Log completion
        trace.info("✅ Custom workflow completed successfully")

    except Exception as e:
        trace.error(f"💥 Custom workflow failed: {e}")
    finally:
        trace.close()


def example_direct_handler_usage():
    """Example: Direct handler usage for custom scenarios."""
    print("\n=== Direct Handler Usage Example ===")

    # Create handler directly
    handler = RestAPIHandler(
        run_id=f"direct-example-{int(time.time())}",
        parent_run_id="direct-parent-001",
        api_url="https://httpbin.org/post",  # Test endpoint
        service_type="generic",
        buffer_size=5,  # Small buffer for testing
        timeout=5.0,
        max_retries=2,
        extras={
            "workflow_name": "direct-handler-test",
            "stage_name": "direct-test",
            "job_name": "test-job",
        },
    )

    # Create logger and add handler
    import logging

    logger = logging.getLogger("direct-test")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    try:
        # Log messages directly
        logger.info("📝 Direct handler test message")
        logger.debug("🔍 Debug information")
        logger.warning("⚠️ Warning message")
        logger.error("❌ Error message")

        # Flush to send buffered messages
        handler.flush()

    except Exception as e:
        print(f"Error in direct handler test: {e}")
    finally:
        handler.close()


def performance_comparison():
    """Compare performance of different REST API configurations."""
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
        handler = RestAPIHandler(
            run_id=f"perf-test-{int(time.time())}",
            api_url="https://httpbin.org/post",
            service_type="generic",
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
        "trace_type": "restapi",
        "api_url": "https://httpbin.org/post",
        "service_type": "generic",
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
        run_id=f"context-example-{int(time.time())}",
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
        trace.close()


async def example_async_logging():
    """Example: Async logging with REST API handler."""
    print("\n=== Async Logging Example ===")

    extras = {
        "trace_type": "restapi",
        "api_url": "https://httpbin.org/post",
        "service_type": "generic",
        "workflow_name": "async-workflow",
        "stage_name": "async-processing",
        "job_name": "async-job",
    }

    trace = get_trace(run_id=f"async-example-{int(time.time())}", extras=extras)

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
        trace.close()


def main():
    """Run all REST API tracing examples."""
    print("🚀 REST API Tracing Examples")
    print("=" * 50)

    # Note: These examples use test endpoints
    # Replace with actual service endpoints and credentials for real usage

    try:
        # Run examples
        example_datadog_integration()
        example_grafana_integration()
        example_cloudwatch_integration()
        example_generic_rest_api()
        example_direct_handler_usage()
        performance_comparison()
        example_context_aware_logging()

        # Run async example
        asyncio.run(example_async_logging())

        print("\n✅ All REST API tracing examples completed!")

    except Exception as e:
        print(f"❌ Error running examples: {e}")


if __name__ == "__main__":
    main()
