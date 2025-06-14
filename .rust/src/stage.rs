//! Stage execution module for the workflow system.
//!
//! This module defines various stage types that can be executed within workflow jobs.
//! Each stage type implements the `Stage` trait to provide consistent execution interface.

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::process::Stdio;
use tokio::process::Command;

use crate::error::{StageError, StageResult};
use crate::result::{Result as WorkflowResult, Status};
use crate::types::{DictData, ExecutionContext};

/// Main trait for all stage types
#[async_trait]
pub trait Stage: Send + Sync {
    /// Execute the stage and return results
    async fn execute(&self, context: &ExecutionContext) -> StageResult<WorkflowResult>;

    /// Get stage name
    fn name(&self) -> &str;

    /// Get stage description
    fn description(&self) -> Option<&str>;

    /// Validate stage configuration
    fn validate(&self) -> StageResult<()>;

    /// Check if stage should be skipped based on conditions
    async fn should_skip(&self, context: &ExecutionContext) -> bool;
}

/// Base stage configuration shared by all stage types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BaseStage {
    /// Stage name
    pub name: String,

    /// Stage description
    pub description: Option<String>,

    /// Skip condition expression
    pub if_condition: Option<String>,

    /// Continue on error
    pub continue_on_error: bool,

    /// Timeout in seconds
    pub timeout: Option<u64>,

    /// Environment variables
    pub env: HashMap<String, String>,

    /// Working directory
    pub working_dir: Option<String>,
}

impl Default for BaseStage {
    fn default() -> Self {
        Self {
            name: "unnamed-stage".to_string(),
            description: None,
            if_condition: None,
            continue_on_error: false,
            timeout: None,
            env: HashMap::new(),
            working_dir: None,
        }
    }
}

impl BaseStage {
    /// Create new base stage with name
    pub fn new(name: String) -> Self {
        Self {
            name,
            ..Default::default()
        }
    }

    /// Create execution context from base stage configuration
    pub fn create_context(&self) -> ExecutionContext {
        ExecutionContext {
            working_dir: self.working_dir.clone(),
            env: self.env.clone(),
            timeout: self.timeout,
            ..Default::default()
        }
    }

    /// Evaluate if condition
    pub async fn evaluate_condition(&self, _context: &ExecutionContext) -> bool {
        // For now, return true if no condition is set
        // In a real implementation, this would evaluate the condition expression
        self.if_condition.is_none()
    }
}

/// Empty stage that does nothing (useful for testing)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmptyStage {
    #[serde(flatten)]
    pub base: BaseStage,
}

#[async_trait]
impl Stage for EmptyStage {
    async fn execute(&self, _context: &ExecutionContext) -> StageResult<WorkflowResult> {
        Ok(WorkflowResult {
            status: Status::Success,
            output: Some("Empty stage completed".to_string()),
            error: None,
            duration: std::time::Duration::from_millis(1),
            metadata: HashMap::new(),
        })
    }

    fn name(&self) -> &str {
        &self.base.name
    }

    fn description(&self) -> Option<&str> {
        self.base.description.as_deref()
    }

    fn validate(&self) -> StageResult<()> {
        if self.base.name.is_empty() {
            return Err(StageError::Validation {
                stage_name: "unknown".to_string(),
                message: "Stage name cannot be empty".to_string(),
            });
        }
        Ok(())
    }

    async fn should_skip(&self, context: &ExecutionContext) -> bool {
        !self.base.evaluate_condition(context).await
    }
}

/// Bash/shell command stage
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BashStage {
    #[serde(flatten)]
    pub base: BaseStage,

    /// Shell command to execute
    pub run: String,

    /// Shell to use (default: /bin/bash)
    pub shell: Option<String>,
}

