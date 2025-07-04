# Event API Reference

The Event module provides threading event management for workflow execution control, enabling cancellation, timeout handling, and coordination between concurrent operations.

## Overview

The Event module implements a threading-based event system that provides:

- **Cancellation control**: Graceful termination of long-running operations
- **Timeout management**: Automatic cancellation after specified time limits
- **Thread coordination**: Synchronization between concurrent workflow operations
- **Resource cleanup**: Proper cleanup of resources when operations are cancelled
- **Status monitoring**: Real-time status tracking of event states

## Quick Start

```python
from ddeutil.workflow.event import Event
import threading
import time

# Create an event for cancellation control
event = Event()

# Start a long-running operation in a separate thread
def long_operation():
    for i in range(100):
        if event.is_set():  # Check if cancelled
            print("Operation cancelled")
            return
        time.sleep(0.1)
        print(f"Processing step {i}")
    print("Operation completed")

# Start the operation
thread = threading.Thread(target=long_operation)
thread.start()

# Cancel after 2 seconds
time.sleep(2)
event.set()  # Signal cancellation
thread.join()

print(f"Event status: {event.is_set()}")
```

## Classes

### Event

Threading event wrapper for workflow execution control.

The Event class wraps Python's threading.Event to provide enhanced functionality for workflow execution control. It supports cancellation signals, timeout handling, and status monitoring for concurrent operations.

#### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `_event` | `threading.Event` | - | Internal threading event object |
| `_timeout` | `float \| None` | `None` | Timeout duration in seconds |
| `_start_time` | `float \| None` | `None` | Event start timestamp |

#### Methods

##### `__init__(timeout=None)`

Initialize Event with optional timeout.

**Parameters:**
- `timeout` (float, optional): Timeout duration in seconds

##### `set()`

Set the event flag to True, signaling cancellation or completion.

**Returns:**
- `None`

##### `clear()`

Clear the event flag to False, resetting the event state.

**Returns:**
- `None`

##### `is_set()`

Check if the event flag is set to True.

**Returns:**
- `bool`: True if event is set, False otherwise

##### `wait(timeout=None)`

Wait for the event to be set, with optional timeout.

**Parameters:**
- `timeout` (float, optional): Maximum wait time in seconds

**Returns:**
- `bool`: True if event was set, False if timeout occurred

##### `check_timeout()`

Check if the event has timed out based on the configured timeout.

**Returns:**
- `bool`: True if timeout has occurred, False otherwise

## Usage Examples

### Basic Event Control

```python
from ddeutil.workflow.event import Event
import threading
import time

# Create event with 5-second timeout
event = Event(timeout=5.0)

def monitored_operation():
    """Operation that checks for cancellation."""
    step = 0
    while step < 50:
        if event.is_set():
            print("Operation cancelled by event")
            return

        if event.check_timeout():
            print("Operation timed out")
            return

        # Simulate work
        time.sleep(0.1)
        step += 1
        print(f"Completed step {step}")

    print("Operation completed successfully")

# Start operation in background thread
thread = threading.Thread(target=monitored_operation)
thread.start()

# Let it run for 2 seconds, then cancel
time.sleep(2.0)
event.set()
thread.join()
```

### Workflow Cancellation Control

```python
from ddeutil.workflow import Workflow
from ddeutil.workflow.event import Event
import threading

# Create cancellation event
cancel_event = Event(timeout=300)  # 5-minute timeout

def execute_workflow_with_cancellation():
    """Execute workflow with cancellation support."""
    workflow = Workflow.from_conf('long-running-pipeline')

    try:
        result = workflow.execute(
            params={'batch_size': 10000},
            event=cancel_event
        )
        return result
    except Exception as e:
        if cancel_event.is_set():
            print("Workflow cancelled by user")
        elif cancel_event.check_timeout():
            print("Workflow timed out")
        else:
            print(f"Workflow failed: {e}")
        raise

# Start workflow execution
workflow_thread = threading.Thread(target=execute_workflow_with_cancellation)
workflow_thread.start()

# Simulate user cancellation after 30 seconds
import time
time.sleep(30)
cancel_event.set()
workflow_thread.join()
```

