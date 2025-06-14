//! Unit tests for individual modules in the ddeutil-workflow package.
//!
//! These tests focus on testing individual components in isolation,
//! including utilities, error handling, configuration, and data structures.

use ddeutil_workflow::{
    error::{WorkflowError, JobError, StageError},
    result::{Status, Result as WorkflowResult},
    utils::{generate_id, render_template, cross_product},
    config::Config,
    types::{RegexWrapper, VolumeMount, ResourceLimits},
};
use std::collections::HashMap;
use serde_json::json;

/// Test ID generation utility
#[test]
fn test_generate_id() {
    let id1 = generate_id();
    let id2 = generate_id();

    // IDs should be different
    assert_ne!(id1, id2);

    // IDs should have expected format (8 characters)
    assert_eq!(id1.len(), 8);
    assert_eq!(id2.len(), 8);

    // IDs should be alphanumeric
    assert!(id1.chars().all(|c| c.is_ascii_alphanumeric()));
    assert!(id2.chars().all(|c| c.is_ascii_alphanumeric()));
}

/// Test template rendering utility
#[test]
fn test_render_template() {
    let mut context = HashMap::new();
    context.insert("name".to_string(), json!("John"));
    context.insert("age".to_string(), json!(30));
    context.insert("city".to_string(), json!("New York"));

    // Simple variable substitution
    let template = "Hello, {{name}}!";
    let result = render_template(template, &context).unwrap();
    assert_eq!(result, "Hello, John!");

    // Multiple variables
    let template = "{{name}} is {{age}} years old and lives in {{city}}.";
    let result = render_template(template, &context).unwrap();
    assert_eq!(result, "John is 30 years old and lives in New York.");

    // Missing variable should return error
    let template = "Hello, {{missing_var}}!";
    let result = render_template(template, &context);
    assert!(result.is_err());

    // Empty template
    let template = "";
    let result = render_template(template, &context).unwrap();
    assert_eq!(result, "");

    // Template without variables
    let template = "No variables here";
    let result = render_template(template, &context).unwrap();
    assert_eq!(result, "No variables here");
}

/// Test cross product utility for matrix strategies
#[test]
fn test_cross_product() {
    let mut matrix = HashMap::new();
    matrix.insert("os".to_string(), vec![json!("ubuntu"), json!("windows")]);
    matrix.insert("version".to_string(), vec![json!("3.9"), json!("3.10"), json!("3.11")]);

    let combinations = cross_product(&matrix);

    // Should have 2 * 3 = 6 combinations
    assert_eq!(combinations.len(), 6);

    // Check that all combinations are present
    let expected_combinations = vec![
        vec![("os", "ubuntu"), ("version", "3.9")],
        vec![("os", "ubuntu"), ("version", "3.10")],
        vec![("os", "ubuntu"), ("version", "3.11")],
        vec![("os", "windows"), ("version", "3.9")],
        vec![("os", "windows"), ("version", "3.10")],
        vec![("os", "windows"), ("version", "3.11")],
    ];

    for expected in expected_combinations {
        let found = combinations.iter().any(|combo| {
            expected.iter().all(|(key, value)| {
                combo.get(*key).map(|v| v.as_str().unwrap()) == Some(*value)
            })
        });
        assert!(found, "Expected combination not found: {:?}", expected);
    }
}

/// Test cross product with single dimension
#[test]
fn test_cross_product_single_dimension() {
    let mut matrix = HashMap::new();
    matrix.insert("version".to_string(), vec![json!("3.9"), json!("3.10")]);

    let combinations = cross_product(&matrix);

    assert_eq!(combinations.len(), 2);
    assert_eq!(combinations[0].get("version").unwrap().as_str().unwrap(), "3.9");
    assert_eq!(combinations[1].get("version").unwrap().as_str().unwrap(), "3.10");
}

