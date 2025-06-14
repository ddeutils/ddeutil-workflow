//! Core workflow orchestration module.
//!
//! This module contains the main workflow orchestration functionality, including
//! the Workflow model, release management, and workflow execution strategies.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::Path;
use tokio::sync::mpsc;
use tokio::time::{timeout, Duration};

use crate::audit::{Audit, AuditModel};
use crate::config::Config;
use crate::cron::Crontab;
use crate::error::{WorkflowError, WorkflowResult};
use crate::event::{Event, EventManager};
use crate::job::Job;
use crate::params::Param;
use crate::result::{Result, Status, validate_statuses};
use crate::trace::{Trace, TraceModel};
use crate::types::{DictData, StrOrNone};
use crate::utils::{generate_id, template_render, param_to_template};

/// Release type enumeration for workflow execution modes.
///
/// This enum defines the different types of workflow releases that can be
/// triggered, each with specific behavior and use cases.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ReleaseType {
    /// Standard workflow release execution
    Normal,
    /// Re-execution of previously failed workflow
    Rerun,
    /// Event-triggered workflow execution
    Event,
    /// Forced execution bypassing normal conditions
    Force,
}

impl Default for ReleaseType {
    fn default() -> Self {
        ReleaseType::Normal
    }
}

/// Main workflow orchestration model for job and schedule management.
///
/// The Workflow struct is the core component of the workflow orchestration system.
/// It manages job execution, scheduling via cron expressions, parameter handling,
/// and provides comprehensive execution capabilities for complex workflows.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Workflow {
    /// Extra parameters for overriding configuration values
    pub extras: DictData,

    /// Unique workflow identifier
    pub name: String,

    /// Workflow description supporting markdown content
    pub desc: Option<String>,

    /// Parameter definitions for the workflow
    pub params: HashMap<String, Param>,

    /// Schedule definitions using cron expressions
    pub on: Vec<Crontab>,

    /// Collection of jobs within this workflow
    pub jobs: HashMap<String, Job>,
}

impl Workflow {
    /// Create a new workflow with the given name
    ///
    /// # Arguments
    ///
    /// * `name` - Workflow name
    ///
    /// # Returns
    ///
    /// New Workflow instance
    pub fn new(name: String) -> Self {
        Self {
            extras: HashMap::new(),
            name,
            desc: None,
            params: HashMap::new(),
            on: Vec::new(),
            jobs: HashMap::new(),
        }
    }

    /// Create Workflow instance from configuration file.
    ///
    /// Loads workflow configuration from YAML files and creates a validated
    /// Workflow instance. The configuration loader searches for workflow
    /// definitions in the specified path or default configuration directories.
    ///
    /// # Arguments
    ///
    /// * `name` - Workflow name to load from configuration
    /// * `path` - Optional custom configuration path to search
    /// * `extras` - Additional parameters to override configuration values
    ///
    /// # Returns
    ///
    /// Validated Workflow instance loaded from configuration
    ///
    /// # Errors
    ///
    /// Returns `WorkflowError` if workflow type doesn't match or configuration invalid
    ///
    /// # Examples
    ///
    /// ```rust
    /// use ddeutil_workflow::Workflow;
    ///
    /// #[tokio::main]
    /// async fn main() -> Result<(), Box<dyn std::error::Error>> {
    ///     // Load from default config path
    ///     let workflow = Workflow::from_config("data-pipeline").await?;
    ///
    ///     // Load with custom extras
    ///     let mut extras = std::collections::HashMap::new();
    ///     extras.insert("environment".to_string(), serde_json::json!("production"));
    ///     let workflow = Workflow::from_config_with_extras("data-pipeline", extras).await?;
    ///
    ///     Ok(())
    /// }
    /// ```
    pub async fn from_config(name: &str) -> WorkflowResult<Self> {
        Self::from_config_with_extras(name, HashMap::new()).await
    }

