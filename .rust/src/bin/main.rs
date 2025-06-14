//! Command-line interface for the DDE Workflow orchestration system.

use clap::{Parser, Subcommand};
use ddeutil_workflow::{Workflow, Result as WorkflowResult};
use serde_json::Value;
use std::collections::HashMap;
use std::path::PathBuf;
use tokio;
use tracing::{info, error};
use tracing_subscriber;

#[derive(Parser)]
#[command(name = "workflow-cli")]
#[command(about = "DDE Workflow - Lightweight workflow orchestration")]
#[command(version)]
struct Cli {
    #[command(subcommand)]
    command: Commands,

    /// Enable verbose logging
    #[arg(short, long)]
    verbose: bool,

    /// Configuration file path
    #[arg(short, long)]
    config: Option<PathBuf>,
}

#[derive(Subcommand)]
enum Commands {
    /// Execute a workflow
    Run {
        /// Workflow name to execute
        workflow: String,

        /// Parameters as JSON string
        #[arg(short, long)]
        params: Option<String>,

        /// Execution timeout in seconds
        #[arg(short, long, default_value = "3600")]
        timeout: u64,

        /// Maximum parallel jobs
        #[arg(short, long, default_value = "2")]
        max_parallel: usize,

        /// Custom run ID
        #[arg(short, long)]
        run_id: Option<String>,
    },

    /// List available workflows
    List,

    /// Validate workflow configuration
    Validate {
        /// Workflow name to validate
        workflow: String,
    },

    /// Show workflow information
    Info {
        /// Workflow name to show info for
        workflow: String,
    },

    /// Start workflow scheduler daemon
    Schedule {
        /// Workflows to schedule (comma-separated)
        workflows: Option<String>,

        /// Check interval in seconds
        #[arg(short, long, default_value = "60")]
        interval: u64,
    },
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();

    // Initialize logging
    let log_level = if cli.verbose { "debug" } else { "info" };
    tracing_subscriber::fmt()
        .with_env_filter(format!("ddeutil_workflow={},workflow_cli={}", log_level, log_level))
        .init();

    // Load environment variables
    dotenvy::dotenv().ok();

    match cli.command {
        Commands::Run {
            workflow,
            params,
            timeout,
            max_parallel,
            run_id,
        } => {
            run_workflow(workflow, params, timeout, max_parallel, run_id).await?;
        }

        Commands::List => {
            list_workflows().await?;
        }

        Commands::Validate { workflow } => {
            validate_workflow(workflow).await?;
        }

        Commands::Info { workflow } => {
            show_workflow_info(workflow).await?;
        }

        Commands::Schedule { workflows, interval } => {
            start_scheduler(workflows, interval).await?;
        }
    }

    Ok(())
}

async fn run_workflow(
    workflow_name: String,
    params_json: Option<String>,
    timeout: u64,
    max_parallel: usize,
    run_id: Option<String>,
) -> Result<(), Box<dyn std::error::Error>> {
    info!("🚀 Loading workflow: {}", workflow_name);

    // Load workflow
    let workflow = Workflow::from_config(&workflow_name).await?;

    // Parse parameters
    let params: HashMap<String, Value> = if let Some(params_str) = params_json {
        serde_json::from_str(&params_str)?
    } else {
        HashMap::new()
    };

    info!("📋 Parameters: {}", serde_json::to_string_pretty(&params)?);

    // Execute workflow
    let start_time = std::time::Instant::now();
    let result = workflow.execute(
        params,
        run_id,
        None,
        Some(timeout),
        Some(max_parallel),
    ).await?;

    let duration = start_time.elapsed();

    // Display results
    match result.status {
        ddeutil_workflow::Status::Success => {
            info!("✅ Workflow completed successfully in {:.2}s", duration.as_secs_f64());
            info!("📊 Run ID: {}", result.run_id);

            if let Some(outputs) = result.get_outputs() {
                info!("📤 Outputs:\n{}", serde_json::to_string_pretty(outputs)?);
            }
        }
        ddeutil_workflow::Status::Failed => {
            error!("❌ Workflow failed in {:.2}s", duration.as_secs_f64());
            error!("📊 Run ID: {}", result.run_id);

            if let Some(errors) = result.get_errors() {
                error!("🚨 Errors:\n{}", serde_json::to_string_pretty(errors)?);
            }

            std::process::exit(1);
        }
        ddeutil_workflow::Status::Cancelled => {
            error!("🚫 Workflow was cancelled in {:.2}s", duration.as_secs_f64());
            std::process::exit(2);
        }
        ddeutil_workflow::Status::Skipped => {
            info!("⏭️ Workflow was skipped in {:.2}s", duration.as_secs_f64());
        }
        ddeutil_workflow::Status::Wait => {
            error!("⏳ Workflow is still waiting (unexpected state)");
            std::process::exit(3);
        }
    }

    Ok(())
}