### Multi-Thread Coordination

```python
from ddeutil.workflow.event import Event
import threading
import time

# Shared event for coordination
coordinator_event = Event()

def worker_thread(worker_id, event):
    """Worker thread that responds to coordination events."""
    print(f"Worker {worker_id} started")

    while not event.is_set():
        # Do work
        time.sleep(0.5)
        print(f"Worker {worker_id} processing...")

    print(f"Worker {worker_id} stopping")

# Start multiple worker threads
workers = []
for i in range(3):
    worker = threading.Thread(target=worker_thread, args=(i, coordinator_event))
    workers.append(worker)
    worker.start()

# Let workers run for 3 seconds
time.sleep(3)

# Signal all workers to stop
print("Signaling workers to stop...")
coordinator_event.set()

# Wait for all workers to complete
for worker in workers:
    worker.join()

print("All workers stopped")
```

### Timeout Management

```python
from ddeutil.workflow.event import Event
import threading
import time

def operation_with_timeout(timeout_seconds):
    """Execute operation with timeout control."""
    event = Event(timeout=timeout_seconds)

    def timed_operation():
        start_time = time.time()
        step = 0

        while step < 100:
            if event.is_set():
                print("Operation cancelled")
                return

            if event.check_timeout():
                elapsed = time.time() - start_time
                print(f"Operation timed out after {elapsed:.2f} seconds")
                return

            # Simulate work
            time.sleep(0.1)
            step += 1

        print("Operation completed successfully")

    # Start operation
    thread = threading.Thread(target=timed_operation)
    thread.start()

    # Wait for completion or timeout
    thread.join()

    return event.is_set()

# Test with different timeouts
print("Testing 2-second timeout:")
operation_with_timeout(2.0)

print("\nTesting 10-second timeout:")
operation_with_timeout(10.0)
```

### Resource Cleanup with Events

```python
from ddeutil.workflow.event import Event
import threading
import time
import tempfile
import os

def resource_intensive_operation():
    """Operation that manages resources with cleanup."""
    event = Event(timeout=60)  # 1-minute timeout

    # Create temporary resources
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_dir = tempfile.mkdtemp()

    try:
        def cleanup_resources():
            """Clean up resources when cancelled or completed."""
            print("Cleaning up resources...")
            try:
                os.unlink(temp_file.name)
                os.rmdir(temp_dir)
                print("Resources cleaned up successfully")
            except Exception as e:
                print(f"Error during cleanup: {e}")

        def main_operation():
            """Main operation with periodic cancellation checks."""
            step = 0
            while step < 1000:
                if event.is_set():
                    print("Operation cancelled, cleaning up...")
                    cleanup_resources()
                    return

                if event.check_timeout():
                    print("Operation timed out, cleaning up...")
                    cleanup_resources()
                    return

                # Simulate work with resource usage
                temp_file.write(f"Step {step}\n".encode())
                temp_file.flush()

                time.sleep(0.1)
                step += 1

            print("Operation completed, cleaning up...")
            cleanup_resources()

        # Start operation
        thread = threading.Thread(target=main_operation)
        thread.start()

        # Simulate cancellation after 3 seconds
        time.sleep(3)
        event.set()

        thread.join()

    except Exception as e:
        print(f"Error in operation: {e}")
        cleanup_resources()

# Run resource-intensive operation
resource_intensive_operation()
```

### Event-Based Workflow Orchestration