    /// Create Workflow instance from configuration with extra parameters
    pub async fn from_config_with_extras(name: &str, extras: DictData) -> WorkflowResult<Self> {
        let config = Config::load().await?;
        let workflow_config = config.get_workflow_config(name)?;

        // Parse workflow from configuration
        let mut workflow: Workflow = serde_yaml::from_value(workflow_config)
            .map_err(|e| WorkflowError::Config {
                message: format!("Failed to parse workflow config: {}", e),
            })?;

        // Apply extras
        workflow.extras.extend(extras);

        // Validate workflow
        workflow.validate()?;

        Ok(workflow)
    }

    /// Validate workflow configuration
    fn validate(&self) -> WorkflowResult<()> {
        // Validate job dependencies
        for (job_id, job) in &self.jobs {
            for need in &job.needs {
                if !self.jobs.contains_key(need) {
                    return Err(WorkflowError::Validation {
                        message: format!("Job '{}' depends on non-existent job '{}'", job_id, need),
                    });
                }
            }
        }

        // Validate cron schedules
        for crontab in &self.on {
            crontab.validate()?;
        }

        Ok(())
    }

    /// Get a job by name
    ///
    /// # Arguments
    ///
    /// * `name` - Job name to retrieve
    ///
    /// # Returns
    ///
    /// Reference to the job if found
    ///
    /// # Errors
    ///
    /// Returns error if job not found
    pub fn job(&self, name: &str) -> WorkflowResult<&Job> {
        self.jobs.get(name).ok_or_else(|| WorkflowError::Validation {
            message: format!("Job '{}' not found in workflow '{}'", name, self.name),
        })
    }

    /// Parameterize workflow parameters with provided values
    ///
    /// # Arguments
    ///
    /// * `params` - Parameter values to apply
    ///
    /// # Returns
    ///
    /// Processed parameter context
    pub fn parameterize(&self, params: &DictData) -> WorkflowResult<DictData> {
        let mut result = HashMap::new();

        // Process each defined parameter
        for (key, param_def) in &self.params {
            let value = if let Some(provided_value) = params.get(key) {
                // Use provided value, validate against type if needed
                param_def.validate_value(provided_value)?
            } else if let Some(default_value) = &param_def.default {
                // Use default value
                default_value.clone()
            } else {
                return Err(WorkflowError::Validation {
                    message: format!("Required parameter '{}' not provided", key),
                });
            };

            result.insert(key.clone(), value);
        }

        // Add any extra parameters not defined in schema
        for (key, value) in params {
            if !result.contains_key(key) {
                result.insert(key.clone(), value.clone());
            }
        }

        Ok(result)
    }

    /// Execute the workflow with provided parameters
    ///
    /// # Arguments
    ///
    /// * `params` - Execution parameters
    /// * `run_id` - Optional custom run ID
    /// * `parent_run_id` - Optional parent run ID for nested execution
    /// * `timeout_seconds` - Execution timeout in seconds
    /// * `max_job_parallel` - Maximum parallel job execution
    ///
    /// # Returns
    ///
    /// Execution result with status and context
    pub async fn execute(
        &self,
        params: DictData,
        run_id: Option<String>,
        parent_run_id: Option<String>,
        timeout_seconds: Option<u64>,
        max_job_parallel: Option<usize>,
    ) -> WorkflowResult<Result> {
        let execution_timeout = Duration::from_secs(timeout_seconds.unwrap_or(crate::defaults::DEFAULT_TIMEOUT));
        let max_parallel = max_job_parallel.unwrap_or(crate::defaults::MAX_JOB_PARALLEL);

        // Execute with timeout
        match timeout(execution_timeout, self.execute_internal(params, run_id, parent_run_id, max_parallel)).await {
            Ok(result) => result,
            Err(_) => {
                let mut error_result = Result::new();
                error_result.update(Status::Failed, None);
                error_result.add_error(
                    "WorkflowTimeout".to_string(),
                    format!("Workflow execution timed out after {} seconds", execution_timeout.as_secs()),
                );
                Ok(error_result)
            }
        }
    }

