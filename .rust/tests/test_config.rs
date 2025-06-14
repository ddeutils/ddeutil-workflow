//! Test configuration and utilities for the ddeutil-workflow test suite.
//!
//! This module provides common test utilities, fixtures, and configuration
//! that can be shared across different test files.

use std::collections::HashMap;
use tempfile::TempDir;
use ddeutil_workflow::{Workflow, job::Job, stage::Stage};

/// Test configuration structure
pub struct TestConfig {
    pub temp_dir: TempDir,
    pub workflow_dir: std::path::PathBuf,
}

impl TestConfig {
    /// Create a new test configuration with temporary directories
    pub fn new() -> Self {
        let temp_dir = TempDir::new().expect("Failed to create temp directory");
        let workflow_dir = temp_dir.path().join("workflows");
        std::fs::create_dir_all(&workflow_dir).expect("Failed to create workflow directory");

        Self {
            temp_dir,
            workflow_dir,
        }
    }

    /// Get the path to the workflow directory
    pub fn workflow_path(&self) -> &std::path::Path {
        &self.workflow_dir
    }

    /// Create a test workflow file
    pub async fn create_workflow_file(&self, name: &str, content: &str) -> std::path::PathBuf {
        let file_path = self.workflow_dir.join(format!("{}.yaml", name));
        tokio::fs::write(&file_path, content).await.expect("Failed to write workflow file");
        file_path
    }
}

/// Create a simple test workflow for testing purposes
pub fn create_simple_workflow(name: &str) -> Workflow {
    let mut workflow = Workflow::new(name.to_string());

    let mut job = Job::new("test-job".to_string());
    job.stages.push(Stage::Empty(
        ddeutil_workflow::stage::EmptyStage {
            name: "test-stage".to_string(),
            echo: Some("Hello from test".to_string()),
            sleep: 0.01,
            ..Default::default()
        }
    ));

    workflow.jobs.insert("test-job".to_string(), job);
    workflow
}

/// Create a workflow with multiple jobs for dependency testing
pub fn create_dependency_workflow(name: &str) -> Workflow {
    let mut workflow = Workflow::new(name.to_string());

    // Job A (no dependencies)
    let mut job_a = Job::new("job-a".to_string());
    job_a.stages.push(Stage::Empty(
        ddeutil_workflow::stage::EmptyStage {
            name: "stage-a".to_string(),
            echo: Some("Job A".to_string()),
            sleep: 0.01,
            ..Default::default()
        }
    ));
    workflow.jobs.insert("job-a".to_string(), job_a);

    // Job B (depends on A)
    let mut job_b = Job::new("job-b".to_string());
    job_b.needs = vec!["job-a".to_string()];
    job_b.stages.push(Stage::Empty(
        ddeutil_workflow::stage::EmptyStage {
            name: "stage-b".to_string(),
            echo: Some("Job B".to_string()),
            sleep: 0.01,
            ..Default::default()
        }
    ));
    workflow.jobs.insert("job-b".to_string(), job_b);

    // Job C (depends on A and B)
    let mut job_c = Job::new("job-c".to_string());
    job_c.needs = vec!["job-a".to_string(), "job-b".to_string()];
    job_c.stages.push(Stage::Empty(
        ddeutil_workflow::stage::EmptyStage {
            name: "stage-c".to_string(),
            echo: Some("Job C".to_string()),
            sleep: 0.01,
            ..Default::default()
        }
    ));
    workflow.jobs.insert("job-c".to_string(), job_c);

    workflow
}

/// Create a workflow with matrix strategy for testing
pub fn create_matrix_workflow(name: &str) -> Workflow {
    let mut workflow = Workflow::new(name.to_string());

    let mut job = Job::new("matrix-job".to_string());

    // Configure matrix strategy
    job.strategy.matrix.insert("os".to_string(), vec![
        serde_json::json!("ubuntu"),
        serde_json::json!("windows"),
    ]);
    job.strategy.matrix.insert("version".to_string(), vec![
        serde_json::json!("3.9"),
        serde_json::json!("3.10"),
    ]);
    job.strategy.max_parallel = Some(2);

    job.stages.push(Stage::Empty(
        ddeutil_workflow::stage::EmptyStage {
            name: "matrix-stage".to_string(),
            echo: Some("Matrix test".to_string()),
            sleep: 0.01,
            ..Default::default()
        }
    ));

    workflow.jobs.insert("matrix-job".to_string(), job);
    workflow
}

/// Sample workflow YAML content for testing configuration loading
pub const SAMPLE_WORKFLOW_YAML: &str = r#"
type: Workflow
name: sample-workflow
desc: "A sample workflow for testing"

params:
  input_file:
    type: str
    description: "Input file path"
    default: "input.txt"
    required: false

  debug:
    type: bool
    description: "Enable debug mode"
    default: false
    required: false

jobs:
  prepare:
    runs-on:
      type: local
    stages:
      - name: "Prepare Environment"
        echo: "Preparing environment with file: ${{ params.input_file }}"
        sleep: 0.1

  process:
    needs: [prepare]
    runs-on:
      type: local
    stages:
      - name: "Process Data"
        echo: "Processing data (debug: ${{ params.debug }})"
        sleep: 0.1

  cleanup:
    needs: [process]
    runs-on:
      type: local
    stages:
      - name: "Cleanup"
        echo: "Cleaning up resources"
        sleep: 0.1
