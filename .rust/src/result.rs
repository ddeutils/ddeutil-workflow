//! Result and status management for workflow execution.
//!
//! This module provides the core result types and status enums used throughout
//! the workflow system to track execution state and outcomes.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

use crate::types::DictData;
use crate::trace::TraceModel;

/// Execution status enumeration for workflow components.
///
/// Status enum provides standardized status values for tracking the execution
/// state of workflows, jobs, and stages. Each status includes an emoji
/// representation for visual feedback.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Status {
    /// Successful execution completion
    Success,
    /// Execution failed with errors
    Failed,
    /// Waiting for execution or dependencies
    Wait,
    /// Execution was skipped due to conditions
    Skipped,
    /// Execution was cancelled
    Cancelled,
}

impl Status {
    /// Get emoji representation of the status
    pub fn emoji(&self) -> &'static str {
        match self {
            Status::Success => "✅",
            Status::Failed => "❌",
            Status::Wait => "⏳",
            Status::Skipped => "⏭️",
            Status::Cancelled => "🚫",
        }
    }

    /// Check if status represents a successful execution
    pub fn is_success(&self) -> bool {
        matches!(self, Status::Success)
    }

    /// Check if status represents a failed execution
    pub fn is_failed(&self) -> bool {
        matches!(self, Status::Failed)
    }

    /// Check if status represents a waiting state
    pub fn is_waiting(&self) -> bool {
        matches!(self, Status::Wait)
    }

    /// Check if status represents a skipped execution
    pub fn is_skipped(&self) -> bool {
        matches!(self, Status::Skipped)
    }

    /// Check if status represents a cancelled execution
    pub fn is_cancelled(&self) -> bool {
        matches!(self, Status::Cancelled)
    }

    /// Check if status represents a final state (not waiting)
    pub fn is_final(&self) -> bool {
        !self.is_waiting()
    }

    /// Check if status represents a result state (success or failed)
    pub fn is_result(&self) -> bool {
        matches!(self, Status::Success | Status::Failed)
    }
}

impl std::fmt::Display for Status {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let name = match self {
            Status::Success => "SUCCESS",
            Status::Failed => "FAILED",
            Status::Wait => "WAIT",
            Status::Skipped => "SKIPPED",
            Status::Cancelled => "CANCELLED",
        };
        write!(f, "{} {}", self.emoji(), name)
    }
}

impl Default for Status {
    fn default() -> Self {
        Status::Wait
    }
}

/// Result model for passing and receiving data context from any module execution.
///
/// The Result struct encapsulates the execution outcome, including status,
/// context data, timing information, and tracing details. It provides a
/// comprehensive view of execution state for workflows, jobs, and stages.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Result {
    /// Execution status
    pub status: Status,

    /// Context data containing execution outputs and metadata
    pub context: DictData,

    /// Unique execution identifier
    pub run_id: String,

    /// Parent execution identifier (if nested)
    pub parent_run_id: Option<String>,

    /// Execution timestamp
    pub timestamp: DateTime<Utc>,

    /// Trace model for logging and debugging
    pub trace: Option<TraceModel>,

    /// Extra configuration parameters
    pub extras: DictData,
}

impl Result {
    /// Create a new Result with default values
    pub fn new() -> Self {
        Self {
            status: Status::Wait,
            context: {
                let mut ctx = HashMap::new();
                ctx.insert("status".to_string(), serde_json::json!("WAIT"));
                ctx
            },
            run_id: crate::utils::generate_id("manual", true),
            parent_run_id: None,
            timestamp: Utc::now(),
            trace: None,
            extras: HashMap::new(),
        }
    }

    /// Create a new Result with specified run_id
    pub fn with_run_id(run_id: String) -> Self {
        let mut result = Self::new();
        result.run_id = run_id;
        result
    }

    /// Create a new Result with parent context
    pub fn with_parent(parent_run_id: String) -> Self {
        let mut result = Self::new();
        result.parent_run_id = Some(parent_run_id);
        result
    }

    /// Create a Result from existing result or generate new one
    pub fn from_result_or_new(
        result: Option<Result>,
        run_id: Option<String>,
        parent_run_id: Option<String>,
    ) -> Self {
        match result {
            Some(mut existing) => {
                if let Some(parent_id) = parent_run_id {
                    existing.set_parent_run_id(parent_id);
                }
                existing
            }
            None => {
                let mut new_result = Self::new();
                if let Some(id) = run_id {
                    new_result.run_id = id;
                }
                if let Some(parent_id) = parent_run_id {
                    new_result.parent_run_id = Some(parent_id);
                }
                new_result
            }
        }
    }

