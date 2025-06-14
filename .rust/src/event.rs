//! Event handling module for workflow execution events.
//!
//! This module provides functionality to handle and process events that occur
//! during workflow execution, including stage completion, errors, and notifications.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fmt;
use tokio::sync::broadcast;

use crate::error::WorkflowResult;
use crate::types::DictData;

/// Event type enumeration
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EventType {
    /// Workflow started
    WorkflowStarted,
    /// Workflow completed successfully
    WorkflowCompleted,
    /// Workflow failed
    WorkflowFailed,
    /// Stage started
    StageStarted,
    /// Stage completed
    StageCompleted,
    /// Stage failed
    StageFailed,
    /// Stage skipped
    StageSkipped,
    /// Job started
    JobStarted,
    /// Job completed
    JobCompleted,
    /// Job failed
    JobFailed,
    /// Custom event
    Custom(String),
}

impl fmt::Display for EventType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            EventType::WorkflowStarted => write!(f, "workflow_started"),
            EventType::WorkflowCompleted => write!(f, "workflow_completed"),
            EventType::WorkflowFailed => write!(f, "workflow_failed"),
            EventType::StageStarted => write!(f, "stage_started"),
            EventType::StageCompleted => write!(f, "stage_completed"),
            EventType::StageFailed => write!(f, "stage_failed"),
            EventType::StageSkipped => write!(f, "stage_skipped"),
            EventType::JobStarted => write!(f, "job_started"),
            EventType::JobCompleted => write!(f, "job_completed"),
            EventType::JobFailed => write!(f, "job_failed"),
            EventType::Custom(name) => write!(f, "custom_{}", name),
        }
    }
}

/// Event priority levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Priority {
    /// Low priority events
    Low,
    /// Normal priority events
    Normal,
    /// High priority events
    High,
    /// Critical priority events
    Critical,
}

impl Default for Priority {
    fn default() -> Self {
        Priority::Normal
    }
}

/// Workflow event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Event {
    /// Unique event ID
    pub id: String,

    /// Event type
    pub event_type: EventType,

    /// Event timestamp
    pub timestamp: DateTime<Utc>,

    /// Event priority
    pub priority: Priority,

    /// Workflow ID
    pub workflow_id: Option<String>,

    /// Job ID
    pub job_id: Option<String>,

    /// Stage ID
    pub stage_id: Option<String>,

    /// Event message
    pub message: String,

    /// Additional event data
    pub data: DictData,

    /// Error information (if applicable)
    pub error: Option<String>,

    /// Event source
    pub source: String,

    /// Event tags for filtering
    pub tags: Vec<String>,
}

impl Event {
    /// Create new event
    pub fn new(event_type: EventType, message: String) -> Self {
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            event_type,
            timestamp: Utc::now(),
            priority: Priority::default(),
            workflow_id: None,
            job_id: None,
            stage_id: None,
            message,
            data: HashMap::new(),
            error: None,
            source: "workflow".to_string(),
            tags: Vec::new(),
        }
    }

    /// Set workflow ID
    pub fn with_workflow_id(mut self, workflow_id: String) -> Self {
        self.workflow_id = Some(workflow_id);
        self
    }

    /// Set job ID
    pub fn with_job_id(mut self, job_id: String) -> Self {
        self.job_id = Some(job_id);
        self
    }

    /// Set stage ID
    pub fn with_stage_id(mut self, stage_id: String) -> Self {
        self.stage_id = Some(stage_id);
        self
    }

    /// Set priority
    pub fn with_priority(mut self, priority: Priority) -> Self {
        self.priority = priority;
        self
    }

    /// Add event data
    pub fn with_data(mut self, key: String, value: serde_json::Value) -> Self {
        self.data.insert(key, value);
        self
    }

    /// Set error
    pub fn with_error(mut self, error: String) -> Self {
        self.error = Some(error);
        self
    }

    /// Set source
    pub fn with_source(mut self, source: String) -> Self {
        self.source = source;
        self
    }

    /// Add tag
    pub fn with_tag(mut self, tag: String) -> Self {
        self.tags.push(tag);
        self
    }

    /// Add multiple tags
    pub fn with_tags(mut self, tags: Vec<String>) -> Self {
        self.tags.extend(tags);
        self
    }

    /// Check if event matches filter
    pub fn matches_filter(&self, filter: &EventFilter) -> bool {
        // Check event type
        if let Some(event_types) = &filter.event_types {
            if !event_types.contains(&self.event_type) {
                return false;
            }
        }

        // Check priority
        if let Some(min_priority) = filter.min_priority {
            if self.priority < min_priority {
                return false;
            }
        }

        // Check workflow ID
        if let Some(workflow_id) = &filter.workflow_id {
            if self.workflow_id.as_ref() != Some(workflow_id) {
                return false;
            }
        }

        // Check job ID
        if let Some(job_id) = &filter.job_id {
            if self.job_id.as_ref() != Some(job_id) {
                return false;
            }
        }

        // Check stage ID
        if let Some(stage_id) = &filter.stage_id {
            if self.stage_id.as_ref() != Some(stage_id) {
                return false;
            }
        }

        // Check tags
        if !filter.tags.is_empty() {
            if !filter.tags.iter().any(|tag| self.tags.contains(tag)) {
                return false;
            }
        }

        // Check time range
        if let Some(start_time) = filter.start_time {
            if self.timestamp < start_time {
                return false;
            }
        }

        if let Some(end_time) = filter.end_time {
            if self.timestamp > end_time {
                return false;
            }
        }

        true
    }
}

