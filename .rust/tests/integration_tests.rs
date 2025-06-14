//! Integration tests for the ddeutil-workflow package.
//!
//! These tests verify the complete workflow system functionality,
//! including workflow execution, configuration loading, and CLI operations.

use ddeutil_workflow::{Workflow, Status, Result as WorkflowResult};
use std::collections::HashMap;
use tempfile::TempDir;
use tokio;

/// Test basic workflow creation and execution
#[tokio::test]
async fn test_workflow_basic_execution() {
    let mut workflow = Workflow::new("test-workflow".to_string());

    // Add a simple job with empty stage
    let mut job = ddeutil_workflow::job::Job::new("test-job".to_string());
    job.stages.push(ddeutil_workflow::stage::Stage::Empty(
        ddeutil_workflow::stage::EmptyStage {
            name: "test-stage".to_string(),
            echo: Some("Hello Integration Test".to_string()),
            sleep: 0.1,
            ..Default::default()
        }
    ));

    workflow.jobs.insert("test-job".to_string(), job);

    // Execute workflow
    let params = HashMap::new();
    let result = workflow.execute(params, None, None, Some(30), None).await.unwrap();

    assert_eq!(result.status, Status::Success);
    assert!(!result.run_id.is_empty());
    assert!(result.get_outputs().is_some());
}

/// Test workflow with multiple jobs and dependencies
#[tokio::test]
async fn test_workflow_with_dependencies() {
    let mut workflow = Workflow::new("dependency-test".to_string());

    // Job A (no dependencies)
    let mut job_a = ddeutil_workflow::job::Job::new("job-a".to_string());
    job_a.stages.push(ddeutil_workflow::stage::Stage::Empty(
        ddeutil_workflow::stage::EmptyStage {
            name: "stage-a".to_string(),
            echo: Some("Job A executed".to_string()),
            sleep: 0.1,
            ..Default::default()
        }
    ));
    workflow.jobs.insert("job-a".to_string(), job_a);

    // Job B (depends on A)
    let mut job_b = ddeutil_workflow::job::Job::new("job-b".to_string());
    job_b.needs = vec!["job-a".to_string()];
    job_b.stages.push(ddeutil_workflow::stage::Stage::Empty(
        ddeutil_workflow::stage::EmptyStage {
            name: "stage-b".to_string(),
            echo: Some("Job B executed after A".to_string()),
            sleep: 0.1,
            ..Default::default()
        }
    ));
    workflow.jobs.insert("job-b".to_string(), job_b);

    // Execute workflow
    let params = HashMap::new();
    let result = workflow.execute(params, None, None, Some(30), None).await.unwrap();

    assert_eq!(result.status, Status::Success);

    // Check that both jobs executed
    let outputs = result.get_outputs().unwrap();
    assert!(outputs.get("jobs.job-a").is_some());
    assert!(outputs.get("jobs.job-b").is_some());
}

/// Test workflow with matrix strategy
#[tokio::test]
async fn test_workflow_matrix_strategy() {
    let mut workflow = Workflow::new("matrix-test".to_string());

    // Job with matrix strategy
    let mut job = ddeutil_workflow::job::Job::new("matrix-job".to_string());

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

    job.stages.push(ddeutil_workflow::stage::Stage::Empty(
        ddeutil_workflow::stage::EmptyStage {
            name: "matrix-stage".to_string(),
            echo: Some("Matrix execution".to_string()),
            sleep: 0.1,
            ..Default::default()
        }
    ));

    workflow.jobs.insert("matrix-job".to_string(), job);

    // Execute workflow
    let params = HashMap::new();
    let result = workflow.execute(params, None, None, Some(60), None).await.unwrap();

    assert_eq!(result.status, Status::Success);

    // Check matrix outputs (should have 4 combinations: 2 OS × 2 versions)
    let outputs = result.get_outputs().unwrap();
    let job_outputs = outputs.get("jobs.matrix-job").unwrap();

    // Matrix results should be present
    assert!(job_outputs.get("matrix.0").is_some());
    assert!(job_outputs.get("matrix.1").is_some());
    assert!(job_outputs.get("matrix.2").is_some());
    assert!(job_outputs.get("matrix.3").is_some());
}

