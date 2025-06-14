//! Job execution and management module.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use crate::error::{JobError, JobResult, WorkflowResult};
use crate::event::EventManager;
use crate::result::{Result, Status};
use crate::stage::Stage;
use crate::types::{DictData, Matrix};

/// Job trigger rules for dependency handling
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Rule {
    /// All dependencies must succeed
    AllSuccess,
    /// All dependencies must fail
    AllFailed,
    /// At least one dependency must fail
    OneFailed,
    /// At least one dependency must succeed
    OneSuccess,
    /// All dependencies must be done (any final state)
    AllDone,
    /// No dependencies should fail
    NoneFailed,
    /// No dependencies should be skipped
    NoneSkipped,
}

impl Default for Rule {
    fn default() -> Self {
        Rule::AllSuccess
    }
}

/// Job execution environment configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunsOn {
    /// Execution type (local, docker, remote)
    pub r#type: String,

    /// Additional configuration for the execution environment
    pub config: DictData,
}

impl Default for RunsOn {
    fn default() -> Self {
        Self {
            r#type: "local".to_string(),
            config: HashMap::new(),
        }
    }
}

/// Matrix strategy for parameterized job execution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Strategy {
    /// Matrix parameters for cross-product execution
    pub matrix: Matrix,

    /// Maximum parallel executions
    pub max_parallel: Option<usize>,

    /// Whether to fail fast on first error
    pub fail_fast: bool,

    /// Combinations to exclude from matrix
    pub exclude: Vec<DictData>,

    /// Additional combinations to include
    pub include: Vec<DictData>,
}

impl Default for Strategy {
    fn default() -> Self {
        Self {
            matrix: HashMap::new(),
            max_parallel: None,
            fail_fast: true,
            exclude: Vec::new(),
            include: Vec::new(),
        }
    }
}

impl Strategy {
    /// Check if strategy is configured
    pub fn is_set(&self) -> bool {
        !self.matrix.is_empty()
    }

    /// Generate all matrix combinations
    pub fn make(&self) -> Vec<DictData> {
        if !self.is_set() {
            return vec![HashMap::new()];
        }

        let mut combinations = crate::utils::cross_product(&self.matrix);

        // Apply exclusions
        for exclude in &self.exclude {
            combinations.retain(|combo| !self.matches_filter(combo, exclude));
        }

        // Add inclusions
        combinations.extend(self.include.clone());

        combinations
    }

    /// Check if a combination matches a filter
    fn matches_filter(&self, combo: &DictData, filter: &DictData) -> bool {
        for (key, value) in filter {
            if let Some(combo_value) = combo.get(key) {
                if combo_value != value {
                    return false;
                }
            } else {
                return false;
            }
        }
        true
    }
}

/// Job execution unit containing multiple stages
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Job {
    /// Job identifier
    pub name: String,

    /// Job description
    pub desc: Option<String>,

    /// Job dependencies (other job names)
    pub needs: Vec<String>,

    /// Trigger rule for dependency handling
    #[serde(default)]
    pub trigger_rule: Rule,

    /// Execution environment configuration
    #[serde(default)]
    pub runs_on: RunsOn,

    /// Matrix strategy for parameterized execution
    #[serde(default)]
    pub strategy: Strategy,

    /// Job execution timeout in seconds
    pub timeout: Option<u64>,

    /// Continue on error flag
    #[serde(default)]
    pub continue_on_error: bool,

    /// Job condition for conditional execution
    pub r#if: Option<String>,

    /// List of stages to execute
    pub stages: Vec<Stage>,

    /// Extra configuration parameters
    #[serde(default)]
    pub extras: DictData,
}

impl Job {
    /// Create a new job with the given name
    pub fn new(name: String) -> Self {
        Self {
            name,
            desc: None,
            needs: Vec::new(),
            trigger_rule: Rule::default(),
            runs_on: RunsOn::default(),
            strategy: Strategy::default(),
            timeout: None,
            continue_on_error: false,
            r#if: None,
            stages: Vec::new(),
            extras: HashMap::new(),
        }
    }

    /// Execute the job with given parameters
    pub async fn execute(
        &self,
        params: DictData,
        result: Option<Result>,
        event_manager: &EventManager,
    ) -> JobResult<Result> {
        let mut job_result = result.unwrap_or_else(|| Result::new());

        // Check job condition
        if let Some(condition) = &self.r#if {
            if !self.evaluate_condition(condition, &params)? {
                job_result.update(Status::Skipped, None);
                return Ok(job_result);
            }
        }

