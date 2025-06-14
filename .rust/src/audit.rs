//! Audit module for tracking workflow execution history.
//!
//! This module provides functionality to record, store, and retrieve
//! workflow execution audit logs for compliance and debugging purposes.

use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use uuid::Uuid;

use crate::error::{AuditError, WorkflowResult};
use crate::result::{Result as ExecutionResult, Status};

/// Audit record for workflow execution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditRecord {
    /// Unique audit record ID
    pub id: Uuid,

    /// Workflow name
    pub workflow_name: String,

    /// Workflow execution ID
    pub execution_id: Uuid,

    /// Start timestamp
    pub start_time: DateTime<Utc>,

    /// End timestamp
    pub end_time: Option<DateTime<Utc>>,

    /// Execution status
    pub status: Status,

    /// Input parameters
    pub inputs: HashMap<String, serde_json::Value>,

    /// Output results
    pub outputs: Option<HashMap<String, serde_json::Value>>,

    /// Error information
    pub error: Option<String>,

    /// Duration in milliseconds
    pub duration_ms: Option<u64>,

    /// Additional metadata
    pub metadata: HashMap<String, serde_json::Value>,
}

impl AuditRecord {
    /// Create new audit record
    pub fn new(workflow_name: String, execution_id: Uuid) -> Self {
        Self {
            id: Uuid::new_v4(),
            workflow_name,
            execution_id,
            start_time: Utc::now(),
            end_time: None,
            status: Status::Running,
            inputs: HashMap::new(),
            outputs: None,
            error: None,
            duration_ms: None,
            metadata: HashMap::new(),
        }
    }

    /// Mark audit record as completed
    pub fn complete(&mut self, result: &ExecutionResult) {
        self.end_time = Some(Utc::now());
        self.status = result.status.clone();
        self.duration_ms = Some(result.duration.as_millis() as u64);

        if let Some(error) = &result.error {
            self.error = Some(error.clone());
        }

        if let Some(output) = &result.output {
            let mut outputs = HashMap::new();
            outputs.insert("output".to_string(), serde_json::Value::String(output.clone()));
            self.outputs = Some(outputs);
        }
    }
}

/// Trait for audit storage implementations
#[async_trait]
pub trait Audit: Send + Sync {
    /// Write audit record
    async fn write(&self, record: &AuditRecord) -> Result<(), AuditError>;

    /// Read audit record by ID
    async fn read(&self, id: Uuid) -> Result<Option<AuditRecord>, AuditError>;

    /// List audit records for a workflow
    async fn list_by_workflow(&self, workflow_name: &str) -> Result<Vec<AuditRecord>, AuditError>;

    /// List audit records within time range
    async fn list_by_time_range(
        &self,
        start: DateTime<Utc>,
        end: DateTime<Utc>,
    ) -> Result<Vec<AuditRecord>, AuditError>;

    /// Delete old audit records
    async fn cleanup(&self, older_than: DateTime<Utc>) -> Result<usize, AuditError>;
}

/// Audit model for managing audit operations
#[derive(Debug)]
pub struct AuditModel {
    /// Storage implementation
    storage: Box<dyn Audit>,

    /// Retention period in days
    retention_days: u32,
}

impl AuditModel {
    /// Create new audit model
    pub fn new(storage: Box<dyn Audit>, retention_days: u32) -> Self {
        Self {
            storage,
            retention_days,
        }
    }

    /// Start audit for workflow execution
    pub async fn start_audit(&self, workflow_name: String, execution_id: Uuid) -> WorkflowResult<AuditRecord> {
        let record = AuditRecord::new(workflow_name, execution_id);
        self.storage.write(&record).await?;
        Ok(record)
    }

    /// Complete audit for workflow execution
    pub async fn complete_audit(&self, mut record: AuditRecord, result: &ExecutionResult) -> WorkflowResult<()> {
        record.complete(result);
        self.storage.write(&record).await?;
        Ok(())
    }

