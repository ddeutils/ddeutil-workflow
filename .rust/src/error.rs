//! Error types for the workflow orchestration system.
//!
//! This module defines all error types used throughout the workflow engine,
//! providing structured error handling with detailed context information.

use serde::{Deserialize, Serialize};
use std::fmt;
use thiserror::Error;

/// Main error type for workflow operations
#[derive(Error, Debug, Clone, Serialize, Deserialize)]
pub enum WorkflowError {
    #[error("Configuration error: {message}")]
    Config { message: String },

    #[error("Validation error: {message}")]
    Validation { message: String },

    #[error("Execution error: {message}")]
    Execution { message: String },

    #[error("Timeout error: operation timed out after {seconds} seconds")]
    Timeout { seconds: u64 },

    #[error("Dependency error: {message}")]
    Dependency { message: String },

    #[error("Template error: {message}")]
    Template { message: String },

    #[error("IO error: {message}")]
    Io { message: String },

    #[error("Job error: {source}")]
    Job {
        #[from]
        source: JobError,
    },
}

/// Error type for job execution
#[derive(Error, Debug, Clone, Serialize, Deserialize)]
pub enum JobError {
    #[error("Job '{job_id}' execution failed: {message}")]
    Execution { job_id: String, message: String },

    #[error("Job '{job_id}' was cancelled")]
    Cancelled { job_id: String },

    #[error("Job '{job_id}' was skipped: {reason}")]
    Skipped { job_id: String, reason: String },

    #[error("Job '{job_id}' dependency failed: {dependency}")]
    DependencyFailed { job_id: String, dependency: String },

    #[error("Job '{job_id}' condition not met: {condition}")]
    ConditionNotMet { job_id: String, condition: String },

    #[error("Job '{job_id}' timeout after {seconds} seconds")]
    Timeout { job_id: String, seconds: u64 },

    #[error("Stage error in job '{job_id}': {source}")]
    Stage {
        job_id: String,
        #[from]
        source: StageError,
    },
}

/// Error type for stage execution
#[derive(Error, Debug, Clone, Serialize, Deserialize)]
pub enum StageError {
    #[error("Stage '{stage_name}' execution failed: {message}")]
    Execution { stage_name: String, message: String },

    #[error("Stage '{stage_name}' was cancelled")]
    Cancelled { stage_name: String },

    #[error("Stage '{stage_name}' was skipped: {reason}")]
    Skipped { stage_name: String, reason: String },

    #[error("Stage '{stage_name}' condition not met: {condition}")]
    ConditionNotMet { stage_name: String, condition: String },

    #[error("Stage '{stage_name}' timeout after {seconds} seconds")]
    Timeout { stage_name: String, seconds: u64 },

    #[error("Stage '{stage_name}' validation failed: {message}")]
    Validation { stage_name: String, message: String },

    #[error("Stage '{stage_name}' command failed with exit code {exit_code}: {output}")]
    CommandFailed {
        stage_name: String,
        exit_code: i32,
        output: String,
    },

    #[error("Stage '{stage_name}' registry function not found: {function}")]
    RegistryNotFound { stage_name: String, function: String },

    #[error("Stage '{stage_name}' template error: {message}")]
    Template { stage_name: String, message: String },
}

/// Error type for configuration operations
#[derive(Error, Debug, Clone, Serialize, Deserialize)]
pub enum ConfigError {
    #[error("Configuration file not found: {path}")]
    FileNotFound { path: String },

    #[error("Configuration parse error: {message}")]
    ParseError { message: String },

    #[error("Configuration validation error: {message}")]
    ValidationError { message: String },

    #[error("Environment variable not found: {var}")]
    EnvVarNotFound { var: String },
}

/// Error type for cron operations
#[derive(Error, Debug, Clone, Serialize, Deserialize)]
pub enum CronError {
    #[error("Invalid cron expression: {expression}")]
    InvalidExpression { expression: String },

    #[error("Cron schedule error: {message}")]
    ScheduleError { message: String },

    #[error("Timezone error: {timezone}")]
    TimezoneError { timezone: String },
}

/// Error type for audit operations
#[derive(Error, Debug, Clone, Serialize, Deserialize)]
pub enum AuditError {
    #[error("Audit write error: {message}")]
    WriteError { message: String },

    #[error("Audit read error: {message}")]
    ReadError { message: String },

    #[error("Audit storage error: {message}")]
    StorageError { message: String },
}

/// Error type for trace operations
#[derive(Error, Debug, Clone, Serialize, Deserialize)]
pub enum TraceError {
    #[error("Trace write error: {message}")]
    WriteError { message: String },

    #[error("Trace configuration error: {message}")]
    ConfigError { message: String },
}

/// Error type for registry operations
#[derive(Error, Debug, Clone, Serialize, Deserialize)]
pub enum RegistryError {
    #[error("Function not found: {name}")]
    FunctionNotFound { name: String },

    #[error("Function registration error: {message}")]
    RegistrationError { message: String },

    #[error("Function call error: {message}")]
    CallError { message: String },
}