/// Event filter for subscribing to specific events
#[derive(Debug, Clone, Default)]
pub struct EventFilter {
    /// Filter by event types
    pub event_types: Option<Vec<EventType>>,

    /// Filter by minimum priority
    pub min_priority: Option<Priority>,

    /// Filter by workflow ID
    pub workflow_id: Option<String>,

    /// Filter by job ID
    pub job_id: Option<String>,

    /// Filter by stage ID
    pub stage_id: Option<String>,

    /// Filter by tags
    pub tags: Vec<String>,

    /// Filter by start time
    pub start_time: Option<DateTime<Utc>>,

    /// Filter by end time
    pub end_time: Option<DateTime<Utc>>,
}

impl EventFilter {
    /// Create new event filter
    pub fn new() -> Self {
        Self::default()
    }

    /// Filter by event types
    pub fn with_event_types(mut self, event_types: Vec<EventType>) -> Self {
        self.event_types = Some(event_types);
        self
    }

    /// Filter by minimum priority
    pub fn with_min_priority(mut self, priority: Priority) -> Self {
        self.min_priority = Some(priority);
        self
    }

    /// Filter by workflow ID
    pub fn with_workflow_id(mut self, workflow_id: String) -> Self {
        self.workflow_id = Some(workflow_id);
        self
    }

    /// Filter by job ID
    pub fn with_job_id(mut self, job_id: String) -> Self {
        self.job_id = Some(job_id);
        self
    }

    /// Filter by stage ID
    pub fn with_stage_id(mut self, stage_id: String) -> Self {
        self.stage_id = Some(stage_id);
        self
    }

    /// Filter by tags
    pub fn with_tags(mut self, tags: Vec<String>) -> Self {
        self.tags = tags;
        self
    }

    /// Filter by time range
    pub fn with_time_range(mut self, start: DateTime<Utc>, end: DateTime<Utc>) -> Self {
        self.start_time = Some(start);
        self.end_time = Some(end);
        self
    }
}

/// Event handler trait
#[async_trait::async_trait]
pub trait EventHandler: Send + Sync {
    /// Handle event
    async fn handle(&self, event: &Event) -> WorkflowResult<()>;

    /// Get handler name
    fn name(&self) -> &str;

    /// Check if handler can handle event
    fn can_handle(&self, event: &Event) -> bool {
        // Default implementation accepts all events
        let _ = event;
        true
    }
}

/// Event bus for managing event subscriptions and publishing
#[derive(Debug)]
pub struct EventBus {
    /// Broadcast channel for events
    sender: broadcast::Sender<Event>,

    /// Event handlers
    handlers: Vec<Box<dyn EventHandler>>,
}

impl EventBus {
    /// Create new event bus
    pub fn new(capacity: usize) -> Self {
        let (sender, _) = broadcast::channel(capacity);

        Self {
            sender,
            handlers: Vec::new(),
        }
    }

    /// Add event handler
    pub fn add_handler(&mut self, handler: Box<dyn EventHandler>) {
        self.handlers.push(handler);
    }

    /// Publish event
    pub async fn publish(&self, event: Event) -> WorkflowResult<()> {
        // Send to broadcast channel
        let _ = self.sender.send(event.clone());

        // Send to handlers
        for handler in &self.handlers {
            if handler.can_handle(&event) {
                if let Err(e) = handler.handle(&event).await {
                    tracing::error!("Event handler '{}' failed: {}", handler.name(), e);
                }
            }
        }

        Ok(())
    }

