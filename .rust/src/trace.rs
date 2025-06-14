//! Tracing and logging module for workflow execution.
//!
//! This module provides structured logging and tracing capabilities
//! for debugging and monitoring workflow execution.

use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use uuid::Uuid;

use crate::error::{TraceError, WorkflowResult};

/// Log level enumeration
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum LogLevel {
    /// Debug level - detailed information for debugging
    Debug,
    /// Info level - general informational messages
    Info,
    /// Warning level - potentially harmful situations
    Warn,
    /// Error level - error events that don't halt execution
    Error,
    /// Fatal level - critical errors that halt execution
    Fatal,
}

impl std::fmt::Display for LogLevel {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            LogLevel::Debug => write!(f, "DEBUG"),
            LogLevel::Info => write!(f, "INFO"),
            LogLevel::Warn => write!(f, "WARN"),
            LogLevel::Error => write!(f, "ERROR"),
            LogLevel::Fatal => write!(f, "FATAL"),
        }
    }
}

impl std::str::FromStr for LogLevel {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_uppercase().as_str() {
            "DEBUG" => Ok(LogLevel::Debug),
            "INFO" => Ok(LogLevel::Info),
            "WARN" | "WARNING" => Ok(LogLevel::Warn),
            "ERROR" => Ok(LogLevel::Error),
            "FATAL" => Ok(LogLevel::Fatal),
            _ => Err(format!("Invalid log level: {}", s)),
        }
    }
}

/// Trace record containing execution information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TraceRecord {
    /// Unique trace ID
    pub id: Uuid,

    /// Timestamp when the trace was created
    pub timestamp: DateTime<Utc>,

    /// Log level
    pub level: LogLevel,

    /// Workflow name
    pub workflow_name: String,

    /// Job name (if applicable)
    pub job_name: Option<String>,

    /// Stage name (if applicable)
    pub stage_name: Option<String>,

    /// Log message
    pub message: String,

    /// Additional context data
    pub context: HashMap<String, serde_json::Value>,

    /// Execution thread/task ID
    pub thread_id: Option<String>,

    /// Duration (for timing traces)
    pub duration_ms: Option<u64>,
}

impl TraceRecord {
    /// Create new trace record
    pub fn new(level: LogLevel, workflow_name: String, message: String) -> Self {
        Self {
            id: Uuid::new_v4(),
            timestamp: Utc::now(),
            level,
            workflow_name,
            job_name: None,
            stage_name: None,
            message,
            context: HashMap::new(),
            thread_id: None,
            duration_ms: None,
        }
    }

    /// Set job context
    pub fn with_job(mut self, job_name: String) -> Self {
        self.job_name = Some(job_name);
        self
    }

    /// Set stage context
    pub fn with_stage(mut self, stage_name: String) -> Self {
        self.stage_name = Some(stage_name);
        self
    }

    /// Add context data
    pub fn with_context(mut self, key: String, value: serde_json::Value) -> Self {
        self.context.insert(key, value);
        self
    }

    /// Set duration
    pub fn with_duration(mut self, duration_ms: u64) -> Self {
        self.duration_ms = Some(duration_ms);
        self
    }

    /// Format trace record as string
    pub fn format(&self) -> String {
        let mut parts = vec![
            format!("[{}]", self.timestamp.format("%Y-%m-%d %H:%M:%S")),
            format!("[{}]", self.level),
            format!("[{}]", self.workflow_name),
        ];

        if let Some(job_name) = &self.job_name {
            parts.push(format!("[{}]", job_name));
        }

        if let Some(stage_name) = &self.stage_name {
            parts.push(format!("[{}]", stage_name));
        }

        parts.push(self.message.clone());

        if let Some(duration) = self.duration_ms {
            parts.push(format!("({}ms)", duration));
        }

        parts.join(" ")
    }

    /// Format trace record as JSON
    pub fn format_json(&self) -> Result<String, TraceError> {
        serde_json::to_string(self).map_err(|e| TraceError::ConfigError {
            message: format!("Failed to serialize trace record: {}", e),
        })
    }
}

/// Trait for trace output implementations
#[async_trait]
pub trait Trace: Send + Sync {
    /// Write trace record
    async fn write(&self, record: &TraceRecord) -> Result<(), TraceError>;

    /// Flush any buffered traces
    async fn flush(&self) -> Result<(), TraceError>;

    /// Close the trace output
    async fn close(&self) -> Result<(), TraceError>;
}

/// Trace model for managing tracing operations
#[derive(Debug)]
pub struct TraceModel {
    /// Trace output implementations
    outputs: Vec<Box<dyn Trace>>,

    /// Minimum log level to trace
    min_level: LogLevel,
}

impl TraceModel {
    /// Create new trace model
    pub fn new(min_level: LogLevel) -> Self {
        Self {
            outputs: Vec::new(),
            min_level,
        }
    }

    /// Add trace output
    pub fn add_output(&mut self, output: Box<dyn Trace>) {
        self.outputs.push(output);
    }