#[async_trait]
impl Stage for BashStage {
    async fn execute(&self, context: &ExecutionContext) -> StageResult<WorkflowResult> {
        let start_time = std::time::Instant::now();
        let shell = self.shell.as_deref().unwrap_or("/bin/bash");

        let mut cmd = Command::new(shell);
        cmd.arg("-c").arg(&self.run);

        // Set working directory
        if let Some(working_dir) = &context.working_dir {
            cmd.current_dir(working_dir);
        }

        // Set environment variables
        for (key, value) in &context.env {
            cmd.env(key, value);
        }

        // Configure stdio
        cmd.stdout(Stdio::piped()).stderr(Stdio::piped());

        let output = cmd.output().await.map_err(|e| StageError::Execution {
            stage_name: self.base.name.clone(),
            message: format!("Failed to execute command: {}", e),
        })?;

        let duration = start_time.elapsed();
        let stdout = String::from_utf8_lossy(&output.stdout).to_string();
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();

        let status = if output.status.success() {
            Status::Success
        } else {
            Status::Failure
        };

        let result_output = if !stdout.is_empty() {
            Some(stdout)
        } else if !stderr.is_empty() {
            Some(stderr)
        } else {
            None
        };

        let error = if !output.status.success() {
            Some(format!(
                "Command failed with exit code {:?}: {}",
                output.status.code(),
                stderr
            ))
        } else {
            None
        };

        Ok(WorkflowResult {
            status,
            output: result_output,
            error,
            duration,
            metadata: HashMap::new(),
        })
    }

    fn name(&self) -> &str {
        &self.base.name
    }

    fn description(&self) -> Option<&str> {
        self.base.description.as_deref()
    }

    fn validate(&self) -> StageResult<()> {
        if self.base.name.is_empty() {
            return Err(StageError::Validation {
                stage_name: "unknown".to_string(),
                message: "Stage name cannot be empty".to_string(),
            });
        }

        if self.run.is_empty() {
            return Err(StageError::Validation {
                stage_name: self.base.name.clone(),
                message: "Bash command cannot be empty".to_string(),
            });
        }

        Ok(())
    }

    async fn should_skip(&self, context: &ExecutionContext) -> bool {
        !self.base.evaluate_condition(context).await
    }
}

/// Python script execution stage
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PyStage {
    #[serde(flatten)]
    pub base: BaseStage,

    /// Python script content
    pub script: String,

    /// Python interpreter to use (default: python3)
    pub python: Option<String>,

    /// Additional arguments to pass to Python
    pub args: Vec<String>,
}

#[async_trait]
impl Stage for PyStage {
    async fn execute(&self, context: &ExecutionContext) -> StageResult<WorkflowResult> {
        let start_time = std::time::Instant::now();
        let python = self.python.as_deref().unwrap_or("python3");

        let mut cmd = Command::new(python);
        cmd.arg("-c").arg(&self.script);

        // Add additional arguments
        for arg in &self.args {
            cmd.arg(arg);
        }

        // Set working directory
        if let Some(working_dir) = &context.working_dir {
            cmd.current_dir(working_dir);
        }

        // Set environment variables
        for (key, value) in &context.env {
            cmd.env(key, value);
        }

        // Configure stdio
        cmd.stdout(Stdio::piped()).stderr(Stdio::piped());

        let output = cmd.output().await.map_err(|e| StageError::Execution {
            stage_name: self.base.name.clone(),
            message: format!("Failed to execute Python script: {}", e),
        })?;

        let duration = start_time.elapsed();
        let stdout = String::from_utf8_lossy(&output.stdout).to_string();
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();

        let status = if output.status.success() {
            Status::Success
        } else {
            Status::Failure
        };

        let result_output = if !stdout.is_empty() {
            Some(stdout)
        } else if !stderr.is_empty() {
            Some(stderr)
        } else {
            None
        };

        let error = if !output.status.success() {
            Some(format!(
                "Python script failed with exit code {:?}: {}",
                output.status.code(),
                stderr
            ))
        } else {
            None
        };

        Ok(WorkflowResult {
            status,
            output: result_output,
            error,
            duration,
            metadata: HashMap::new(),
        })
    }

    fn name(&self) -> &str {
        &self.base.name
    }

    fn description(&self) -> Option<&str> {
        self.base.description.as_deref()
    }

    fn validate(&self) -> StageResult<()> {
        if self.base.name.is_empty() {
            return Err(StageError::Validation {
                stage_name: "unknown".to_string(),
                message: "Stage name cannot be empty".to_string(),
            });
        }

        if self.script.is_empty() {
            return Err(StageError::Validation {
                stage_name: self.base.name.clone(),
                message: "Python script cannot be empty".to_string(),
            });
        }

        Ok(())
    }