/// Test cross product with empty matrix
#[test]
fn test_cross_product_empty() {
    let matrix = HashMap::new();
    let combinations = cross_product(&matrix);

    // Empty matrix should return single empty combination
    assert_eq!(combinations.len(), 1);
    assert!(combinations[0].is_empty());
}

/// Test Status enum functionality
#[test]
fn test_status_enum() {
    // Test status creation
    let success = Status::Success;
    let failed = Status::Failed;
    let cancelled = Status::Cancelled;
    let skipped = Status::Skipped;

    // Test emoji representation
    assert_eq!(success.emoji(), "✅");
    assert_eq!(failed.emoji(), "❌");
    assert_eq!(cancelled.emoji(), "🚫");
    assert_eq!(skipped.emoji(), "⏭️");

    // Test is_terminal
    assert!(success.is_terminal());
    assert!(failed.is_terminal());
    assert!(cancelled.is_terminal());
    assert!(!skipped.is_terminal());

    // Test serialization
    let json_success = serde_json::to_string(&success).unwrap();
    assert_eq!(json_success, "\"Success\"");

    let json_failed = serde_json::to_string(&failed).unwrap();
    assert_eq!(json_failed, "\"Failed\"");
}

/// Test WorkflowResult structure
#[test]
fn test_workflow_result() {
    let mut result = WorkflowResult::new("test-run-123".to_string());

    // Initial state
    assert_eq!(result.status, Status::Success);
    assert_eq!(result.run_id, "test-run-123");
    assert!(!result.has_errors());
    assert!(result.get_outputs().is_none());

    // Add some outputs
    let mut outputs = HashMap::new();
    outputs.insert("key1".to_string(), json!("value1"));
    outputs.insert("key2".to_string(), json!(42));
    result.outputs = Some(outputs);

    assert!(result.get_outputs().is_some());
    let outputs = result.get_outputs().unwrap();
    assert_eq!(outputs.get("key1").unwrap().as_str().unwrap(), "value1");
    assert_eq!(outputs.get("key2").unwrap().as_i64().unwrap(), 42);

    // Add errors
    let mut errors = HashMap::new();
    errors.insert("job1".to_string(), json!("Job failed"));
    result.errors = Some(errors);
    result.status = Status::Failed;

    assert!(result.has_errors());
    assert_eq!(result.status, Status::Failed);

    let errors = result.get_errors().unwrap();
    assert_eq!(errors.get("job1").unwrap().as_str().unwrap(), "Job failed");
}

/// Test error types
#[test]
fn test_error_types() {
    // WorkflowError
    let workflow_error = WorkflowError::ValidationError("Invalid workflow".to_string());
    assert_eq!(workflow_error.to_string(), "Workflow validation failed: Invalid workflow");

    let config_error = WorkflowError::ConfigError("Config not found".to_string());
    assert_eq!(config_error.to_string(), "Configuration error: Config not found");

    let timeout_error = WorkflowError::TimeoutError("Workflow timed out".to_string());
    assert_eq!(timeout_error.to_string(), "Workflow timeout: Workflow timed out");

    // JobError
    let job_error = JobError::ExecutionError("Job execution failed".to_string());
    assert_eq!(job_error.to_string(), "Job execution failed: Job execution failed");

    let dependency_error = JobError::DependencyError("Missing dependency".to_string());
    assert_eq!(dependency_error.to_string(), "Job dependency error: Missing dependency");

    // StageError
    let stage_error = StageError::CommandError("Command failed".to_string());
    assert_eq!(stage_error.to_string(), "Stage command error: Command failed");

    let timeout_error = StageError::TimeoutError("Stage timed out".to_string());
    assert_eq!(stage_error.to_string(), "Stage timeout: Stage timed out");
}

