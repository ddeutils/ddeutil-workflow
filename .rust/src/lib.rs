//! # DDE Workflow - Lightweight Workflow Orchestration
//!
//! This crate provides a comprehensive workflow orchestration system with YAML template
//! support. It enables developers to create, manage, and execute complex workflows with
//! minimal configuration.
//!
//! ## Key Features
//!
//! - **YAML-based workflow configuration** - Define workflows using intuitive YAML syntax
//! - **Job and stage execution management** - Hierarchical execution with jobs containing stages
//! - **Scheduling with cron-like syntax** - Built-in scheduler supporting cron expressions
//! - **Parallel and sequential execution** - Multi-threading support for concurrent execution
//! - **Comprehensive error handling** - Robust error management with detailed tracing
//! - **Extensible stage types** - Support for Bash, Python, Docker, and custom stages
//! - **Matrix strategy** - Parameterized workflows with cross-product execution
//! - **Audit and tracing** - Complete execution tracking and logging
//!
//! ## Quick Start
//!
//! ```rust
//! use ddeutil_workflow::{Workflow, Result};
//!
//! #[tokio::main]
//! async fn main() -> anyhow::Result<()> {
//!     // Load workflow from configuration
//!     let workflow = Workflow::from_config("my-workflow").await?;
//!
//!     // Execute with parameters
//!     let params = serde_json::json!({
//!         "param1": "value1",
//!         "param2": "value2"
//!     });
//!
//!     let result = workflow.execute(params).await?;
//!
//!     if result.status.is_success() {
//!         println!("Workflow completed successfully");
//!     }
//!
//!     Ok(())
//! }
//! ```
//!
//! ## Architecture
//!
//! The workflow system is built around several core concepts:
//!
//! - **Workflow**: Top-level orchestration container
//! - **Job**: Execution unit containing multiple stages
//! - **Stage**: Individual task execution (Bash, Python, Docker, etc.)
//! - **Result**: Execution status and output management
//! - **Event**: Scheduling and trigger management
//! - **Audit**: Execution tracking and logging
//!
//! ## Configuration
//!
//! Workflows are defined using YAML configuration files:
//!
//! ```yaml
//! type: Workflow
//! name: data-processing
//! on:
//!   - cronjob: '0 */6 * * *'
//!     timezone: "UTC"
//! params:
//!   source: str
//!   target: str
//! jobs:
//!   extract-data:
//!     runs-on:
//!       type: local
//!     stages:
//!       - name: "Extract Data"
//!         uses: "tasks/extract@v1"
//!         with:
//!           source: ${{ params.source }}
//!           target: ${{ params.target }}
//! ```

// Core modules
pub mod config;
pub mod defaults;
pub mod error;
pub mod result;
pub mod types;

// Workflow components
pub mod job;
pub mod stage;
pub mod workflow;

// Utility modules
pub mod utils;

// Feature modules
pub mod audit;
pub mod cron;
pub mod event;
pub mod params;
pub mod registry;
pub mod trace;

// Re-exports for convenience
pub use audit::{Audit, AuditModel, FileAudit};
pub use config::Config;
pub use cron::{CronJob, CronRunner};
pub use error::{WorkflowError, JobError, StageError};
pub use event::{Event, Crontab, EventManager};
pub use job::{Job, Strategy, Rule, RunsOn};
pub use params::{Param, ParamType};
pub use registry::{Registry, TaggedFunction};
pub use result::{Result, Status};
pub use stage::{Stage, BaseStage, EmptyStage, BashStage, PyStage, CallStage};
pub use trace::{Trace, TraceModel, ConsoleTrace, FileTrace};
pub use utils::{generate_id, template_render};
pub use workflow::{Workflow, ReleaseType};

// Re-export common types
pub use types::{DictData, Matrix, StrOrNone};

/// Current version of the workflow engine
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Default configuration values
pub mod defaults {
    /// Maximum number of jobs to run in parallel
    pub const MAX_JOB_PARALLEL: usize = 2;

    /// Maximum number of stages to run in parallel within a job
    pub const MAX_STAGE_PARALLEL: usize = 4;

    /// Default timeout for operations (1 hour in seconds)
    pub const DEFAULT_TIMEOUT: u64 = 3600;

    /// Minimum interval between cron jobs (1 minute in seconds)
    pub const MIN_CRON_INTERVAL: u64 = 60;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_version() {
        assert!(!VERSION.is_empty());
    }

    #[test]
    fn test_defaults() {
        assert!(defaults::MAX_JOB_PARALLEL > 0);
        assert!(defaults::MAX_STAGE_PARALLEL > 0);
        assert!(defaults::DEFAULT_TIMEOUT > 0);
        assert!(defaults::MIN_CRON_INTERVAL > 0);
    }
}