    /// Internal execution logic without timeout wrapper
    async fn execute_internal(
        &self,
        params: DictData,
        run_id: Option<String>,
        parent_run_id: Option<String>,
        max_parallel: usize,
    ) -> WorkflowResult<Result> {
        // Create execution context
        let execution_id = run_id.unwrap_or_else(|| generate_id(&self.name, true));
        let mut result = Result::from_result_or_new(None, Some(execution_id.clone()), parent_run_id);

        // Initialize trace
        let trace = TraceModel::new(&execution_id, result.parent_run_id.as_deref());
        result.trace = Some(trace);

        // Log workflow start
        if let Some(ref trace) = result.trace {
            trace.info(&format!("🚀 Starting workflow: {}", self.name)).await;
            trace.info(&format!("📋 Parameters: {}", serde_json::to_string_pretty(&params).unwrap_or_default())).await;
        }

        // Parameterize inputs
        let processed_params = match self.parameterize(&params) {
            Ok(params) => params,
            Err(e) => {
                result.update(Status::Failed, None);
                result.add_error("ParameterError".to_string(), e.to_string());
                return Ok(result);
            }
        };

        // Create event manager for cancellation
        let (event_tx, event_rx) = mpsc::channel(100);
        let event_manager = EventManager::new(event_tx);

        // Execute jobs based on dependency order
        match self.execute_jobs(processed_params, &mut result, &event_manager, max_parallel).await {
            Ok(_) => {
                if let Some(ref trace) = result.trace {
                    trace.info(&format!("✅ Workflow completed: {}", self.name)).await;
                }
                result.update(Status::Success, None);
            }
            Err(e) => {
                if let Some(ref trace) = result.trace {
                    trace.error(&format!("❌ Workflow failed: {}", e)).await;
                }
                result.update(Status::Failed, None);
                result.add_error("WorkflowError".to_string(), e.to_string());
            }
        }

        Ok(result)
    }

    /// Execute jobs in dependency order with parallel execution where possible
    async fn execute_jobs(
        &self,
        params: DictData,
        result: &mut Result,
        event_manager: &EventManager,
        max_parallel: usize,
    ) -> WorkflowResult<()> {
        // Build dependency graph and execution order
        let execution_order = self.build_execution_order()?;
        let mut job_results: HashMap<String, Result> = HashMap::new();

        // Execute jobs in batches based on dependencies
        for job_batch in execution_order {
            let mut batch_tasks = Vec::new();

            // Create tasks for this batch
            for job_id in job_batch {
                let job = self.jobs.get(&job_id).unwrap(); // Safe due to validation
                let job_params = params.clone();
                let job_result = Result::with_parent(result.run_id.clone());

                // Check if job should be skipped based on dependencies
                if self.should_skip_job(&job_id, &job_results)? {
                    let mut skipped_result = job_result;
                    skipped_result.update(Status::Skipped, None);
                    job_results.insert(job_id.clone(), skipped_result);
                    continue;
                }

                let job_clone = job.clone();
                let job_id_clone = job_id.clone();
                let event_manager_clone = event_manager.clone();

                let task = tokio::spawn(async move {
                    let job_result = job_clone.execute(job_params, Some(job_result), &event_manager_clone).await;
                    (job_id_clone, job_result)
                });

                batch_tasks.push(task);

                // Limit parallel execution
                if batch_tasks.len() >= max_parallel {
                    break;
                }
            }

            // Wait for batch completion
            for task in batch_tasks {
                match task.await {
                    Ok((job_id, job_result)) => {
                        match job_result {
                            Ok(res) => {
                                job_results.insert(job_id, res);
                            }
                            Err(e) => {
                                let mut error_result = Result::with_parent(result.run_id.clone());
                                error_result.update(Status::Failed, None);
                                error_result.add_error("JobError".to_string(), e.to_string());
                                job_results.insert(job_id, error_result);
                            }
                        }
                    }
                    Err(e) => {
                        return Err(WorkflowError::Execution {
                            message: format!("Job execution task failed: {}", e),
                        });
                    }
                }
            }
        }

        // Aggregate results
        let statuses: Vec<Status> = job_results.values().map(|r| r.status).collect();
        let final_status = validate_statuses(&statuses);

        // Merge job outputs into workflow result
        for (job_id, job_result) in job_results {
            result.add_output(format!("jobs.{}", job_id), serde_json::to_value(job_result.context)?);
        }

        result.status = final_status;

        if final_status.is_failed() {
            return Err(WorkflowError::Execution {
                message: "One or more jobs failed".to_string(),
            });
        }

        Ok(())
    }