```python
from ddeutil.workflow.event import Event
import threading
import time

class WorkflowOrchestrator:
    """Orchestrator for managing multiple workflows with event control."""

    def __init__(self):
        self.global_cancel_event = Event()
        self.workflow_events = {}
        self.workflow_threads = {}

    def start_workflow(self, workflow_id, workflow_func, timeout=300):
        """Start a workflow with its own event control."""
        if workflow_id in self.workflow_events:
            raise ValueError(f"Workflow {workflow_id} already running")

        # Create workflow-specific event
        workflow_event = Event(timeout=timeout)
        self.workflow_events[workflow_id] = workflow_event

        def workflow_wrapper():
            """Wrapper that handles both global and workflow-specific events."""
            try:
                workflow_func(workflow_event)
            except Exception as e:
                print(f"Workflow {workflow_id} failed: {e}")
            finally:
                # Clean up
                if workflow_id in self.workflow_events:
                    del self.workflow_events[workflow_id]
                if workflow_id in self.workflow_threads:
                    del self.workflow_threads[workflow_id]

        # Start workflow thread
        thread = threading.Thread(target=workflow_wrapper)
        self.workflow_threads[workflow_id] = thread
        thread.start()

        print(f"Started workflow {workflow_id}")

    def cancel_workflow(self, workflow_id):
        """Cancel a specific workflow."""
        if workflow_id in self.workflow_events:
            self.workflow_events[workflow_id].set()
            print(f"Cancelled workflow {workflow_id}")

    def cancel_all_workflows(self):
        """Cancel all running workflows."""
        self.global_cancel_event.set()
        for workflow_id in list(self.workflow_events.keys()):
            self.cancel_workflow(workflow_id)
        print("Cancelled all workflows")

    def wait_for_workflow(self, workflow_id, timeout=None):
        """Wait for a specific workflow to complete."""
        if workflow_id in self.workflow_threads:
            self.workflow_threads[workflow_id].join(timeout=timeout)

    def wait_for_all_workflows(self):
        """Wait for all workflows to complete."""
        for thread in self.workflow_threads.values():
            thread.join()

# Example usage
def sample_workflow(event):
    """Sample workflow that responds to cancellation events."""
    step = 0
    while step < 50:
        if event.is_set():
            print("Workflow cancelled")
            return
        time.sleep(0.2)
        step += 1
    print("Workflow completed")

# Create orchestrator
orchestrator = WorkflowOrchestrator()

# Start multiple workflows
orchestrator.start_workflow("workflow-1", sample_workflow, timeout=10)
orchestrator.start_workflow("workflow-2", sample_workflow, timeout=15)
orchestrator.start_workflow("workflow-3", sample_workflow, timeout=20)

# Let them run for 3 seconds
time.sleep(3)

# Cancel specific workflow
orchestrator.cancel_workflow("workflow-1")

# Let remaining workflows run for 2 more seconds
time.sleep(2)

# Cancel all workflows
orchestrator.cancel_all_workflows()

# Wait for all to complete
orchestrator.wait_for_all_workflows()
```

### Event-Based Monitoring

```python
from ddeutil.workflow.event import Event
import threading
import time
import psutil

class SystemMonitor:
    """Monitor system resources with event-based control."""

    def __init__(self, threshold_cpu=80, threshold_memory=80):
        self.threshold_cpu = threshold_cpu
        self.threshold_memory = threshold_memory
        self.stop_event = Event()
        self.alert_event = Event()

    def start_monitoring(self):
        """Start system monitoring in background thread."""
        def monitor_loop():
            while not self.stop_event.is_set():
                # Check CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                memory_percent = psutil.virtual_memory().percent

                print(f"CPU: {cpu_percent:.1f}%, Memory: {memory_percent:.1f}%")

                # Trigger alert if thresholds exceeded
                if cpu_percent > self.threshold_cpu or memory_percent > self.threshold_memory:
                    self.alert_event.set()
                    print("System resource threshold exceeded!")

                time.sleep(2)

        thread = threading.Thread(target=monitor_loop)
        thread.start()
        return thread

    def stop_monitoring(self):
        """Stop system monitoring."""
        self.stop_event.set()

    def wait_for_alert(self, timeout=None):
        """Wait for system alert."""
        return self.alert_event.wait(timeout=timeout)

# Example usage
monitor = SystemMonitor(threshold_cpu=50, threshold_memory=70)
monitor_thread = monitor.start_monitoring()

# Simulate high CPU usage
def cpu_intensive_task():
    """Simulate CPU-intensive work."""
    while True:
        # Busy loop to consume CPU
        pass

# Start CPU-intensive task
cpu_thread = threading.Thread(target=cpu_intensive_task)
cpu_thread.start()

# Wait for alert
if monitor.wait_for_alert(timeout=10):
    print("Received system alert!")

    # Stop CPU-intensive task
    cpu_thread.join(timeout=1)
    if cpu_thread.is_alive():
        print("Force stopping CPU task...")

# Stop monitoring
monitor.stop_monitoring()
monitor_thread.join()
```