    /// Set minimum log level
    pub fn set_min_level(&mut self, level: LogLevel) {
        self.min_level = level;
    }

    /// Check if level should be traced
    pub fn should_trace(&self, level: LogLevel) -> bool {
        level as u8 >= self.min_level as u8
    }

    /// Write trace record to all outputs
    pub async fn trace(&self, record: &TraceRecord) -> WorkflowResult<()> {
        if !self.should_trace(record.level) {
            return Ok(());
        }

        for output in &self.outputs {
            output.write(record).await?;
        }

        Ok(())
    }

    /// Convenience method for debug traces
    pub async fn debug(&self, workflow_name: String, message: String) -> WorkflowResult<()> {
        let record = TraceRecord::new(LogLevel::Debug, workflow_name, message);
        self.trace(&record).await
    }

    /// Convenience method for info traces
    pub async fn info(&self, workflow_name: String, message: String) -> WorkflowResult<()> {
        let record = TraceRecord::new(LogLevel::Info, workflow_name, message);
        self.trace(&record).await
    }

    /// Convenience method for warning traces
    pub async fn warn(&self, workflow_name: String, message: String) -> WorkflowResult<()> {
        let record = TraceRecord::new(LogLevel::Warn, workflow_name, message);
        self.trace(&record).await
    }

    /// Convenience method for error traces
    pub async fn error(&self, workflow_name: String, message: String) -> WorkflowResult<()> {
        let record = TraceRecord::new(LogLevel::Error, workflow_name, message);
        self.trace(&record).await
    }

    /// Flush all outputs
    pub async fn flush(&self) -> WorkflowResult<()> {
        for output in &self.outputs {
            output.flush().await?;
        }
        Ok(())
    }

    /// Close all outputs
    pub async fn close(&self) -> WorkflowResult<()> {
        for output in &self.outputs {
            output.close().await?;
        }
        Ok(())
    }
}

/// Console trace output
#[derive(Debug)]
pub struct ConsoleTrace {
    /// Whether to use colored output
    pub colored: bool,
    /// Output format (text or json)
    pub format: String,
}

impl ConsoleTrace {
    /// Create new console trace output
    pub fn new() -> Self {
        Self {
            colored: true,
            format: "text".to_string(),
        }
    }

    /// Create console trace with specific format
    pub fn with_format(format: String) -> Self {
        Self {
            colored: true,
            format,
        }
    }
}

impl Default for ConsoleTrace {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl Trace for ConsoleTrace {
    async fn write(&self, record: &TraceRecord) -> Result<(), TraceError> {
        let output = match self.format.as_str() {
            "json" => record.format_json()?,
            _ => record.format(),
        };

        if self.colored {
            match record.level {
                LogLevel::Debug => println!("\x1b[36m{}\x1b[0m", output), // Cyan
                LogLevel::Info => println!("\x1b[32m{}\x1b[0m", output),  // Green
                LogLevel::Warn => println!("\x1b[33m{}\x1b[0m", output),  // Yellow
                LogLevel::Error => println!("\x1b[31m{}\x1b[0m", output), // Red
                LogLevel::Fatal => println!("\x1b[35m{}\x1b[0m", output), // Magenta
            }
        } else {
            println!("{}", output);
        }

        Ok(())
    }

    async fn flush(&self) -> Result<(), TraceError> {
        // Console output is usually auto-flushed
        Ok(())
    }

    async fn close(&self) -> Result<(), TraceError> {
        // Nothing to close for console output
        Ok(())
    }
}

/// File trace output
#[derive(Debug)]
pub struct FileTrace {
    /// Path to the log file
    pub file_path: PathBuf,
    /// Output format (text or json)
    pub format: String,
    /// Maximum file size before rotation
    pub max_size_mb: Option<u64>,
}

impl FileTrace {
    /// Create new file trace output
    pub fn new(file_path: PathBuf) -> Self {
        Self {
            file_path,
            format: "text".to_string(),
            max_size_mb: None,
        }
    }

    /// Create file trace with specific format
    pub fn with_format(file_path: PathBuf, format: String) -> Self {
        Self {
            file_path,
            format,
            max_size_mb: None,
        }
    }

    /// Set maximum file size for rotation
    pub fn with_rotation(mut self, max_size_mb: u64) -> Self {
        self.max_size_mb = Some(max_size_mb);
        self
    }

    /// Ensure parent directory exists
    async fn ensure_parent_dir(&self) -> Result<(), TraceError> {
        if let Some(parent) = self.file_path.parent() {
            if !parent.exists() {
                tokio::fs::create_dir_all(parent).await.map_err(|e| {
                    TraceError::WriteError {
                        message: format!("Failed to create log directory: {}", e),
                    }
                })?;
            }
        }
        Ok(())
    }