    /// Subscribe to events with filter
    pub fn subscribe(&self, filter: EventFilter) -> EventSubscription {
        let receiver = self.sender.subscribe();
        EventSubscription::new(receiver, filter)
    }

    /// Get sender for publishing events
    pub fn sender(&self) -> &broadcast::Sender<Event> {
        &self.sender
    }
}

/// Event subscription for receiving filtered events
pub struct EventSubscription {
    /// Broadcast receiver
    receiver: broadcast::Receiver<Event>,

    /// Event filter
    filter: EventFilter,
}

impl EventSubscription {
    /// Create new event subscription
    pub fn new(receiver: broadcast::Receiver<Event>, filter: EventFilter) -> Self {
        Self { receiver, filter }
    }

    /// Receive next event that matches filter
    pub async fn recv(&mut self) -> Result<Event, broadcast::error::RecvError> {
        loop {
            let event = self.receiver.recv().await?;
            if event.matches_filter(&self.filter) {
                return Ok(event);
            }
        }
    }

    /// Try to receive event without blocking
    pub fn try_recv(&mut self) -> Result<Event, broadcast::error::TryRecvError> {
        loop {
            let event = self.receiver.try_recv()?;
            if event.matches_filter(&self.filter) {
                return Ok(event);
            }
        }
    }
}

/// Console event handler for logging events
pub struct ConsoleEventHandler {
    /// Handler name
    name: String,

    /// Event filter
    filter: EventFilter,
}

impl ConsoleEventHandler {
    /// Create new console event handler
    pub fn new() -> Self {
        Self {
            name: "console".to_string(),
            filter: EventFilter::new(),
        }
    }

    /// Create with filter
    pub fn with_filter(filter: EventFilter) -> Self {
        Self {
            name: "console".to_string(),
            filter,
        }
    }
}

impl Default for ConsoleEventHandler {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait::async_trait]
impl EventHandler for ConsoleEventHandler {
    async fn handle(&self, event: &Event) -> WorkflowResult<()> {
        let timestamp = event.timestamp.format("%Y-%m-%d %H:%M:%S UTC");
        let priority_icon = match event.priority {
            Priority::Low => "🟢",
            Priority::Normal => "🔵",
            Priority::High => "🟡",
            Priority::Critical => "🔴",
        };

        println!(
            "{} {} [{}] {} - {}",
            timestamp,
            priority_icon,
            event.event_type,
            event.source,
            event.message
        );

        if let Some(error) = &event.error {
            println!("  Error: {}", error);
        }

        if !event.data.is_empty() {
            println!("  Data: {}", serde_json::to_string_pretty(&event.data).unwrap_or_default());
        }

        Ok(())
    }

    fn name(&self) -> &str {
        &self.name
    }

    fn can_handle(&self, event: &Event) -> bool {
        event.matches_filter(&self.filter)
    }
}

/// Helper functions for creating common events
pub mod helpers {
    use super::*;

    /// Create workflow started event
    pub fn workflow_started(workflow_id: String, message: String) -> Event {
        Event::new(EventType::WorkflowStarted, message)
            .with_workflow_id(workflow_id)
            .with_priority(Priority::Normal)
    }

    /// Create workflow completed event
    pub fn workflow_completed(workflow_id: String, duration_ms: u64) -> Event {
        Event::new(
            EventType::WorkflowCompleted,
            format!("Workflow completed in {}ms", duration_ms),
        )
        .with_workflow_id(workflow_id)
        .with_data("duration_ms".to_string(), serde_json::json!(duration_ms))
        .with_priority(Priority::Normal)
    }

    /// Create workflow failed event
    pub fn workflow_failed(workflow_id: String, error: String) -> Event {
        Event::new(EventType::WorkflowFailed, "Workflow failed".to_string())
            .with_workflow_id(workflow_id)
            .with_error(error)
            .with_priority(Priority::High)
    }

    /// Create stage started event
    pub fn stage_started(workflow_id: String, stage_id: String, stage_name: String) -> Event {
        Event::new(
            EventType::StageStarted,
            format!("Stage '{}' started", stage_name),
        )
        .with_workflow_id(workflow_id)
        .with_stage_id(stage_id)
        .with_data("stage_name".to_string(), serde_json::json!(stage_name))
        .with_priority(Priority::Normal)
    }