    /// Get audit history for workflow
    pub async fn get_workflow_history(&self, workflow_name: &str) -> WorkflowResult<Vec<AuditRecord>> {
        let records = self.storage.list_by_workflow(workflow_name).await?;
        Ok(records)
    }

    /// Cleanup old audit records
    pub async fn cleanup_old_records(&self) -> WorkflowResult<usize> {
        let cutoff_date = Utc::now() - chrono::Duration::days(self.retention_days as i64);
        let deleted_count = self.storage.cleanup(cutoff_date).await?;
        Ok(deleted_count)
    }
}

/// File-based audit storage implementation
#[derive(Debug)]
pub struct FileAudit {
    /// Directory path for audit files
    pub audit_dir: PathBuf,
}

impl FileAudit {
    /// Create new file audit storage
    pub fn new(audit_dir: PathBuf) -> Self {
        Self { audit_dir }
    }

    /// Ensure audit directory exists
    async fn ensure_dir(&self) -> Result<(), AuditError> {
        if !self.audit_dir.exists() {
            tokio::fs::create_dir_all(&self.audit_dir)
                .await
                .map_err(|e| AuditError::StorageError {
                    message: format!("Failed to create audit directory: {}", e),
                })?;
        }
        Ok(())
    }

    /// Get file path for audit record
    fn get_file_path(&self, id: Uuid) -> PathBuf {
        self.audit_dir.join(format!("{}.json", id))
    }
}

#[async_trait]
impl Audit for FileAudit {
    async fn write(&self, record: &AuditRecord) -> Result<(), AuditError> {
        self.ensure_dir().await?;

        let file_path = self.get_file_path(record.id);
        let content = serde_json::to_string_pretty(record).map_err(|e| AuditError::WriteError {
            message: format!("Failed to serialize audit record: {}", e),
        })?;

        tokio::fs::write(&file_path, content)
            .await
            .map_err(|e| AuditError::WriteError {
                message: format!("Failed to write audit file: {}", e),
            })?;

        Ok(())
    }

    async fn read(&self, id: Uuid) -> Result<Option<AuditRecord>, AuditError> {
        let file_path = self.get_file_path(id);

        if !file_path.exists() {
            return Ok(None);
        }

        let content = tokio::fs::read_to_string(&file_path)
            .await
            .map_err(|e| AuditError::ReadError {
                message: format!("Failed to read audit file: {}", e),
            })?;

        let record = serde_json::from_str(&content).map_err(|e| AuditError::ReadError {
            message: format!("Failed to deserialize audit record: {}", e),
        })?;

        Ok(Some(record))
    }

    async fn list_by_workflow(&self, workflow_name: &str) -> Result<Vec<AuditRecord>, AuditError> {
        if !self.audit_dir.exists() {
            return Ok(Vec::new());
        }

        let mut records = Vec::new();
        let mut entries = tokio::fs::read_dir(&self.audit_dir)
            .await
            .map_err(|e| AuditError::ReadError {
                message: format!("Failed to read audit directory: {}", e),
            })?;

        while let Some(entry) = entries.next_entry().await.map_err(|e| AuditError::ReadError {
            message: format!("Failed to read directory entry: {}", e),
        })? {
            if entry.path().extension() == Some(std::ffi::OsStr::new("json")) {
                let content = tokio::fs::read_to_string(entry.path())
                    .await
                    .map_err(|e| AuditError::ReadError {
                        message: format!("Failed to read audit file: {}", e),
                    })?;

                if let Ok(record) = serde_json::from_str::<AuditRecord>(&content) {
                    if record.workflow_name == workflow_name {
                        records.push(record);
                    }
                }
            }
        }

        // Sort by start time
        records.sort_by(|a, b| b.start_time.cmp(&a.start_time));
        Ok(records)
    }