## Event Patterns

### Producer-Consumer Pattern

```python
from ddeutil.workflow.event import Event
import threading
import queue
import time

class ProducerConsumer:
    """Producer-consumer pattern with event-based control."""

    def __init__(self, max_queue_size=10):
        self.queue = queue.Queue(maxsize=max_queue_size)
        self.stop_event = Event()
        self.producer_thread = None
        self.consumer_thread = None

    def producer(self):
        """Producer that generates items."""
        item = 0
        while not self.stop_event.is_set():
            try:
                self.queue.put(item, timeout=1)
                print(f"Produced item {item}")
                item += 1
                time.sleep(0.5)
            except queue.Full:
                print("Queue full, waiting...")

    def consumer(self):
        """Consumer that processes items."""
        while not self.stop_event.is_set():
            try:
                item = self.queue.get(timeout=1)
                print(f"Consumed item {item}")
                self.queue.task_done()
                time.sleep(0.2)
            except queue.Empty:
                print("Queue empty, waiting...")

    def start(self):
        """Start producer and consumer threads."""
        self.producer_thread = threading.Thread(target=self.producer)
        self.consumer_thread = threading.Thread(target=self.consumer)

        self.producer_thread.start()
        self.consumer_thread.start()

    def stop(self):
        """Stop producer and consumer threads."""
        self.stop_event.set()

        if self.producer_thread:
            self.producer_thread.join()
        if self.consumer_thread:
            self.consumer_thread.join()

# Example usage
pc = ProducerConsumer(max_queue_size=5)
pc.start()

# Let it run for 5 seconds
time.sleep(5)

# Stop the system
pc.stop()
```

### Barrier Pattern

```python
from ddeutil.workflow.event import Event
import threading
import time

class EventBarrier:
    """Barrier pattern using events for synchronization."""

    def __init__(self, parties):
        self.parties = parties
        self.count = parties
        self.event = Event()
        self.lock = threading.Lock()

    def wait(self):
        """Wait for all parties to reach the barrier."""
        with self.lock:
            self.count -= 1
            if self.count == 0:
                # Last party to arrive, release all
                self.event.set()

        # Wait for release
        self.event.wait()

        # Reset for next use
        with self.lock:
            self.count += 1
            if self.count == self.parties:
                self.event.clear()

def worker(worker_id, barrier):
    """Worker that waits at barrier."""
    print(f"Worker {worker_id} starting")
    time.sleep(worker_id * 0.5)  # Simulate different start times

    print(f"Worker {worker_id} waiting at barrier")
    barrier.wait()

    print(f"Worker {worker_id} passed barrier")

# Create barrier for 3 workers
barrier = EventBarrier(3)

# Start workers
threads = []
for i in range(3):
    thread = threading.Thread(target=worker, args=(i, barrier))
    threads.append(thread)
    thread.start()

# Wait for all workers to complete
for thread in threads:
    thread.join()

print("All workers completed")
```

## Best Practices

### 1. Event Design

- **Clear purpose**: Use events for specific control purposes (cancellation, coordination, etc.)
- **Timeout handling**: Always set appropriate timeouts for long-running operations
- **Resource cleanup**: Ensure proper cleanup when events are triggered
- **Status checking**: Regularly check event status in long-running loops