    /// Build execution order based on job dependencies
    fn build_execution_order(&self) -> WorkflowResult<Vec<Vec<String>>> {
        let mut order = Vec::new();
        let mut remaining_jobs: HashMap<String, Vec<String>> = self.jobs
            .iter()
            .map(|(id, job)| (id.clone(), job.needs.clone()))
            .collect();
        let mut completed_jobs = std::collections::HashSet::new();

        while !remaining_jobs.is_empty() {
            let mut current_batch = Vec::new();

            // Find jobs with no remaining dependencies
            for (job_id, dependencies) in &remaining_jobs {
                if dependencies.iter().all(|dep| completed_jobs.contains(dep)) {
                    current_batch.push(job_id.clone());
                }
            }

            if current_batch.is_empty() {
                return Err(WorkflowError::Validation {
                    message: "Circular dependency detected in job dependencies".to_string(),
                });
            }

            // Remove completed jobs from remaining
            for job_id in &current_batch {
                remaining_jobs.remove(job_id);
                completed_jobs.insert(job_id.clone());
            }

            order.push(current_batch);
        }

        Ok(order)
    }

    /// Check if a job should be skipped based on dependency results
    fn should_skip_job(&self, job_id: &str, job_results: &HashMap<String, Result>) -> WorkflowResult<bool> {
        let job = self.jobs.get(job_id).unwrap();

        // Check dependency results based on trigger rule
        for dependency in &job.needs {
            if let Some(dep_result) = job_results.get(dependency) {
                match job.trigger_rule {
                    crate::job::Rule::AllSuccess => {
                        if !dep_result.status.is_success() {
                            return Ok(true);
                        }
                    }
                    crate::job::Rule::AllFailed => {
                        if !dep_result.status.is_failed() {
                            return Ok(true);
                        }
                    }
                    crate::job::Rule::OneFailed => {
                        if dep_result.status.is_failed() {
                            return Ok(false); // Don't skip if one failed
                        }
                    }
                    crate::job::Rule::OneSuccess => {
                        if dep_result.status.is_success() {
                            return Ok(false); // Don't skip if one succeeded
                        }
                    }
                    crate::job::Rule::AllDone => {
                        if !dep_result.status.is_final() {
                            return Ok(true);
                        }
                    }
                    crate::job::Rule::NoneFailed => {
                        if dep_result.status.is_failed() {
                            return Ok(true);
                        }
                    }
                    crate::job::Rule::NoneSkipped => {
                        if dep_result.status.is_skipped() {
                            return Ok(true);
                        }
                    }
                }
            }
        }

        Ok(false)
    }

    /// Execute workflow with release management
    pub async fn release(
        &self,
        release_time: DateTime<Utc>,
        params: DictData,
        release_type: ReleaseType,
        run_id: Option<String>,
        parent_run_id: Option<String>,
        audit: Option<Box<dyn Audit>>,
        timeout_seconds: Option<u64>,
    ) -> WorkflowResult<Result> {
        // Validate release time
        let validated_time = self.validate_release_time(release_time)?;

        // Execute workflow
        let mut result = self.execute(params, run_id, parent_run_id, timeout_seconds, None).await?;

        // Add release metadata
        result.add_output("release".to_string(), serde_json::json!({
            "type": release_type,
            "time": validated_time,
            "workflow": self.name
        }));

        // Write audit if provided
        if let Some(audit_writer) = audit {
            let audit_data = AuditModel {
                run_id: result.run_id.clone(),
                workflow_name: self.name.clone(),
                status: result.status,
                start_time: result.timestamp,
                end_time: Utc::now(),
                context: result.context.clone(),
            };

            if let Err(e) = audit_writer.write(&audit_data).await {
                tracing::warn!("Failed to write audit data: {}", e);
            }
        }

        Ok(result)
    }

