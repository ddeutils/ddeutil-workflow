//! Cron scheduling module for workflow automation.
//!
//! This module provides functionality to schedule and run workflows
//! based on cron expressions and time triggers.

use chrono::{DateTime, Utc};
use cron::Schedule;
use serde::{Deserialize, Serialize};
use std::str::FromStr;
use tokio::time::{sleep, Duration};

use crate::error::{CronError, WorkflowResult};

/// Cron job configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CronJob {
    /// Cron expression (e.g., "0 */6 * * *")
    pub schedule: String,

    /// Timezone for the schedule
    pub timezone: Option<String>,

    /// Whether the job is enabled
    pub enabled: bool,

    /// Maximum number of concurrent executions
    pub max_concurrent: Option<u32>,

    /// Timeout for execution
    pub timeout: Option<u64>,
}

impl CronJob {
    /// Create new cron job
    pub fn new(schedule: String) -> Self {
        Self {
            schedule,
            timezone: None,
            enabled: true,
            max_concurrent: None,
            timeout: None,
        }
    }

    /// Validate cron expression
    pub fn validate(&self) -> Result<(), CronError> {
        Schedule::from_str(&self.schedule).map_err(|_| CronError::InvalidExpression {
            expression: self.schedule.clone(),
        })?;
        Ok(())
    }

    /// Get next execution time
    pub fn next_execution(&self) -> Result<DateTime<Utc>, CronError> {
        let schedule = Schedule::from_str(&self.schedule).map_err(|_| CronError::InvalidExpression {
            expression: self.schedule.clone(),
        })?;

        let now = Utc::now();
        schedule
            .upcoming(Utc)
            .next()
            .ok_or_else(|| CronError::ScheduleError {
                message: "No upcoming execution time found".to_string(),
            })
    }

    /// Get all execution times within a time range
    pub fn executions_in_range(
        &self,
        start: DateTime<Utc>,
        end: DateTime<Utc>,
    ) -> Result<Vec<DateTime<Utc>>, CronError> {
        let schedule = Schedule::from_str(&self.schedule).map_err(|_| CronError::InvalidExpression {
            expression: self.schedule.clone(),
        })?;

        let mut executions = Vec::new();
        for datetime in schedule.after(&start).take(1000) {
            if datetime > end {
                break;
            }
            executions.push(datetime);
        }

        Ok(executions)
    }
}

/// Cron runner for managing scheduled workflows
#[derive(Debug)]
pub struct CronRunner {
    /// List of scheduled jobs
    jobs: Vec<(String, CronJob)>,

    /// Whether the runner is active
    active: bool,
}

impl CronRunner {
    /// Create new cron runner
    pub fn new() -> Self {
        Self {
            jobs: Vec::new(),
            active: false,
        }
    }

    /// Add a cron job
    pub fn add_job(&mut self, workflow_name: String, cron_job: CronJob) -> WorkflowResult<()> {
        cron_job.validate()?;
        self.jobs.push((workflow_name, cron_job));
        Ok(())
    }

    /// Remove a cron job
    pub fn remove_job(&mut self, workflow_name: &str) -> bool {
        let initial_len = self.jobs.len();
        self.jobs.retain(|(name, _)| name != workflow_name);
        self.jobs.len() < initial_len
    }

    /// List all scheduled jobs
    pub fn list_jobs(&self) -> Vec<(String, &CronJob)> {
        self.jobs.iter().map(|(name, job)| (name.clone(), job)).collect()
    }

    /// Get next execution times for all jobs
    pub fn get_next_executions(&self) -> Vec<(String, Result<DateTime<Utc>, CronError>)> {
        self.jobs
            .iter()
            .map(|(name, job)| (name.clone(), job.next_execution()))
            .collect()
    }