/// Error type for cancellation scenarios
#[derive(Error, Debug, Clone, Serialize, Deserialize)]
pub enum CancelError {
    #[error("Workflow was cancelled")]
    Workflow,

    #[error("Job '{job_id}' was cancelled")]
    Job { job_id: String },

    #[error("Stage '{stage_name}' was cancelled")]
    Stage { stage_name: String },
}

/// Error type for skip scenarios
#[derive(Error, Debug, Clone, Serialize, Deserialize)]
pub enum SkipError {
    #[error("Workflow was skipped: {reason}")]
    Workflow { reason: String },

    #[error("Job '{job_id}' was skipped: {reason}")]
    Job { job_id: String, reason: String },

    #[error("Stage '{stage_name}' was skipped: {reason}")]
    Stage { stage_name: String, reason: String },
}

/// Result type aliases for better ergonomics
pub type WorkflowResult<T> = std::result::Result<T, WorkflowError>;
pub type JobResult<T> = std::result::Result<T, JobError>;
pub type StageResult<T> = std::result::Result<T, StageError>;

/// Trait for converting errors to status codes
pub trait ToStatus {
    fn to_status(&self) -> crate::result::Status;
}

impl ToStatus for WorkflowError {
    fn to_status(&self) -> crate::result::Status {
        match self {
            WorkflowError::Config { .. } | WorkflowError::Validation { .. } => {
                crate::result::Status::Failure
            }
            WorkflowError::Timeout { .. } => crate::result::Status::Timeout,
            _ => crate::result::Status::Error,
        }
    }
}

impl ToStatus for JobError {
    fn to_status(&self) -> crate::result::Status {
        match self {
            JobError::Cancelled { .. } => crate::result::Status::Cancelled,
            JobError::Skipped { .. } => crate::result::Status::Skipped,
            JobError::Timeout { .. } => crate::result::Status::Timeout,
            _ => crate::result::Status::Failure,
        }
    }
}

impl ToStatus for StageError {
    fn to_status(&self) -> crate::result::Status {
        match self {
            StageError::Cancelled { .. } => crate::result::Status::Cancelled,
            StageError::Skipped { .. } => crate::result::Status::Skipped,
            StageError::Timeout { .. } => crate::result::Status::Timeout,
            _ => crate::result::Status::Failure,
        }
    }
}

// Standard error conversions
impl From<std::io::Error> for WorkflowError {
    fn from(err: std::io::Error) -> Self {
        WorkflowError::Io {
            message: err.to_string(),
        }
    }
}

impl From<serde_yaml::Error> for WorkflowError {
    fn from(err: serde_yaml::Error) -> Self {
        WorkflowError::Config {
            message: format!("YAML error: {}", err),
        }
    }
}

impl From<serde_json::Error> for WorkflowError {
    fn from(err: serde_json::Error) -> Self {
        WorkflowError::Config {
            message: format!("JSON error: {}", err),
        }
    }
}

impl From<ConfigError> for WorkflowError {
    fn from(err: ConfigError) -> Self {
        WorkflowError::Config {
            message: err.to_string(),
        }
    }
}

impl From<CronError> for WorkflowError {
    fn from(err: CronError) -> Self {
        WorkflowError::Execution {
            message: err.to_string(),
        }
    }
}

impl From<AuditError> for WorkflowError {
    fn from(err: AuditError) -> Self {
        WorkflowError::Execution {
            message: err.to_string(),
        }
    }
}

impl From<TraceError> for WorkflowError {
    fn from(err: TraceError) -> Self {
        WorkflowError::Execution {
            message: err.to_string(),
        }
    }
}

impl From<RegistryError> for StageError {
    fn from(err: RegistryError) -> Self {
        StageError::RegistryNotFound {
            stage_name: "unknown".to_string(),
            function: err.to_string(),
        }
    }
}

/// Helper function to extract error details as JSON
pub fn error_details(err: &WorkflowError) -> serde_json::Value {
    serde_json::to_value(err).unwrap_or_else(|_| {
        serde_json::json!({
            "error": err.to_string(),
            "type": "WorkflowError"
        })
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_error_serialization() {
        let error = WorkflowError::Config {
            message: "test error".to_string(),
        };

        let serialized = serde_json::to_string(&error).unwrap();
        let deserialized: WorkflowError = serde_json::from_str(&serialized).unwrap();

        match deserialized {
            WorkflowError::Config { message } => {
                assert_eq!(message, "test error");
            }
            _ => panic!("Wrong error type"),
        }
    }

    #[test]
    fn test_error_conversion() {
        let io_error = std::io::Error::new(std::io::ErrorKind::NotFound, "file not found");
        let workflow_error = WorkflowError::from(io_error);

        match workflow_error {
            WorkflowError::Io { message } => {
                assert!(message.contains("file not found"));
            }
            _ => panic!("Wrong error type"),
        }
    }

    #[test]
    fn test_to_status() {
        let error = WorkflowError::Timeout { seconds: 30 };
        assert_eq!(error.to_status(), crate::result::Status::Timeout);

        let job_error = JobError::Cancelled {
            job_id: "test".to_string(),
        };
        assert_eq!(job_error.to_status(), crate::result::Status::Cancelled);
    }
}