    /// Create stage completed event
    pub fn stage_completed(
        workflow_id: String,
        stage_id: String,
        stage_name: String,
        duration_ms: u64,
    ) -> Event {
        Event::new(
            EventType::StageCompleted,
            format!("Stage '{}' completed in {}ms", stage_name, duration_ms),
        )
        .with_workflow_id(workflow_id)
        .with_stage_id(stage_id)
        .with_data("stage_name".to_string(), serde_json::json!(stage_name))
        .with_data("duration_ms".to_string(), serde_json::json!(duration_ms))
        .with_priority(Priority::Normal)
    }

    /// Create stage failed event
    pub fn stage_failed(
        workflow_id: String,
        stage_id: String,
        stage_name: String,
        error: String,
    ) -> Event {
        Event::new(
            EventType::StageFailed,
            format!("Stage '{}' failed", stage_name),
        )
        .with_workflow_id(workflow_id)
        .with_stage_id(stage_id)
        .with_data("stage_name".to_string(), serde_json::json!(stage_name))
        .with_error(error)
        .with_priority(Priority::High)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_event_creation() {
        let event = Event::new(
            EventType::WorkflowStarted,
            "Test workflow started".to_string(),
        )
        .with_workflow_id("test-workflow".to_string())
        .with_priority(Priority::High)
        .with_tag("test".to_string());

        assert_eq!(event.event_type, EventType::WorkflowStarted);
        assert_eq!(event.message, "Test workflow started");
        assert_eq!(event.workflow_id, Some("test-workflow".to_string()));
        assert_eq!(event.priority, Priority::High);
        assert!(event.tags.contains(&"test".to_string()));
    }

    #[test]
    fn test_event_filter() {
        let event = Event::new(
            EventType::StageCompleted,
            "Stage completed".to_string(),
        )
        .with_workflow_id("test-workflow".to_string())
        .with_stage_id("test-stage".to_string())
        .with_priority(Priority::Normal)
        .with_tag("production".to_string());

        let filter = EventFilter::new()
            .with_event_types(vec![EventType::StageCompleted, EventType::StageFailed])
            .with_workflow_id("test-workflow".to_string())
            .with_min_priority(Priority::Low);

        assert!(event.matches_filter(&filter));

        let restrictive_filter = EventFilter::new()
            .with_event_types(vec![EventType::WorkflowStarted])
            .with_workflow_id("other-workflow".to_string());

        assert!(!event.matches_filter(&restrictive_filter));
    }

    #[tokio::test]
    async fn test_event_bus() {
        let mut event_bus = EventBus::new(100);

        let handler = Box::new(ConsoleEventHandler::new());
        event_bus.add_handler(handler);

        let event = Event::new(
            EventType::WorkflowStarted,
            "Test workflow started".to_string(),
        );

        let result = event_bus.publish(event).await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_event_subscription() {
        let event_bus = EventBus::new(100);

        let filter = EventFilter::new()
            .with_event_types(vec![EventType::WorkflowStarted]);

        let mut subscription = event_bus.subscribe(filter);

        // Publish matching event
        let event = Event::new(
            EventType::WorkflowStarted,
            "Test workflow started".to_string(),
        );

        let _ = event_bus.publish(event.clone()).await;

        // Should receive the event
        let received = tokio::time::timeout(
            std::time::Duration::from_millis(100),
            subscription.recv()
        ).await;

        assert!(received.is_ok());
        let received_event = received.unwrap().unwrap();
        assert_eq!(received_event.event_type, EventType::WorkflowStarted);
    }

    #[test]
    fn test_helper_functions() {
        use helpers::*;

        let event = workflow_started(
            "test-workflow".to_string(),
            "Workflow started".to_string(),
        );
        assert_eq!(event.event_type, EventType::WorkflowStarted);
        assert_eq!(event.workflow_id, Some("test-workflow".to_string()));

        let event = workflow_failed(
            "test-workflow".to_string(),
            "Something went wrong".to_string(),
        );
        assert_eq!(event.event_type, EventType::WorkflowFailed);
        assert_eq!(event.priority, Priority::High);
        assert!(event.error.is_some());

        let event = stage_completed(
            "test-workflow".to_string(),
            "test-stage".to_string(),
            "Test Stage".to_string(),
            1500,
        );
        assert_eq!(event.event_type, EventType::StageCompleted);
        assert!(event.data.contains_key("duration_ms"));
    }
}