    /// Check if file rotation is needed
    async fn needs_rotation(&self) -> Result<bool, TraceError> {
        if let Some(max_size) = self.max_size_mb {
            if self.file_path.exists() {
                let metadata = tokio::fs::metadata(&self.file_path).await.map_err(|e| {
                    TraceError::WriteError {
                        message: format!("Failed to get file metadata: {}", e),
                    }
                })?;
                let size_mb = metadata.len() / (1024 * 1024);
                return Ok(size_mb >= max_size);
            }
        }
        Ok(false)
    }

    /// Rotate log file
    async fn rotate(&self) -> Result<(), TraceError> {
        let timestamp = Utc::now().format("%Y%m%d_%H%M%S");
        let rotated_path = self.file_path.with_extension(format!("log.{}", timestamp));

        tokio::fs::rename(&self.file_path, &rotated_path).await.map_err(|e| {
            TraceError::WriteError {
                message: format!("Failed to rotate log file: {}", e),
            }
        })?;

        Ok(())
    }
}

#[async_trait]
impl Trace for FileTrace {
    async fn write(&self, record: &TraceRecord) -> Result<(), TraceError> {
        self.ensure_parent_dir().await?;

        if self.needs_rotation().await? {
            self.rotate().await?;
        }

        let output = match self.format.as_str() {
            "json" => record.format_json()?,
            _ => record.format(),
        };

        let content = format!("{}\n", output);
        tokio::fs::write(&self.file_path, content).await.map_err(|e| {
            TraceError::WriteError {
                message: format!("Failed to write to log file: {}", e),
            }
        })?;

        Ok(())
    }

    async fn flush(&self) -> Result<(), TraceError> {
        // File writes are usually auto-flushed
        Ok(())
    }

    async fn close(&self) -> Result<(), TraceError> {
        // Nothing specific to close for file output
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn test_log_level_parsing() {
        assert_eq!(LogLevel::Debug, "DEBUG".parse().unwrap());
        assert_eq!(LogLevel::Info, "info".parse().unwrap());
        assert_eq!(LogLevel::Warn, "WARN".parse().unwrap());
        assert_eq!(LogLevel::Error, "error".parse().unwrap());
        assert_eq!(LogLevel::Fatal, "FATAL".parse().unwrap());

        assert!("invalid".parse::<LogLevel>().is_err());
    }

    #[test]
    fn test_trace_record_creation() {
        let record = TraceRecord::new(
            LogLevel::Info,
            "test-workflow".to_string(),
            "Test message".to_string(),
        );

        assert_eq!(record.level, LogLevel::Info);
        assert_eq!(record.workflow_name, "test-workflow");
        assert_eq!(record.message, "Test message");
        assert!(record.job_name.is_none());
        assert!(record.stage_name.is_none());
    }

    #[test]
    fn test_trace_record_with_context() {
        let record = TraceRecord::new(
            LogLevel::Info,
            "test-workflow".to_string(),
            "Test message".to_string(),
        )
        .with_job("test-job".to_string())
        .with_stage("test-stage".to_string())
        .with_context("key".to_string(), serde_json::Value::String("value".to_string()))
        .with_duration(100);

        assert_eq!(record.job_name, Some("test-job".to_string()));
        assert_eq!(record.stage_name, Some("test-stage".to_string()));
        assert_eq!(record.duration_ms, Some(100));
        assert_eq!(record.context.len(), 1);
    }

    #[test]
    fn test_trace_record_formatting() {
        let record = TraceRecord::new(
            LogLevel::Info,
            "test-workflow".to_string(),
            "Test message".to_string(),
        )
        .with_job("test-job".to_string());

        let formatted = record.format();
        assert!(formatted.contains("INFO"));
        assert!(formatted.contains("test-workflow"));
        assert!(formatted.contains("test-job"));
        assert!(formatted.contains("Test message"));
    }

    #[tokio::test]
    async fn test_console_trace() {
        let console_trace = ConsoleTrace::new();
        let record = TraceRecord::new(
            LogLevel::Info,
            "test-workflow".to_string(),
            "Test message".to_string(),
        );

        // This should not fail
        assert!(console_trace.write(&record).await.is_ok());
        assert!(console_trace.flush().await.is_ok());
        assert!(console_trace.close().await.is_ok());
    }

    #[tokio::test]
    async fn test_file_trace() {
        let temp_dir = TempDir::new().unwrap();
        let log_file = temp_dir.path().join("test.log");
        let file_trace = FileTrace::new(log_file.clone());

        let record = TraceRecord::new(
            LogLevel::Info,
            "test-workflow".to_string(),
            "Test message".to_string(),
        );

        assert!(file_trace.write(&record).await.is_ok());
        assert!(log_file.exists());
    }

    #[tokio::test]
    async fn test_trace_model() {
        let mut trace_model = TraceModel::new(LogLevel::Info);
        trace_model.add_output(Box::new(ConsoleTrace::new()));

        assert!(trace_model.should_trace(LogLevel::Info));
        assert!(trace_model.should_trace(LogLevel::Error));
        assert!(!trace_model.should_trace(LogLevel::Debug));

        assert!(trace_model.info("test-workflow".to_string(), "Test message".to_string()).await.is_ok());
    }
}