async fn list_workflows() -> Result<(), Box<dyn std::error::Error>> {
    info!("📋 Available workflows:");

    // This would typically scan configuration directories
    // For now, just show a placeholder
    println!("  • data-pipeline");
    println!("  • etl-process");
    println!("  • backup-job");

    Ok(())
}

async fn validate_workflow(workflow_name: String) -> Result<(), Box<dyn std::error::Error>> {
    info!("🔍 Validating workflow: {}", workflow_name);

    match Workflow::from_config(&workflow_name).await {
        Ok(_) => {
            info!("✅ Workflow configuration is valid");
        }
        Err(e) => {
            error!("❌ Workflow validation failed: {}", e);
            std::process::exit(1);
        }
    }

    Ok(())
}

async fn show_workflow_info(workflow_name: String) -> Result<(), Box<dyn std::error::Error>> {
    info!("📖 Workflow information: {}", workflow_name);

    let workflow = Workflow::from_config(&workflow_name).await?;

    println!("Name: {}", workflow.name);

    if let Some(desc) = &workflow.desc {
        println!("Description: {}", desc);
    }

    println!("Jobs: {}", workflow.jobs.len());
    for (job_id, job) in &workflow.jobs {
        println!("  • {} ({} stages)", job_id, job.stages.len());
        if !job.needs.is_empty() {
            println!("    Depends on: {}", job.needs.join(", "));
        }
    }

    println!("Parameters: {}", workflow.params.len());
    for (param_name, param) in &workflow.params {
        println!("  • {} ({})", param_name, param.param_type);
        if let Some(default) = &param.default {
            println!("    Default: {}", default);
        }
    }

    println!("Schedules: {}", workflow.on.len());
    for (i, schedule) in workflow.on.iter().enumerate() {
        println!("  • Schedule {}: {}", i + 1, schedule.cronjob);
    }

    Ok(())
}

async fn start_scheduler(
    workflows: Option<String>,
    interval: u64,
) -> Result<(), Box<dyn std::error::Error>> {
    info!("⏰ Starting workflow scheduler");

    let workflow_names = if let Some(names) = workflows {
        names.split(',').map(|s| s.trim().to_string()).collect()
    } else {
        // Load all available workflows
        vec!["data-pipeline".to_string()] // Placeholder
    };

    info!("📋 Monitoring workflows: {}", workflow_names.join(", "));
    info!("⏱️ Check interval: {}s", interval);

    // Main scheduler loop
    let mut interval_timer = tokio::time::interval(tokio::time::Duration::from_secs(interval));

    loop {
        interval_timer.tick().await;

        for workflow_name in &workflow_names {
            match check_and_run_scheduled_workflow(workflow_name).await {
                Ok(executed) => {
                    if executed {
                        info!("🎯 Executed scheduled workflow: {}", workflow_name);
                    }
                }
                Err(e) => {
                    error!("❌ Failed to check workflow {}: {}", workflow_name, e);
                }
            }
        }
    }
}

async fn check_and_run_scheduled_workflow(workflow_name: &str) -> Result<bool, Box<dyn std::error::Error>> {
    let workflow = Workflow::from_config(workflow_name).await?;

    // Check if any schedule should trigger now
    let now = chrono::Utc::now();

    for schedule in &workflow.on {
        if schedule.should_run_at(now)? {
            info!("⏰ Triggering scheduled execution of: {}", workflow_name);

            // Execute workflow in background
            let workflow_clone = workflow.clone();
            let workflow_name_clone = workflow_name.to_string();

            tokio::spawn(async move {
                let params = HashMap::new();
                match workflow_clone.execute(params, None, None, None, None).await {
                    Ok(result) => {
                        if result.status.is_success() {
                            info!("✅ Scheduled workflow completed: {}", workflow_name_clone);
                        } else {
                            error!("❌ Scheduled workflow failed: {}", workflow_name_clone);
                        }
                    }
                    Err(e) => {
                        error!("❌ Scheduled workflow error: {}: {}", workflow_name_clone, e);
                    }
                }
            });

            return Ok(true);
        }
    }

    Ok(false)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cli_parsing() {
        let cli = Cli::try_parse_from(&[
            "workflow-cli",
            "run",
            "test-workflow",
            "--params", r#"{"key": "value"}"#,
            "--timeout", "300",
        ]).unwrap();

        match cli.command {
            Commands::Run { workflow, params, timeout, .. } => {
                assert_eq!(workflow, "test-workflow");
                assert_eq!(params, Some(r#"{"key": "value"}"#.to_string()));
                assert_eq!(timeout, 300);
            }
            _ => panic!("Wrong command parsed"),
        }
    }
}