        // Handle matrix strategy
        if self.strategy.is_set() {
            self.execute_matrix(params, job_result, event_manager).await
        } else {
            self.execute_single(params, job_result, event_manager).await
        }
    }

    /// Execute job with matrix strategy
    async fn execute_matrix(
        &self,
        params: DictData,
        mut result: Result,
        event_manager: &EventManager,
    ) -> JobResult<Result> {
        let combinations = self.strategy.make();
        let max_parallel = self.strategy.max_parallel.unwrap_or(crate::defaults::MAX_STAGE_PARALLEL);

        let mut matrix_results = Vec::new();
        let mut tasks = Vec::new();

        for (index, matrix_params) in combinations.into_iter().enumerate() {
            // Merge matrix parameters with job parameters
            let mut combined_params = params.clone();
            combined_params.insert("matrix".to_string(), serde_json::to_value(&matrix_params)?);

            // Create matrix-specific result
            let matrix_result = Result::with_parent(result.run_id.clone());

            let job_clone = self.clone();
            let event_manager_clone = event_manager.clone();

            let task = tokio::spawn(async move {
                job_clone.execute_single(combined_params, matrix_result, &event_manager_clone).await
            });

            tasks.push(task);

            // Limit parallel execution
            if tasks.len() >= max_parallel {
                // Wait for some tasks to complete
                let (completed, remaining) = futures::future::select_all(tasks).await;

                match completed {
                    Ok(matrix_result) => {
                        match matrix_result {
                            Ok(res) => matrix_results.push(res),
                            Err(e) => {
                                if self.strategy.fail_fast {
                                    return Err(e);
                                }
                                // Create failed result for this matrix combination
                                let mut failed_result = Result::with_parent(result.run_id.clone());
                                failed_result.update(Status::Failed, None);
                                failed_result.add_error("MatrixError".to_string(), e.to_string());
                                matrix_results.push(failed_result);
                            }
                        }
                    }
                    Err(e) => {
                        return Err(JobError::Execution {
                            job_id: self.name.clone(),
                            message: format!("Matrix task failed: {}", e),
                        });
                    }
                }

                tasks = remaining;
            }
        }

        // Wait for remaining tasks
        for task in tasks {
            match task.await {
                Ok(matrix_result) => {
                    match matrix_result {
                        Ok(res) => matrix_results.push(res),
                        Err(e) => {
                            if self.strategy.fail_fast {
                                return Err(e);
                            }
                            let mut failed_result = Result::with_parent(result.run_id.clone());
                            failed_result.update(Status::Failed, None);
                            failed_result.add_error("MatrixError".to_string(), e.to_string());
                            matrix_results.push(failed_result);
                        }
                    }
                }
                Err(e) => {
                    return Err(JobError::Execution {
                        job_id: self.name.clone(),
                        message: format!("Matrix task failed: {}", e),
                    });
                }
            }
        }

        // Aggregate matrix results
        let statuses: Vec<Status> = matrix_results.iter().map(|r| r.status).collect();
        let final_status = crate::result::validate_statuses(&statuses);

        // Merge matrix outputs
        for (index, matrix_result) in matrix_results.into_iter().enumerate() {
            result.add_output(
                format!("matrix.{}", index),
                serde_json::to_value(matrix_result.context)?,
            );
        }

        result.status = final_status;
        Ok(result)
    }

    /// Execute job as single instance
    async fn execute_single(
        &self,
        params: DictData,
        mut result: Result,
        event_manager: &EventManager,
    ) -> JobResult<Result> {
        // Execute stages sequentially
        for (index, stage) in self.stages.iter().enumerate() {
            // Check for cancellation
            if event_manager.is_cancelled().await {
                result.update(Status::Cancelled, None);
                return Ok(result);
            }

            // Execute stage
            match stage.execute(params.clone(), Some(result.clone()), event_manager).await {
                Ok(stage_result) => {
                    // Merge stage result
                    result.merge(stage_result.clone());

                    // Add stage output
                    result.add_output(
                        format!("stages.{}", index),
                        serde_json::to_value(stage_result.context)?,
                    );

                    // Check if stage failed and continue_on_error is false
                    if stage_result.status.is_failed() && !self.continue_on_error {
                        result.update(Status::Failed, None);
                        return Ok(result);
                    }
                }
                Err(e) => {
                    if !self.continue_on_error {
                        return Err(JobError::Stage {
                            job_id: self.name.clone(),
                            source: e,
                        });
                    } else {
                        // Log error but continue
                        result.add_error(
                            format!("Stage{}", index),
                            format!("Stage failed but continuing: {}", e),
                        );
                    }
                }
            }
        }

        // If we reach here, job completed successfully
        if result.status == Status::Wait {
            result.update(Status::Success, None);
        }

        Ok(result)
    }

    /// Evaluate job condition
    fn evaluate_condition(&self, condition: &str, params: &DictData) -> JobResult<bool> {
        // Simple condition evaluation - in a full implementation this would
        // use a proper expression evaluator

        // For now, just check if condition contains "true" or "false"
        let rendered = crate::utils::param_to_template(condition, params)
            .map_err(|e| JobError::Execution {
                job_id: self.name.clone(),
                message: format!("Failed to render condition: {}", e),
            })?;

        Ok(rendered.trim().to_lowercase() == "true")
    }

    /// Validate job configuration
    pub fn validate(&self) -> JobResult<()> {
        if self.name.is_empty() {
            return Err(JobError::Execution {
                job_id: "unknown".to_string(),
                message: "Job name cannot be empty".to_string(),
            });
        }

        if self.stages.is_empty() {
            return Err(JobError::Execution {
                job_id: self.name.clone(),
                message: "Job must have at least one stage".to_string(),
            });
        }

        // Validate stages
        for stage in &self.stages {
            stage.validate().map_err(|e| JobError::Stage {
                job_id: self.name.clone(),
                source: e,
            })?;
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::stage::EmptyStage;

    #[test]
    fn test_job_creation() {
        let job = Job::new("test-job".to_string());
        assert_eq!(job.name, "test-job");
        assert!(job.stages.is_empty());
        assert_eq!(job.trigger_rule, Rule::AllSuccess);
    }

    #[test]
    fn test_strategy_matrix() {
        let mut strategy = Strategy::default();
        strategy.matrix.insert("os".to_string(), vec![
            serde_json::json!("ubuntu"),
            serde_json::json!("windows"),
        ]);
        strategy.matrix.insert("version".to_string(), vec![
            serde_json::json!("3.9"),
            serde_json::json!("3.10"),
        ]);

        let combinations = strategy.make();
        assert_eq!(combinations.len(), 4);

        // Check that all combinations exist
        let has_ubuntu_39 = combinations.iter().any(|combo| {
            combo.get("os") == Some(&serde_json::json!("ubuntu")) &&
            combo.get("version") == Some(&serde_json::json!("3.9"))
        });
        assert!(has_ubuntu_39);
    }

    #[test]
    fn test_strategy_exclude() {
        let mut strategy = Strategy::default();
        strategy.matrix.insert("os".to_string(), vec![
            serde_json::json!("ubuntu"),
            serde_json::json!("windows"),
        ]);
        strategy.matrix.insert("version".to_string(), vec![
            serde_json::json!("3.9"),
            serde_json::json!("3.10"),
        ]);

        // Exclude ubuntu + 3.9 combination
        let mut exclude = HashMap::new();
        exclude.insert("os".to_string(), serde_json::json!("ubuntu"));
        exclude.insert("version".to_string(), serde_json::json!("3.9"));
        strategy.exclude.push(exclude);

        let combinations = strategy.make();
        assert_eq!(combinations.len(), 3); // 4 - 1 excluded

        // Check that excluded combination doesn't exist
        let has_ubuntu_39 = combinations.iter().any(|combo| {
            combo.get("os") == Some(&serde_json::json!("ubuntu")) &&
            combo.get("version") == Some(&serde_json::json!("3.9"))
        });
        assert!(!has_ubuntu_39);
    }

    #[tokio::test]
    async fn test_job_execution() {
        let mut job = Job::new("test-job".to_string());
        job.stages.push(Stage::Empty(EmptyStage {
            name: "test-stage".to_string(),
            echo: Some("Hello World".to_string()),
            sleep: 0.0,
            ..Default::default()
        }));

        let params = HashMap::new();
        let event_manager = EventManager::new(tokio::sync::mpsc::channel(1).0);

        let result = job.execute(params, None, &event_manager).await.unwrap();
        assert_eq!(result.status, Status::Success);
    }

    #[test]
    fn test_job_validation() {
        let mut job = Job::new("".to_string());
        assert!(job.validate().is_err());

        job.name = "test-job".to_string();
        assert!(job.validate().is_err()); // No stages

        job.stages.push(Stage::Empty(EmptyStage {
            name: "test-stage".to_string(),
            ..Default::default()
        }));
        assert!(job.validate().is_ok());
    }
}