/// Test workflow parameter handling
#[tokio::test]
async fn test_workflow_parameters() {
    let mut workflow = Workflow::new("param-test".to_string());

    // Add parameters to workflow
    workflow.params.insert("source".to_string(), ddeutil_workflow::params::Param {
        param_type: "str".to_string(),
        description: Some("Source file path".to_string()),
        default: Some(serde_json::json!("default.txt")),
        required: false,
        choices: None,
    });

    workflow.params.insert("count".to_string(), ddeutil_workflow::params::Param {
        param_type: "int".to_string(),
        description: Some("Number of items".to_string()),
        default: Some(serde_json::json!(10)),
        required: false,
        choices: None,
    });

    // Add job that uses parameters
    let mut job = ddeutil_workflow::job::Job::new("param-job".to_string());
    job.stages.push(ddeutil_workflow::stage::Stage::Empty(
        ddeutil_workflow::stage::EmptyStage {
            name: "param-stage".to_string(),
            echo: Some("Processing parameters".to_string()),
            sleep: 0.1,
            ..Default::default()
        }
    ));

    workflow.jobs.insert("param-job".to_string(), job);

    // Execute with custom parameters
    let mut params = HashMap::new();
    params.insert("source".to_string(), serde_json::json!("input.csv"));
    params.insert("count".to_string(), serde_json::json!(42));

    let result = workflow.execute(params, None, None, Some(30), None).await.unwrap();

    assert_eq!(result.status, Status::Success);
}

/// Test workflow timeout handling
#[tokio::test]
async fn test_workflow_timeout() {
    let mut workflow = Workflow::new("timeout-test".to_string());

    // Add job with long sleep
    let mut job = ddeutil_workflow::job::Job::new("slow-job".to_string());
    job.stages.push(ddeutil_workflow::stage::Stage::Empty(
        ddeutil_workflow::stage::EmptyStage {
            name: "slow-stage".to_string(),
            echo: Some("This will timeout".to_string()),
            sleep: 5.0, // 5 seconds
            ..Default::default()
        }
    ));

    workflow.jobs.insert("slow-job".to_string(), job);

    // Execute with short timeout
    let params = HashMap::new();
    let result = workflow.execute(params, None, None, Some(1), None).await.unwrap(); // 1 second timeout

    assert_eq!(result.status, Status::Failed);
    assert!(result.has_errors());

    let errors = result.get_errors().unwrap();
    let error_str = serde_json::to_string(errors).unwrap();
    assert!(error_str.contains("timeout") || error_str.contains("Timeout"));
}

/// Test configuration loading from files
#[tokio::test]
async fn test_config_loading() {
    let temp_dir = TempDir::new().unwrap();
    let config_path = temp_dir.path();

    // Create a test workflow configuration file
    let workflow_content = r#"
type: Workflow
name: config-test-workflow
desc: "Test workflow loaded from config"

params:
  input_file:
    type: str
    description: "Input file path"
    default: "test.txt"

jobs:
  process-file:
    runs-on:
      type: local
    stages:
      - name: "Process File"
        echo: "Processing file: ${{ params.input_file }}"
        sleep: 0.1
"#;

    let workflow_file = config_path.join("config-test-workflow.yaml");
    tokio::fs::write(&workflow_file, workflow_content).await.unwrap();

    // Set environment variable for config path
    std::env::set_var("WORKFLOW_CORE_CONFIG_PATH", config_path.to_str().unwrap());

    // Load workflow from config
    let workflow = Workflow::from_config("config-test-workflow").await.unwrap();

    assert_eq!(workflow.name, "config-test-workflow");
    assert!(workflow.desc.is_some());
    assert_eq!(workflow.jobs.len(), 1);
    assert!(workflow.jobs.contains_key("process-file"));
    assert_eq!(workflow.params.len(), 1);
    assert!(workflow.params.contains_key("input_file"));

    // Clean up
    std::env::remove_var("WORKFLOW_CORE_CONFIG_PATH");
}