/// Test error conversion
#[test]
fn test_error_conversion() {
    let job_error = JobError::ExecutionError("Test error".to_string());
    let workflow_error: WorkflowError = job_error.into();

    match workflow_error {
        WorkflowError::JobError(inner) => {
            match inner {
                JobError::ExecutionError(msg) => assert_eq!(msg, "Test error"),
                _ => panic!("Wrong job error type"),
            }
        }
        _ => panic!("Wrong workflow error type"),
    }

    let stage_error = StageError::CommandError("Stage test error".to_string());
    let job_error: JobError = stage_error.into();

    match job_error {
        JobError::StageError(inner) => {
            match inner {
                StageError::CommandError(msg) => assert_eq!(msg, "Stage test error"),
                _ => panic!("Wrong stage error type"),
            }
        }
        _ => panic!("Wrong job error type"),
    }
}

/// Test RegexWrapper
#[test]
fn test_regex_wrapper() {
    let regex = RegexWrapper::new(r"^\d{3}-\d{2}-\d{4}$").unwrap();

    // Valid SSN format
    assert!(regex.is_match("123-45-6789"));

    // Invalid formats
    assert!(!regex.is_match("123-456-789"));
    assert!(!regex.is_match("abc-de-fghi"));
    assert!(!regex.is_match("123-45-67890"));

    // Test serialization
    let json = serde_json::to_string(&regex).unwrap();
    assert!(json.contains("^\\d{3}-\\d{2}-\\d{4}$"));

    // Test deserialization
    let deserialized: RegexWrapper = serde_json::from_str(&json).unwrap();
    assert!(deserialized.is_match("123-45-6789"));
}

/// Test VolumeMount
#[test]
fn test_volume_mount() {
    let volume = VolumeMount {
        source: "/host/path".to_string(),
        target: "/container/path".to_string(),
        read_only: true,
    };

    assert_eq!(volume.source, "/host/path");
    assert_eq!(volume.target, "/container/path");
    assert!(volume.read_only);

    // Test serialization
    let json = serde_json::to_string(&volume).unwrap();
    let deserialized: VolumeMount = serde_json::from_str(&json).unwrap();

    assert_eq!(deserialized.source, volume.source);
    assert_eq!(deserialized.target, volume.target);
    assert_eq!(deserialized.read_only, volume.read_only);
}

/// Test ResourceLimits
#[test]
fn test_resource_limits() {
    let limits = ResourceLimits {
        memory: Some("1GB".to_string()),
        cpu: Some("2".to_string()),
        timeout: Some(3600),
    };

    assert_eq!(limits.memory.as_ref().unwrap(), "1GB");
    assert_eq!(limits.cpu.as_ref().unwrap(), "2");
    assert_eq!(limits.timeout.unwrap(), 3600);

    // Test default
    let default_limits = ResourceLimits::default();
    assert!(default_limits.memory.is_none());
    assert!(default_limits.cpu.is_none());
    assert!(default_limits.timeout.is_none());

    // Test serialization
    let json = serde_json::to_string(&limits).unwrap();
    let deserialized: ResourceLimits = serde_json::from_str(&json).unwrap();

    assert_eq!(deserialized.memory, limits.memory);
    assert_eq!(deserialized.cpu, limits.cpu);
    assert_eq!(deserialized.timeout, limits.timeout);
}

/// Test Config structure
#[test]
fn test_config() {
    let mut config = Config::default();

    // Test default values
    assert_eq!(config.workflow_core_config_path, "./workflows");
    assert_eq!(config.workflow_core_stage_timeout, 300);
    assert_eq!(config.workflow_core_max_parallel, 10);
    assert!(!config.workflow_core_debug);

    // Test environment variable override
    std::env::set_var("WORKFLOW_CORE_CONFIG_PATH", "/custom/path");
    std::env::set_var("WORKFLOW_CORE_STAGE_TIMEOUT", "600");
    std::env::set_var("WORKFLOW_CORE_MAX_PARALLEL", "20");
    std::env::set_var("WORKFLOW_CORE_DEBUG", "true");

    config.load_from_env();

    assert_eq!(config.workflow_core_config_path, "/custom/path");
    assert_eq!(config.workflow_core_stage_timeout, 600);
    assert_eq!(config.workflow_core_max_parallel, 20);
    assert!(config.workflow_core_debug);

    // Clean up
    std::env::remove_var("WORKFLOW_CORE_CONFIG_PATH");
    std::env::remove_var("WORKFLOW_CORE_STAGE_TIMEOUT");
    std::env::remove_var("WORKFLOW_CORE_MAX_PARALLEL");
    std::env::remove_var("WORKFLOW_CORE_DEBUG");
}