    async fn list_by_time_range(
        &self,
        start: DateTime<Utc>,
        end: DateTime<Utc>,
    ) -> Result<Vec<AuditRecord>, AuditError> {
        if !self.audit_dir.exists() {
            return Ok(Vec::new());
        }

        let mut records = Vec::new();
        let mut entries = tokio::fs::read_dir(&self.audit_dir)
            .await
            .map_err(|e| AuditError::ReadError {
                message: format!("Failed to read audit directory: {}", e),
            })?;

        while let Some(entry) = entries.next_entry().await.map_err(|e| AuditError::ReadError {
            message: format!("Failed to read directory entry: {}", e),
        })? {
            if entry.path().extension() == Some(std::ffi::OsStr::new("json")) {
                let content = tokio::fs::read_to_string(entry.path())
                    .await
                    .map_err(|e| AuditError::ReadError {
                        message: format!("Failed to read audit file: {}", e),
                    })?;

                if let Ok(record) = serde_json::from_str::<AuditRecord>(&content) {
                    if record.start_time >= start && record.start_time <= end {
                        records.push(record);
                    }
                }
            }
        }

        records.sort_by(|a, b| b.start_time.cmp(&a.start_time));
        Ok(records)
    }

    async fn cleanup(&self, older_than: DateTime<Utc>) -> Result<usize, AuditError> {
        if !self.audit_dir.exists() {
            return Ok(0);
        }

        let mut deleted_count = 0;
        let mut entries = tokio::fs::read_dir(&self.audit_dir)
            .await
            .map_err(|e| AuditError::ReadError {
                message: format!("Failed to read audit directory: {}", e),
            })?;

        while let Some(entry) = entries.next_entry().await.map_err(|e| AuditError::ReadError {
            message: format!("Failed to read directory entry: {}", e),
        })? {
            if entry.path().extension() == Some(std::ffi::OsStr::new("json")) {
                let content = tokio::fs::read_to_string(entry.path())
                    .await
                    .map_err(|e| AuditError::ReadError {
                        message: format!("Failed to read audit file: {}", e),
                    })?;

                if let Ok(record) = serde_json::from_str::<AuditRecord>(&content) {
                    if record.start_time < older_than {
                        tokio::fs::remove_file(entry.path())
                            .await
                            .map_err(|e| AuditError::StorageError {
                                message: format!("Failed to delete audit file: {}", e),
                            })?;
                        deleted_count += 1;
                    }
                }
            }
        }

        Ok(deleted_count)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[tokio::test]
    async fn test_audit_record_creation() {
        let workflow_name = "test-workflow".to_string();
        let execution_id = Uuid::new_v4();
        let record = AuditRecord::new(workflow_name.clone(), execution_id);

        assert_eq!(record.workflow_name, workflow_name);
        assert_eq!(record.execution_id, execution_id);
        assert_eq!(record.status, Status::Running);
        assert!(record.end_time.is_none());
    }

    #[tokio::test]
    async fn test_file_audit_write_read() {
        let temp_dir = TempDir::new().unwrap();
        let audit = FileAudit::new(temp_dir.path().to_path_buf());

        let record = AuditRecord::new("test-workflow".to_string(), Uuid::new_v4());
        let record_id = record.id;

        // Write record
        audit.write(&record).await.unwrap();

        // Read record
        let read_record = audit.read(record_id).await.unwrap();
        assert!(read_record.is_some());
        assert_eq!(read_record.unwrap().id, record_id);
    }

    #[tokio::test]
    async fn test_audit_cleanup() {
        let temp_dir = TempDir::new().unwrap();
        let audit = FileAudit::new(temp_dir.path().to_path_buf());

        // Create old record
        let mut old_record = AuditRecord::new("test-workflow".to_string(), Uuid::new_v4());
        old_record.start_time = Utc::now() - chrono::Duration::days(35);
        audit.write(&old_record).await.unwrap();

        // Create recent record
        let recent_record = AuditRecord::new("test-workflow".to_string(), Uuid::new_v4());
        audit.write(&recent_record).await.unwrap();

        // Cleanup records older than 30 days
        let cutoff = Utc::now() - chrono::Duration::days(30);
        let deleted_count = audit.cleanup(cutoff).await.unwrap();

        assert_eq!(deleted_count, 1);
    }
}