/// Test error handling in workflow execution
#[tokio::test]
async fn test_workflow_error_handling() {
    let mut workflow = Workflow::new("error-test".to_string());

    // Add job that will fail
    let mut job = ddeutil_workflow::job::Job::new("failing-job".to_string());
    job.stages.push(ddeutil_workflow::stage::Stage::Bash(
        ddeutil_workflow::stage::BashStage {
            name: "failing-stage".to_string(),
            bash: "exit 1".to_string(), // This will fail
            env: HashMap::new(),
            working_dir: None,
            timeout: None,
            continue_on_error: false,
            r#if: None,
        }
    ));

    workflow.jobs.insert("failing-job".to_string(), job);

    // Execute workflow
    let params = HashMap::new();
    let result = workflow.execute(params, None, None, Some(30), None).await.unwrap();

    assert_eq!(result.status, Status::Failed);
    assert!(result.has_errors());
}

/// Test workflow validation
#[tokio::test]
async fn test_workflow_validation() {
    let mut workflow = Workflow::new("validation-test".to_string());

    // Add job with invalid dependency
    let mut job = ddeutil_workflow::job::Job::new("dependent-job".to_string());
    job.needs = vec!["non-existent-job".to_string()];
    job.stages.push(ddeutil_workflow::stage::Stage::Empty(
        ddeutil_workflow::stage::EmptyStage {
            name: "test-stage".to_string(),
            ..Default::default()
        }
    ));

    workflow.jobs.insert("dependent-job".to_string(), job);

    // Validation should fail
    let validation_result = workflow.validate();
    assert!(validation_result.is_err());

    let error = validation_result.unwrap_err();
    let error_message = error.to_string();
    assert!(error_message.contains("non-existent-job"));
}

/// Test concurrent workflow execution
#[tokio::test]
async fn test_concurrent_workflows() {
    let workflow1 = create_test_workflow("concurrent-1", 0.2);
    let workflow2 = create_test_workflow("concurrent-2", 0.3);
    let workflow3 = create_test_workflow("concurrent-3", 0.1);

    let params = HashMap::new();

    // Execute workflows concurrently
    let (result1, result2, result3) = tokio::join!(
        workflow1.execute(params.clone(), None, None, Some(30), None),
        workflow2.execute(params.clone(), None, None, Some(30), None),
        workflow3.execute(params.clone(), None, None, Some(30), None),
    );

    assert_eq!(result1.unwrap().status, Status::Success);
    assert_eq!(result2.unwrap().status, Status::Success);
    assert_eq!(result3.unwrap().status, Status::Success);
}

/// Helper function to create a test workflow
fn create_test_workflow(name: &str, sleep_duration: f64) -> Workflow {
    let mut workflow = Workflow::new(name.to_string());

    let mut job = ddeutil_workflow::job::Job::new(format!("{}-job", name));
    job.stages.push(ddeutil_workflow::stage::Stage::Empty(
        ddeutil_workflow::stage::EmptyStage {
            name: format!("{}-stage", name),
            echo: Some(format!("Executing {}", name)),
            sleep: sleep_duration,
            ..Default::default()
        }
    ));

    workflow.jobs.insert(format!("{}-job", name), job);
    workflow
}

/// Test workflow result serialization
#[tokio::test]
async fn test_result_serialization() {
    let mut workflow = Workflow::new("serialization-test".to_string());

    let mut job = ddeutil_workflow::job::Job::new("test-job".to_string());
    job.stages.push(ddeutil_workflow::stage::Stage::Empty(
        ddeutil_workflow::stage::EmptyStage {
            name: "test-stage".to_string(),
            echo: Some("Test output".to_string()),
            sleep: 0.1,
            ..Default::default()
        }
    ));

    workflow.jobs.insert("test-job".to_string(), job);

    let params = HashMap::new();
    let result = workflow.execute(params, None, None, Some(30), None).await.unwrap();

    // Test JSON serialization
    let json_result = serde_json::to_string(&result).unwrap();
    assert!(!json_result.is_empty());

    // Test deserialization
    let deserialized: ddeutil_workflow::Result = serde_json::from_str(&json_result).unwrap();
    assert_eq!(deserialized.status, result.status);
    assert_eq!(deserialized.run_id, result.run_id);
}