    async fn should_skip(&self, context: &ExecutionContext) -> bool {
        !self.base.evaluate_condition(context).await
    }
}

/// Function call stage for registry functions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CallStage {
    #[serde(flatten)]
    pub base: BaseStage,

    /// Function name to call
    pub uses: String,

    /// Parameters to pass to the function
    pub with: DictData,
}

#[async_trait]
impl Stage for CallStage {
    async fn execute(&self, _context: &ExecutionContext) -> StageResult<WorkflowResult> {
        // This would integrate with the registry system to call functions
        // For now, return a placeholder implementation
        Ok(WorkflowResult {
            status: Status::Success,
            output: Some(format!("Called function: {}", self.uses)),
            error: None,
            duration: std::time::Duration::from_millis(100),
            metadata: self.with.clone(),
        })
    }

    fn name(&self) -> &str {
        &self.base.name
    }

    fn description(&self) -> Option<&str> {
        self.base.description.as_deref()
    }

    fn validate(&self) -> StageResult<()> {
        if self.base.name.is_empty() {
            return Err(StageError::Validation {
                stage_name: "unknown".to_string(),
                message: "Stage name cannot be empty".to_string(),
            });
        }

        if self.uses.is_empty() {
            return Err(StageError::Validation {
                stage_name: self.base.name.clone(),
                message: "Function name cannot be empty".to_string(),
            });
        }

        Ok(())
    }

    async fn should_skip(&self, context: &ExecutionContext) -> bool {
        !self.base.evaluate_condition(context).await
    }
}

/// Foreach stage for iterating over collections
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ForeachStage {
    #[serde(flatten)]
    pub base: BaseStage,

    /// Items to iterate over (expression that resolves to array)
    pub items: String,

    /// Variable name for current item
    pub item_var: String,

    /// Variable name for current index (optional)
    pub index_var: Option<String>,

    /// Nested stages to execute for each item
    pub stages: Vec<StageDefinition>,

    /// Maximum parallel executions
    pub max_parallel: Option<usize>,

    /// Whether to continue on individual item failure
    pub continue_on_error: bool,
}

#[async_trait]
impl Stage for ForeachStage {
    async fn execute(&self, context: &ExecutionContext) -> StageResult<WorkflowResult> {
        let start_time = std::time::Instant::now();

        // In a real implementation, this would:
        // 1. Evaluate the items expression to get the collection
        // 2. Execute nested stages for each item with proper variable substitution
        // 3. Handle parallel execution and error handling

        // For now, simulate iteration over a sample collection
        let sample_items = vec!["item1", "item2", "item3"];
        let mut results = Vec::new();
        let mut all_success = true;

        for (index, item) in sample_items.iter().enumerate() {
            // Create context with item variables
            let mut item_context = context.clone();
            item_context.env.insert(self.item_var.clone(), item.to_string());

            if let Some(index_var) = &self.index_var {
                item_context.env.insert(index_var.clone(), index.to_string());
            }

            // Execute nested stages (placeholder)
            for stage_def in &self.stages {
                let stage_result = format!("Executed {} for item: {}", stage_def.name, item);
                results.push(stage_result);
            }
        }

        let status = if all_success { Status::Success } else { Status::Failure };
        let output = Some(format!("Foreach completed: {} items processed", sample_items.len()));

        Ok(WorkflowResult {
            status,
            output,
            error: None,
            duration: start_time.elapsed(),
            metadata: {
                let mut meta = HashMap::new();
                meta.insert("processed_items".to_string(), serde_json::Value::Number(serde_json::Number::from(sample_items.len())));
                meta
            },
        })
    }

    fn name(&self) -> &str {
        &self.base.name
    }

    fn description(&self) -> Option<&str> {
        self.base.description.as_deref()
    }