/// Test Config serialization
#[test]
fn test_config_serialization() {
    let config = Config {
        workflow_core_config_path: "/test/path".to_string(),
        workflow_core_stage_timeout: 120,
        workflow_core_max_parallel: 5,
        workflow_core_debug: true,
    };

    // Test JSON serialization
    let json = serde_json::to_string(&config).unwrap();
    let deserialized: Config = serde_json::from_str(&json).unwrap();

    assert_eq!(deserialized.workflow_core_config_path, config.workflow_core_config_path);
    assert_eq!(deserialized.workflow_core_stage_timeout, config.workflow_core_stage_timeout);
    assert_eq!(deserialized.workflow_core_max_parallel, config.workflow_core_max_parallel);
    assert_eq!(deserialized.workflow_core_debug, config.workflow_core_debug);
}

/// Test template rendering with complex data
#[test]
fn test_complex_template_rendering() {
    let mut context = HashMap::new();
    context.insert("user".to_string(), json!({
        "name": "Alice",
        "profile": {
            "age": 25,
            "city": "Boston"
        }
    }));
    context.insert("items".to_string(), json!(["apple", "banana", "cherry"]));

    // Test nested object access
    let template = "User: {{user.name}}, Age: {{user.profile.age}}";
    let result = render_template(template, &context).unwrap();
    assert_eq!(result, "User: Alice, Age: 25");

    // Test array access
    let template = "First item: {{items.0}}";
    let result = render_template(template, &context).unwrap();
    assert_eq!(result, "First item: apple");
}

/// Test cross product with complex data types
#[test]
fn test_cross_product_complex_types() {
    let mut matrix = HashMap::new();
    matrix.insert("config".to_string(), vec![
        json!({"env": "dev", "debug": true}),
        json!({"env": "prod", "debug": false}),
    ]);
    matrix.insert("version".to_string(), vec![json!("1.0"), json!("2.0")]);

    let combinations = cross_product(&matrix);

    assert_eq!(combinations.len(), 4);

    // Check that complex objects are preserved
    let first_combo = &combinations[0];
    let config = first_combo.get("config").unwrap();
    assert!(config.is_object());
    assert_eq!(config.get("env").unwrap().as_str().unwrap(), "dev");
    assert_eq!(config.get("debug").unwrap().as_bool().unwrap(), true);
}

/// Test error chain functionality
#[test]
fn test_error_chain() {
    let stage_error = StageError::CommandError("Command 'ls' failed".to_string());
    let job_error: JobError = stage_error.into();
    let workflow_error: WorkflowError = job_error.into();

    let error_string = workflow_error.to_string();
    assert!(error_string.contains("Command 'ls' failed"));

    // Test that the error chain preserves information
    match workflow_error {
        WorkflowError::JobError(JobError::StageError(StageError::CommandError(msg))) => {
            assert_eq!(msg, "Command 'ls' failed");
        }
        _ => panic!("Error chain not preserved correctly"),
    }
}

/// Test ID generation uniqueness over multiple calls
#[test]
fn test_id_generation_uniqueness() {
    let mut ids = std::collections::HashSet::new();

    // Generate 1000 IDs and ensure they're all unique
    for _ in 0..1000 {
        let id = generate_id();
        assert!(!ids.contains(&id), "Duplicate ID generated: {}", id);
        ids.insert(id);
    }

    assert_eq!(ids.len(), 1000);
}