    /// Start the cron runner
    pub async fn start(&mut self) -> WorkflowResult<()> {
        self.active = true;

        while self.active {
            let now = Utc::now();
            let mut next_check = now + chrono::Duration::minutes(1);

            // Check each job for execution
            for (workflow_name, job) in &self.jobs {
                if !job.enabled {
                    continue;
                }

                if let Ok(next_execution) = job.next_execution() {
                    if next_execution <= now + chrono::Duration::seconds(30) {
                        // Execute workflow (placeholder - would integrate with workflow executor)
                        tracing::info!(
                            "Executing scheduled workflow: {} at {}",
                            workflow_name,
                            next_execution
                        );

                        // In a real implementation, this would trigger workflow execution
                        // For now, just log the execution
                    }

                    if next_execution < next_check {
                        next_check = next_execution;
                    }
                }
            }

            // Sleep until next check time
            let sleep_duration = (next_check - now).to_std().unwrap_or(Duration::from_secs(60));
            sleep(sleep_duration).await;
        }

        Ok(())
    }

    /// Stop the cron runner
    pub fn stop(&mut self) {
        self.active = false;
    }

    /// Check if runner is active
    pub fn is_active(&self) -> bool {
        self.active
    }
}

impl Default for CronRunner {
    fn default() -> Self {
        Self::new()
    }
}

/// Helper functions for cron expressions
pub mod helpers {
    use super::*;

    /// Create cron expression for daily execution at specific time
    pub fn daily(hour: u32, minute: u32) -> String {
        format!("{} {} * * *", minute, hour)
    }

    /// Create cron expression for hourly execution
    pub fn hourly() -> String {
        "0 * * * *".to_string()
    }

    /// Create cron expression for weekly execution
    pub fn weekly(day: u32, hour: u32, minute: u32) -> String {
        format!("{} {} * * {}", minute, hour, day)
    }

    /// Create cron expression for monthly execution
    pub fn monthly(day: u32, hour: u32, minute: u32) -> String {
        format!("{} {} {} * *", minute, hour, day)
    }

    /// Validate cron expression
    pub fn validate_expression(expression: &str) -> Result<(), CronError> {
        Schedule::from_str(expression).map_err(|_| CronError::InvalidExpression {
            expression: expression.to_string(),
        })?;
        Ok(())
    }

    /// Get human-readable description of cron expression
    pub fn describe_expression(expression: &str) -> Result<String, CronError> {
        // This is a simplified description - a real implementation would use
        // a cron expression parser to provide detailed descriptions
        match expression {
            "0 * * * *" => Ok("Every hour".to_string()),
            "0 0 * * *" => Ok("Daily at midnight".to_string()),
            "0 12 * * *" => Ok("Daily at noon".to_string()),
            "0 0 * * 0" => Ok("Weekly on Sunday at midnight".to_string()),
            "0 0 1 * *" => Ok("Monthly on the 1st at midnight".to_string()),
            _ => Ok(format!("Custom schedule: {}", expression)),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cron_job_creation() {
        let job = CronJob::new("0 */6 * * *".to_string());
        assert_eq!(job.schedule, "0 */6 * * *");
        assert!(job.enabled);
        assert!(job.validate().is_ok());
    }

    #[test]
    fn test_invalid_cron_expression() {
        let job = CronJob::new("invalid expression".to_string());
        assert!(job.validate().is_err());
    }

    #[test]
    fn test_next_execution() {
        let job = CronJob::new("0 * * * *".to_string()); // Every hour
        let next = job.next_execution().unwrap();
        assert!(next > Utc::now());
    }

    #[test]
    fn test_cron_runner() {
        let mut runner = CronRunner::new();
        assert!(!runner.is_active());

        let job = CronJob::new("0 * * * *".to_string());
        runner.add_job("test-workflow".to_string(), job).unwrap();

        assert_eq!(runner.list_jobs().len(), 1);
        assert!(runner.remove_job("test-workflow"));
        assert_eq!(runner.list_jobs().len(), 0);
    }

    #[test]
    fn test_cron_helpers() {
        use helpers::*;

        assert_eq!(daily(12, 30), "30 12 * * *");
        assert_eq!(hourly(), "0 * * * *");
        assert_eq!(weekly(0, 12, 0), "0 12 * * 0");
        assert_eq!(monthly(1, 0, 0), "0 0 1 * *");

        assert!(validate_expression("0 * * * *").is_ok());
        assert!(validate_expression("invalid").is_err());

        assert!(describe_expression("0 * * * *").unwrap().contains("Every hour"));
    }
}