    fn validate(&self) -> StageResult<()> {
        if self.base.name.is_empty() {
            return Err(StageError::Validation {
                stage_name: "unknown".to_string(),
                message: "Stage name cannot be empty".to_string(),
            });
        }

        if self.items.is_empty() {
            return Err(StageError::Validation {
                stage_name: self.base.name.clone(),
                message: "Items expression cannot be empty".to_string(),
            });
        }

        if self.item_var.is_empty() {
            return Err(StageError::Validation {
                stage_name: self.base.name.clone(),
                message: "Item variable name cannot be empty".to_string(),
            });
        }

        if self.stages.is_empty() {
            return Err(StageError::Validation {
                stage_name: self.base.name.clone(),
                message: "Foreach stage must have at least one nested stage".to_string(),
            });
        }

        Ok(())
    }

    async fn should_skip(&self, context: &ExecutionContext) -> bool {
        !self.base.evaluate_condition(context).await
    }
}

/// Until stage for conditional looping
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UntilStage {
    #[serde(flatten)]
    pub base: BaseStage,

    /// Condition expression to evaluate
    pub condition: String,

    /// Nested stages to execute in each iteration
    pub stages: Vec<StageDefinition>,

    /// Maximum number of iterations to prevent infinite loops
    pub max_iterations: u32,

    /// Delay between iterations in seconds
    pub delay: Option<f64>,

    /// Whether to continue on nested stage failure
    pub continue_on_error: bool,
}

#[async_trait]
impl Stage for UntilStage {
    async fn execute(&self, context: &ExecutionContext) -> StageResult<WorkflowResult> {
        let start_time = std::time::Instant::now();
        let mut iterations = 0;
        let mut condition_met = false;

        while iterations < self.max_iterations && !condition_met {
            iterations += 1;

            // Execute nested stages
            for stage_def in &self.stages {
                // In a real implementation, this would execute the actual stage
                tracing::info!("Executing stage {} in iteration {}", stage_def.name, iterations);
            }

            // Evaluate condition (placeholder - would use expression evaluator)
            condition_met = iterations >= 2; // Sample condition

            // Delay if specified
            if let Some(delay) = self.delay {
                tokio::time::sleep(std::time::Duration::from_secs_f64(delay)).await;
            }
        }

        let status = if condition_met {
            Status::Success
        } else {
            Status::Timeout // Reached max iterations
        };

        let output = Some(format!(
            "Until loop completed: {} iterations, condition met: {}",
            iterations, condition_met
        ));

        Ok(WorkflowResult {
            status,
            output,
            error: None,
            duration: start_time.elapsed(),
            metadata: {
                let mut meta = HashMap::new();
                meta.insert("iterations".to_string(), serde_json::Value::Number(serde_json::Number::from(iterations)));
                meta.insert("condition_met".to_string(), serde_json::Value::Bool(condition_met));
                meta
            },
        })
    }

    fn name(&self) -> &str {
        &self.base.name
    }

    fn description(&self) -> Option<&str> {
        self.base.description.as_deref()
    }

    fn validate(&self) -> StageResult<()> {
        if self.base.name.is_empty() {
            return Err(StageError::Validation {
                stage_name: "unknown".to_string(),
                message: "Stage name cannot be empty".to_string(),
            });
        }

        if self.condition.is_empty() {
            return Err(StageError::Validation {
                stage_name: self.base.name.clone(),
                message: "Condition expression cannot be empty".to_string(),
            });
        }

        if self.stages.is_empty() {
            return Err(StageError::Validation {
                stage_name: self.base.name.clone(),
                message: "Until stage must have at least one nested stage".to_string(),
            });
        }

        if self.max_iterations == 0 {
            return Err(StageError::Validation {
                stage_name: self.base.name.clone(),
                message: "Max iterations must be greater than 0".to_string(),
            });
        }

        Ok(())
    }

    async fn should_skip(&self, context: &ExecutionContext) -> bool {
        !self.base.evaluate_condition(context).await
    }
}

/// Case branch definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CaseBranch {
    /// Condition for this branch
    pub condition: String,

    /// Stages to execute if condition matches
    pub stages: Vec<StageDefinition>,
}

/// Case stage for conditional branching (like switch/case)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CaseStage {
    #[serde(flatten)]
    pub base: BaseStage,

    /// Expression to evaluate
    pub expression: String,

    /// Case branches
    pub cases: Vec<CaseBranch>,

    /// Default stages to execute if no case matches
    pub default: Option<Vec<StageDefinition>>,

    /// Whether to continue executing after first match
    pub fall_through: bool,
}