    /// Validate release time against workflow schedule
    fn validate_release_time(&self, release_time: DateTime<Utc>) -> WorkflowResult<DateTime<Utc>> {
        // For now, just return the provided time
        // In a full implementation, this would validate against cron schedules
        Ok(release_time)
    }

    /// Re-run a failed workflow with previous context
    pub async fn rerun(
        &self,
        previous_context: DictData,
        parent_run_id: Option<String>,
        timeout_seconds: Option<u64>,
        max_job_parallel: Option<usize>,
    ) -> WorkflowResult<Result> {
        // Extract parameters from previous context
        let params = previous_context.get("params")
            .and_then(|p| serde_json::from_value(p.clone()).ok())
            .unwrap_or_default();

        // Execute with rerun type
        self.execute(params, None, parent_run_id, timeout_seconds, max_job_parallel).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::job::{Job, Rule, RunsOn};
    use crate::stage::EmptyStage;

    #[tokio::test]
    async fn test_workflow_creation() {
        let workflow = Workflow::new("test-workflow".to_string());
        assert_eq!(workflow.name, "test-workflow");
        assert!(workflow.jobs.is_empty());
        assert!(workflow.params.is_empty());
    }

    #[tokio::test]
    async fn test_workflow_execution() {
        let mut workflow = Workflow::new("test-workflow".to_string());

        // Add a simple job
        let mut job = Job::new("test-job".to_string());
        job.stages.push(crate::stage::Stage::Empty(EmptyStage {
            name: "test-stage".to_string(),
            echo: Some("Hello World".to_string()),
            sleep: 0.0,
            ..Default::default()
        }));

        workflow.jobs.insert("test-job".to_string(), job);

        let params = HashMap::new();
        let result = workflow.execute(params, None, None, Some(30), None).await.unwrap();

        assert_eq!(result.status, Status::Success);
    }

    #[test]
    fn test_dependency_order() {
        let mut workflow = Workflow::new("test-workflow".to_string());

        // Job A (no dependencies)
        let job_a = Job::new("job-a".to_string());
        workflow.jobs.insert("job-a".to_string(), job_a);

        // Job B (depends on A)
        let mut job_b = Job::new("job-b".to_string());
        job_b.needs = vec!["job-a".to_string()];
        workflow.jobs.insert("job-b".to_string(), job_b);

        // Job C (depends on A and B)
        let mut job_c = Job::new("job-c".to_string());
        job_c.needs = vec!["job-a".to_string(), "job-b".to_string()];
        workflow.jobs.insert("job-c".to_string(), job_c);

        let order = workflow.build_execution_order().unwrap();

        assert_eq!(order.len(), 3);
        assert_eq!(order[0], vec!["job-a"]);
        assert_eq!(order[1], vec!["job-b"]);
        assert_eq!(order[2], vec!["job-c"]);
    }

    #[test]
    fn test_circular_dependency_detection() {
        let mut workflow = Workflow::new("test-workflow".to_string());

        // Job A depends on B
        let mut job_a = Job::new("job-a".to_string());
        job_a.needs = vec!["job-b".to_string()];
        workflow.jobs.insert("job-a".to_string(), job_a);

        // Job B depends on A (circular)
        let mut job_b = Job::new("job-b".to_string());
        job_b.needs = vec!["job-a".to_string()];
        workflow.jobs.insert("job-b".to_string(), job_b);

        let result = workflow.build_execution_order();
        assert!(result.is_err());
    }
}