    /// Set parent run ID and update trace if needed
    pub fn set_parent_run_id(&mut self, parent_run_id: String) {
        self.parent_run_id = Some(parent_run_id.clone());
        // Update trace with parent context if trace exists
        if let Some(ref mut trace) = self.trace {
            trace.set_parent_run_id(parent_run_id);
        }
    }

    /// Update result with new status and context
    pub fn update(&mut self, status: Status, context: Option<DictData>) {
        self.status = status;

        // Update context with new data
        if let Some(new_context) = context {
            for (key, value) in new_context {
                self.context.insert(key, value);
            }
        }

        // Always update status in context
        self.context.insert("status".to_string(), serde_json::json!(format!("{:?}", status).to_uppercase()));

        // Update timestamp
        self.timestamp = Utc::now();
    }

    /// Merge another result into this one
    pub fn merge(&mut self, other: Result) {
        // Merge context data
        for (key, value) in other.context {
            self.context.insert(key, value);
        }

        // Update status based on priority (Failed > Cancelled > Success > Skipped > Wait)
        self.status = validate_statuses(&[self.status, other.status]);

        // Update context status
        self.context.insert("status".to_string(), serde_json::json!(format!("{:?}", self.status).to_uppercase()));
    }

    /// Get execution duration since creation
    pub fn duration(&self) -> chrono::Duration {
        Utc::now() - self.timestamp
    }

    /// Get execution duration in seconds
    pub fn duration_seconds(&self) -> f64 {
        self.duration().num_milliseconds() as f64 / 1000.0
    }

    /// Check if result has errors in context
    pub fn has_errors(&self) -> bool {
        self.context.contains_key("errors") || self.status.is_failed()
    }

    /// Get error information from context
    pub fn get_errors(&self) -> Option<&serde_json::Value> {
        self.context.get("errors")
    }

    /// Add error to result context
    pub fn add_error(&mut self, error_name: String, error_message: String) {
        let error_entry = serde_json::json!({
            "name": error_name,
            "message": error_message,
            "timestamp": Utc::now()
        });

        match self.context.get_mut("errors") {
            Some(errors) => {
                if let Some(error_array) = errors.as_array_mut() {
                    error_array.push(error_entry);
                } else {
                    // Convert single error to array
                    let existing = errors.clone();
                    *errors = serde_json::json!([existing, error_entry]);
                }
            }
            None => {
                self.context.insert("errors".to_string(), serde_json::json!([error_entry]));
            }
        }

        // Update status to failed if not already in a final failed state
        if !self.status.is_failed() && !self.status.is_cancelled() {
            self.status = Status::Failed;
            self.context.insert("status".to_string(), serde_json::json!("FAILED"));
        }
    }

    /// Get outputs from context
    pub fn get_outputs(&self) -> Option<&serde_json::Value> {
        self.context.get("outputs")
    }

    /// Set outputs in context
    pub fn set_outputs(&mut self, outputs: serde_json::Value) {
        self.context.insert("outputs".to_string(), outputs);
    }

    /// Add output to existing outputs
    pub fn add_output(&mut self, key: String, value: serde_json::Value) {
        match self.context.get_mut("outputs") {
            Some(outputs) => {
                if let Some(output_obj) = outputs.as_object_mut() {
                    output_obj.insert(key, value);
                } else {
                    // Replace non-object outputs with new object
                    self.context.insert("outputs".to_string(), serde_json::json!({ key: value }));
                }
            }
            None => {
                self.context.insert("outputs".to_string(), serde_json::json!({ key: value }));
            }
        }
    }
}

impl Default for Result {
    fn default() -> Self {
        Self::new()
    }
}

/// Determine final status from multiple status values.
///
/// Applies workflow logic to determine the overall status based on a collection
/// of individual status values. Follows priority order: Cancelled > Failed > Wait >
/// individual status consistency.
pub fn validate_statuses(statuses: &[Status]) -> Status {
    if statuses.is_empty() {
        return Status::Wait;
    }

    // Priority order: Cancelled > Failed > Wait > Success/Skipped
    if statuses.iter().any(|s| matches!(s, Status::Cancelled)) {
        return Status::Cancelled;
    }

    if statuses.iter().any(|s| matches!(s, Status::Failed)) {
        return Status::Failed;
    }

    if statuses.iter().any(|s| matches!(s, Status::Wait)) {
        return Status::Wait;
    }

    // Check for consistency in remaining statuses
    let first_status = statuses[0];
    if statuses.iter().all(|s| *s == first_status) {
        return first_status;
    }

    // Mixed success/skipped states default to success
    if statuses.iter().all(|s| matches!(s, Status::Success | Status::Skipped)) {
        return Status::Success;
    }

    // Default fallback
    Status::Failed
}