"#;

/// Sample workflow with matrix strategy
pub const SAMPLE_MATRIX_WORKFLOW_YAML: &str = r#"
type: Workflow
name: matrix-workflow
desc: "A workflow with matrix strategy"

jobs:
  test:
    strategy:
      matrix:
        os: [ubuntu, windows, macos]
        python: ["3.9", "3.10", "3.11"]
      max-parallel: 3
      fail-fast: false
    runs-on:
      type: local
    stages:
      - name: "Test on ${{ matrix.os }} with Python ${{ matrix.python }}"
        echo: "Testing on ${{ matrix.os }} with Python ${{ matrix.python }}"
        sleep: 0.1
"#;

/// Test assertion helpers
pub mod assertions {
    use ddeutil_workflow::{Status, Result as WorkflowResult};

    /// Assert that a workflow result is successful
    pub fn assert_success(result: &WorkflowResult) {
        assert_eq!(result.status, Status::Success, "Workflow should succeed");
        assert!(!result.has_errors(), "Workflow should not have errors");
    }

    /// Assert that a workflow result failed
    pub fn assert_failed(result: &WorkflowResult) {
        assert_eq!(result.status, Status::Failed, "Workflow should fail");
        assert!(result.has_errors(), "Workflow should have errors");
    }

    /// Assert that a workflow result was cancelled
    pub fn assert_cancelled(result: &WorkflowResult) {
        assert_eq!(result.status, Status::Cancelled, "Workflow should be cancelled");
    }

    /// Assert that workflow has specific output
    pub fn assert_has_output(result: &WorkflowResult, key: &str) {
        let outputs = result.get_outputs().expect("Workflow should have outputs");
        assert!(outputs.contains_key(key), "Output should contain key: {}", key);
    }

    /// Assert that workflow completed within expected time
    pub fn assert_duration_within(result: &WorkflowResult, max_duration_ms: u64) {
        if let (Some(start), Some(end)) = (&result.started_at, &result.finished_at) {
            let duration = end.signed_duration_since(*start);
            let duration_ms = duration.num_milliseconds() as u64;
            assert!(
                duration_ms <= max_duration_ms,
                "Workflow took {}ms, expected <= {}ms",
                duration_ms,
                max_duration_ms
            );
        }
    }
}

/// Mock data generators for testing
pub mod mocks {
    use std::collections::HashMap;
    use serde_json::Value;

    /// Generate mock parameters for testing
    pub fn mock_params() -> HashMap<String, Value> {
        let mut params = HashMap::new();
        params.insert("test_param".to_string(), serde_json::json!("test_value"));
        params.insert("number_param".to_string(), serde_json::json!(42));
        params.insert("bool_param".to_string(), serde_json::json!(true));
        params
    }

    /// Generate mock environment variables
    pub fn mock_env() -> HashMap<String, String> {
        let mut env = HashMap::new();
        env.insert("TEST_ENV".to_string(), "test_value".to_string());
        env.insert("DEBUG".to_string(), "true".to_string());
        env
    }

    /// Generate mock matrix configuration
    pub fn mock_matrix() -> HashMap<String, Vec<Value>> {
        let mut matrix = HashMap::new();
        matrix.insert("os".to_string(), vec![
            serde_json::json!("ubuntu"),
            serde_json::json!("windows"),
        ]);
        matrix.insert("version".to_string(), vec![
            serde_json::json!("1.0"),
            serde_json::json!("2.0"),
        ]);
        matrix
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_config_creation() {
        let config = TestConfig::new();
        assert!(config.workflow_path().exists());
    }

    #[test]
    fn test_simple_workflow_creation() {
        let workflow = create_simple_workflow("test");
        assert_eq!(workflow.name, "test");
        assert_eq!(workflow.jobs.len(), 1);
        assert!(workflow.jobs.contains_key("test-job"));
    }

    #[test]
    fn test_dependency_workflow_creation() {
        let workflow = create_dependency_workflow("dep-test");
        assert_eq!(workflow.name, "dep-test");
        assert_eq!(workflow.jobs.len(), 3);

        // Check dependencies
        let job_b = workflow.jobs.get("job-b").unwrap();
        assert_eq!(job_b.needs, vec!["job-a"]);

        let job_c = workflow.jobs.get("job-c").unwrap();
        assert_eq!(job_c.needs, vec!["job-a", "job-b"]);
    }

    #[test]
    fn test_matrix_workflow_creation() {
        let workflow = create_matrix_workflow("matrix-test");
        assert_eq!(workflow.name, "matrix-test");
        assert_eq!(workflow.jobs.len(), 1);

        let job = workflow.jobs.get("matrix-job").unwrap();
        assert_eq!(job.strategy.matrix.len(), 2);
        assert!(job.strategy.matrix.contains_key("os"));
        assert!(job.strategy.matrix.contains_key("version"));
    }
}