#[async_trait]
impl Stage for CaseStage {
    async fn execute(&self, context: &ExecutionContext) -> StageResult<WorkflowResult> {
        let start_time = std::time::Instant::now();
        let mut executed_cases = Vec::new();
        let mut matched = false;

        // Evaluate expression (placeholder - would use expression evaluator)
        let expression_value = "sample_value"; // This would be the actual evaluated expression

        // Check each case
        for (index, case_branch) in self.cases.iter().enumerate() {
            // Evaluate case condition (placeholder)
            let condition_matches = case_branch.condition.contains("sample"); // Sample condition check

            if condition_matches {
                matched = true;
                executed_cases.push(index);

                // Execute stages for this case
                for stage_def in &case_branch.stages {
                    // In a real implementation, this would execute the actual stage
                    tracing::info!("Executing stage {} in case {}", stage_def.name, index);
                }

                // Break if not fall-through
                if !self.fall_through {
                    break;
                }
            }
        }

        // Execute default if no cases matched
        if !matched && self.default.is_some() {
            if let Some(default_stages) = &self.default {
                for stage_def in default_stages {
                    tracing::info!("Executing default stage {}", stage_def.name);
                }
            }
        }

        let output = if matched {
            Some(format!("Case stage executed {} matching branches", executed_cases.len()))
        } else {
            Some("Case stage executed default branch".to_string())
        };

        Ok(WorkflowResult {
            status: Status::Success,
            output,
            error: None,
            duration: start_time.elapsed(),
            metadata: {
                let mut meta = HashMap::new();
                meta.insert("matched_cases".to_string(), serde_json::Value::Array(
                    executed_cases.into_iter().map(|i| serde_json::Value::Number(serde_json::Number::from(i))).collect()
                ));
                meta.insert("expression_value".to_string(), serde_json::Value::String(expression_value.to_string()));
                meta
            },
        })
    }

    fn name(&self) -> &str {
        &self.base.name
    }

    fn description(&self) -> Option<&str> {
        self.base.description.as_deref()
    }

    fn validate(&self) -> StageResult<()> {
        if self.base.name.is_empty() {
            return Err(StageError::Validation {
                stage_name: "unknown".to_string(),
                message: "Stage name cannot be empty".to_string(),
            });
        }

        if self.expression.is_empty() {
            return Err(StageError::Validation {
                stage_name: self.base.name.clone(),
                message: "Expression cannot be empty".to_string(),
            });
        }

        if self.cases.is_empty() {
            return Err(StageError::Validation {
                stage_name: self.base.name.clone(),
                message: "Case stage must have at least one case branch".to_string(),
            });
        }

        // Validate each case branch
        for (index, case_branch) in self.cases.iter().enumerate() {
            if case_branch.condition.is_empty() {
                return Err(StageError::Validation {
                    stage_name: self.base.name.clone(),
                    message: format!("Case branch {} condition cannot be empty", index),
                });
            }

            if case_branch.stages.is_empty() {
                return Err(StageError::Validation {
                    stage_name: self.base.name.clone(),
                    message: format!("Case branch {} must have at least one stage", index),
                });
            }
        }

        Ok(())
    }

    async fn should_skip(&self, context: &ExecutionContext) -> bool {
        !self.base.evaluate_condition(context).await
    }
}