/// Get status from error type
pub fn get_status_from_error(error: &crate::error::WorkflowError) -> Status {
    use crate::error::{JobError, StageError, WorkflowError};

    match error {
        WorkflowError::Job { source } => match source {
            JobError::Cancelled { .. } => Status::Cancelled,
            JobError::Skipped { .. } => Status::Skipped,
            JobError::Stage { source, .. } => match source {
                StageError::Cancelled { .. } => Status::Cancelled,
                StageError::Skipped { .. } => Status::Skipped,
                _ => Status::Failed,
            },
            _ => Status::Failed,
        },
        _ => Status::Failed,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_status_display() {
        assert_eq!(Status::Success.to_string(), "✅ SUCCESS");
        assert_eq!(Status::Failed.to_string(), "❌ FAILED");
        assert_eq!(Status::Wait.to_string(), "⏳ WAIT");
        assert_eq!(Status::Skipped.to_string(), "⏭️ SKIPPED");
        assert_eq!(Status::Cancelled.to_string(), "🚫 CANCELLED");
    }

    #[test]
    fn test_status_checks() {
        assert!(Status::Success.is_success());
        assert!(Status::Failed.is_failed());
        assert!(Status::Wait.is_waiting());
        assert!(Status::Skipped.is_skipped());
        assert!(Status::Cancelled.is_cancelled());

        assert!(Status::Success.is_final());
        assert!(!Status::Wait.is_final());

        assert!(Status::Success.is_result());
        assert!(Status::Failed.is_result());
        assert!(!Status::Wait.is_result());
    }

    #[test]
    fn test_validate_statuses() {
        assert_eq!(validate_statuses(&[]), Status::Wait);
        assert_eq!(validate_statuses(&[Status::Success, Status::Success]), Status::Success);
        assert_eq!(validate_statuses(&[Status::Success, Status::Failed]), Status::Failed);
        assert_eq!(validate_statuses(&[Status::Success, Status::Cancelled]), Status::Cancelled);
        assert_eq!(validate_statuses(&[Status::Success, Status::Wait]), Status::Wait);
        assert_eq!(validate_statuses(&[Status::Success, Status::Skipped]), Status::Success);
    }

    #[test]
    fn test_result_creation() {
        let result = Result::new();
        assert_eq!(result.status, Status::Wait);
        assert!(!result.run_id.is_empty());
        assert!(result.parent_run_id.is_none());
    }

    #[test]
    fn test_result_update() {
        let mut result = Result::new();

        let mut context = HashMap::new();
        context.insert("test".to_string(), serde_json::json!("value"));

        result.update(Status::Success, Some(context));

        assert_eq!(result.status, Status::Success);
        assert_eq!(result.context.get("test").unwrap(), &serde_json::json!("value"));
        assert_eq!(result.context.get("status").unwrap(), &serde_json::json!("SUCCESS"));
    }

    #[test]
    fn test_result_error_handling() {
        let mut result = Result::new();

        result.add_error("TestError".to_string(), "Test error message".to_string());

        assert!(result.has_errors());
        assert_eq!(result.status, Status::Failed);

        let errors = result.get_errors().unwrap();
        assert!(errors.is_array());
        assert_eq!(errors.as_array().unwrap().len(), 1);
    }

    #[test]
    fn test_result_outputs() {
        let mut result = Result::new();

        result.add_output("key1".to_string(), serde_json::json!("value1"));
        result.add_output("key2".to_string(), serde_json::json!(42));

        let outputs = result.get_outputs().unwrap();
        assert!(outputs.is_object());

        let output_obj = outputs.as_object().unwrap();
        assert_eq!(output_obj.get("key1").unwrap(), &serde_json::json!("value1"));
        assert_eq!(output_obj.get("key2").unwrap(), &serde_json::json!(42));
    }

    #[test]
    fn test_result_merge() {
        let mut result1 = Result::new();
        result1.status = Status::Success;
        result1.context.insert("key1".to_string(), serde_json::json!("value1"));

        let mut result2 = Result::new();
        result2.status = Status::Failed;
        result2.context.insert("key2".to_string(), serde_json::json!("value2"));

        result1.merge(result2);

        assert_eq!(result1.status, Status::Failed); // Failed takes priority
        assert_eq!(result1.context.get("key1").unwrap(), &serde_json::json!("value1"));
        assert_eq!(result1.context.get("key2").unwrap(), &serde_json::json!("value2"));
    }
}