### 2. Thread Safety

- **Atomic operations**: Use events for thread-safe signaling
- **Race conditions**: Avoid race conditions by checking event status before operations
- **Memory barriers**: Events provide implicit memory barriers for thread coordination
- **Deadlock prevention**: Design event usage to prevent deadlocks

### 3. Performance

- **Efficient checking**: Check event status at appropriate intervals
- **Minimal overhead**: Events have minimal performance impact
- **Resource management**: Clean up event-related resources promptly
- **Monitoring**: Monitor event usage for performance bottlenecks

### 4. Error Handling

- **Exception safety**: Handle exceptions properly in event-driven code
- **Timeout handling**: Implement proper timeout handling for all operations
- **Graceful shutdown**: Ensure graceful shutdown when events are triggered
- **Error propagation**: Propagate errors appropriately in event handlers

### 5. Debugging

- **Event logging**: Log event state changes for debugging
- **Timeout debugging**: Track timeout occurrences and durations
- **Thread monitoring**: Monitor thread states during event operations
- **Resource tracking**: Track resource usage in event-driven operations

## Troubleshooting

### Common Issues

#### Event Not Triggering

```python
# Problem: Event not triggering as expected
event = Event()

def check_event_status():
    """Debug event status."""
    print(f"Event is set: {event.is_set()}")
    print(f"Event timeout check: {event.check_timeout()}")

# Check event status before and after setting
check_event_status()
event.set()
check_event_status()
```

#### Timeout Issues

```python
# Problem: Timeout not working as expected
import time

event = Event(timeout=5.0)
start_time = time.time()

def monitor_timeout():
    """Monitor timeout behavior."""
    while not event.is_set():
        elapsed = time.time() - start_time
        print(f"Elapsed time: {elapsed:.2f}s")

        if event.check_timeout():
            print("Timeout detected")
            break

        time.sleep(0.5)

monitor_timeout()
```

#### Thread Coordination Issues

```python
# Problem: Threads not coordinating properly
from ddeutil.workflow.event import Event
import threading

coordinator = Event()
threads = []

def worker(worker_id):
    """Worker that coordinates with others."""
    print(f"Worker {worker_id} starting")
    coordinator.wait()  # Wait for coordination signal
    print(f"Worker {worker_id} continuing")

# Start multiple workers
for i in range(3):
    thread = threading.Thread(target=worker, args=(i,))
    threads.append(thread)
    thread.start()

# Let workers start, then coordinate
time.sleep(1)
print("Coordinating workers...")
coordinator.set()

# Wait for all workers
for thread in threads:
    thread.join()
```

### Debugging Tips

1. **Enable event logging**: Log event state changes for debugging
2. **Monitor thread states**: Check thread states during event operations
3. **Use timeouts**: Always set timeouts to prevent indefinite waiting
4. **Check event status**: Regularly check event status in long-running operations
5. **Resource cleanup**: Ensure proper cleanup when events are triggered

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKFLOW_CORE_EVENT_DEFAULT_TIMEOUT` | `300` | Default event timeout in seconds |
| `WORKFLOW_CORE_EVENT_CHECK_INTERVAL` | `0.1` | Default event check interval in seconds |

### Event Usage Patterns

```python
# Basic cancellation pattern
event = Event(timeout=60)
try:
    long_running_operation(event)
except Exception as e:
    if event.is_set():
        print("Operation cancelled")
    elif event.check_timeout():
        print("Operation timed out")
    else:
        print(f"Operation failed: {e}")

# Coordination pattern
coordinator = Event()
threads = [threading.Thread(target=worker, args=(coordinator,)) for _ in range(3)]
for thread in threads:
    thread.start()
coordinator.set()  # Release all threads
for thread in threads:
    thread.join()

# Timeout pattern
event = Event(timeout=30)
thread = threading.Thread(target=timed_operation, args=(event,))
thread.start()
thread.join()
```