/// Stage definition for nested stages in control flow stages
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StageDefinition {
    /// Stage name
    pub name: String,

    /// Stage type
    pub stage_type: String,

    /// Stage configuration
    pub config: DictData,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_empty_stage() {
        let stage = EmptyStage {
            base: BaseStage::new("test-empty".to_string()),
        };

        assert!(stage.validate().is_ok());
        assert_eq!(stage.name(), "test-empty");

        let context = ExecutionContext::default();
        let result = stage.execute(&context).await.unwrap();
        assert_eq!(result.status, Status::Success);
    }

    #[tokio::test]
    async fn test_bash_stage() {
        let stage = BashStage {
            base: BaseStage::new("test-bash".to_string()),
            run: "echo 'Hello World'".to_string(),
            shell: None,
        };

        assert!(stage.validate().is_ok());
        assert_eq!(stage.name(), "test-bash");

        let context = ExecutionContext::default();
        let result = stage.execute(&context).await.unwrap();
        assert_eq!(result.status, Status::Success);
        assert!(result.output.unwrap().contains("Hello World"));
    }

    #[tokio::test]
    async fn test_py_stage() {
        let stage = PyStage {
            base: BaseStage::new("test-python".to_string()),
            script: "print('Hello from Python')".to_string(),
            python: None,
            args: vec![],
        };

        assert!(stage.validate().is_ok());
        assert_eq!(stage.name(), "test-python");

        let context = ExecutionContext::default();
        let result = stage.execute(&context).await.unwrap();
        assert_eq!(result.status, Status::Success);
        assert!(result.output.unwrap().contains("Hello from Python"));
    }

    #[tokio::test]
    async fn test_foreach_stage() {
        let stage = ForeachStage {
            base: BaseStage::new("test-foreach".to_string()),
            items: "['item1', 'item2', 'item3']".to_string(),
            item_var: "item".to_string(),
            index_var: Some("index".to_string()),
            stages: vec![StageDefinition {
                name: "nested-stage".to_string(),
                stage_type: "bash".to_string(),
                config: HashMap::new(),
            }],
            max_parallel: None,
            continue_on_error: false,
        };

        assert!(stage.validate().is_ok());
        assert_eq!(stage.name(), "test-foreach");

        let context = ExecutionContext::default();
        let result = stage.execute(&context).await.unwrap();
        assert_eq!(result.status, Status::Success);
    }

    #[tokio::test]
    async fn test_until_stage() {
        let stage = UntilStage {
            base: BaseStage::new("test-until".to_string()),
            condition: "counter >= 5".to_string(),
            stages: vec![StageDefinition {
                name: "increment".to_string(),
                stage_type: "bash".to_string(),
                config: HashMap::new(),
            }],
            max_iterations: 10,
            delay: Some(0.1),
            continue_on_error: false,
        };

        assert!(stage.validate().is_ok());
        assert_eq!(stage.name(), "test-until");

        let context = ExecutionContext::default();
        let result = stage.execute(&context).await.unwrap();
        assert_eq!(result.status, Status::Success);
    }

    #[tokio::test]
    async fn test_case_stage() {
        let stage = CaseStage {
            base: BaseStage::new("test-case".to_string()),
            expression: "environment".to_string(),
            cases: vec![
                CaseBranch {
                    condition: "production".to_string(),
                    stages: vec![StageDefinition {
                        name: "deploy-prod".to_string(),
                        stage_type: "bash".to_string(),
                        config: HashMap::new(),
                    }],
                },
                CaseBranch {
                    condition: "staging".to_string(),
                    stages: vec![StageDefinition {
                        name: "deploy-staging".to_string(),
                        stage_type: "bash".to_string(),
                        config: HashMap::new(),
                    }],
                },
            ],
            default: Some(vec![StageDefinition {
                name: "deploy-dev".to_string(),
                stage_type: "bash".to_string(),
                config: HashMap::new(),
            }]),
            fall_through: false,
        };

        assert!(stage.validate().is_ok());
        assert_eq!(stage.name(), "test-case");

        let context = ExecutionContext::default();
        let result = stage.execute(&context).await.unwrap();
        assert_eq!(result.status, Status::Success);
    }

    #[test]
    fn test_stage_validation() {
        let empty_stage = EmptyStage {
            base: BaseStage::new("".to_string()),
        };
        assert!(empty_stage.validate().is_err());

        let bash_stage = BashStage {
            base: BaseStage::new("test".to_string()),
            run: "".to_string(),
            shell: None,
        };
        assert!(bash_stage.validate().is_err());

        let foreach_stage = ForeachStage {
            base: BaseStage::new("test".to_string()),
            items: "".to_string(), // Invalid: empty items
            item_var: "item".to_string(),
            index_var: None,
            stages: vec![],
            max_parallel: None,
            continue_on_error: false,
        };
        assert!(foreach_stage.validate().is_err());
    }
}
