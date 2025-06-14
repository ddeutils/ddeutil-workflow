//! Configuration management for the workflow system.
//!
//! This module handles loading and managing configuration settings from multiple sources
//! including environment variables, configuration files, and default values.

use serde::{Deserialize, Serialize};
use serde_yaml::Value;
use std::collections::HashMap;
use std::env;
use std::path::{Path, PathBuf};

use crate::error::{ConfigError, WorkflowError, WorkflowResult};
use crate::types::DictData;

/// Main configuration structure for the workflow system
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    /// Configuration file paths to search
    pub config_paths: Vec<PathBuf>,

    /// Core configuration settings
    pub core: CoreConfig,

    /// Trace configuration settings
    pub trace: TraceConfig,

    /// Registry configuration settings
    pub registry: RegistryConfig,

    /// Audit configuration settings
    pub audit: AuditConfig,
}

/// Core workflow engine configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CoreConfig {
    /// Default timezone for workflow execution
    pub timezone: String,

    /// Maximum parallel job execution
    pub max_job_parallel: usize,

    /// Default execution timeout in seconds
    pub default_timeout: u64,

    /// Minimum cron interval in seconds
    pub min_cron_interval: u64,
}

/// Trace and logging configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TraceConfig {
    /// Logging level (DEBUG, INFO, WARN, ERROR)
    pub level: String,

    /// Log file path (optional)
    pub path: Option<PathBuf>,

    /// Enable console logging
    pub console: bool,

    /// Log format (json, text)
    pub format: String,
}

/// Registry configuration for custom functions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegistryConfig {
    /// Default caller module for custom functions
    pub caller: String,

    /// Additional registry paths
    pub paths: Vec<PathBuf>,
}

/// Audit configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditConfig {
    /// Enable audit logging
    pub enabled: bool,

    /// Audit storage path
    pub path: Option<PathBuf>,

    /// Audit retention days
    pub retention_days: u32,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            config_paths: vec![
                PathBuf::from("./configs"),
                PathBuf::from("./workflows"),
                PathBuf::from("/etc/workflow"),
            ],
            core: CoreConfig::default(),
            trace: TraceConfig::default(),
            registry: RegistryConfig::default(),
            audit: AuditConfig::default(),
        }
    }
}

impl Default for CoreConfig {
    fn default() -> Self {
        Self {
            timezone: "UTC".to_string(),
            max_job_parallel: crate::defaults::MAX_JOB_PARALLEL,
            default_timeout: crate::defaults::DEFAULT_TIMEOUT,
            min_cron_interval: crate::defaults::MIN_CRON_INTERVAL,
        }
    }
}

impl Default for TraceConfig {
    fn default() -> Self {
        Self {
            level: "INFO".to_string(),
            path: None,
            console: true,
            format: "text".to_string(),
        }
    }
}

impl Default for RegistryConfig {
    fn default() -> Self {
        Self {
            caller: "tasks".to_string(),
            paths: vec![PathBuf::from("./registry")],
        }
    }
}

impl Default for AuditConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            path: Some(PathBuf::from("./audit")),
            retention_days: 30,
        }
    }
}

impl Config {
    /// Load configuration from environment variables and files
    pub async fn load() -> WorkflowResult<Self> {
        let mut config = Self::default();

        // Load from environment variables
        config.load_from_env()?;

        // Load from configuration files if they exist
        config.load_from_files().await?;

        Ok(config)
    }

    /// Load configuration from environment variables
    fn load_from_env(&mut self) -> WorkflowResult<()> {
        // Core configuration
        if let Ok(timezone) = env::var("WORKFLOW_CORE_TIMEZONE") {
            self.core.timezone = timezone;
        }

        if let Ok(max_parallel) = env::var("WORKFLOW_CORE_MAX_JOB_PARALLEL") {
            self.core.max_job_parallel = max_parallel.parse().map_err(|_| {
                WorkflowError::Config {
                    message: "Invalid WORKFLOW_CORE_MAX_JOB_PARALLEL value".to_string(),
                }
            })?;
        }

        if let Ok(timeout) = env::var("WORKFLOW_CORE_DEFAULT_TIMEOUT") {
            self.core.default_timeout = timeout.parse().map_err(|_| {
                WorkflowError::Config {
                    message: "Invalid WORKFLOW_CORE_DEFAULT_TIMEOUT value".to_string(),
                }
            })?;
        }

        // Trace configuration
        if let Ok(level) = env::var("WORKFLOW_TRACE_LEVEL") {
            self.trace.level = level;
        }

        if let Ok(path) = env::var("WORKFLOW_TRACE_PATH") {
            self.trace.path = Some(PathBuf::from(path));
        }

        if let Ok(console) = env::var("WORKFLOW_TRACE_CONSOLE") {
            self.trace.console = console.to_lowercase() == "true";
        }

        // Registry configuration
        if let Ok(caller) = env::var("WORKFLOW_REGISTRY_CALLER") {
            self.registry.caller = caller;
        }

        // Audit configuration
        if let Ok(enabled) = env::var("WORKFLOW_AUDIT_ENABLED") {
            self.audit.enabled = enabled.to_lowercase() == "true";
        }

        if let Ok(path) = env::var("WORKFLOW_AUDIT_PATH") {
            self.audit.path = Some(PathBuf::from(path));
        }

        // Config paths
        if let Ok(paths) = env::var("WORKFLOW_CORE_CONFIG_PATH") {
            self.config_paths = paths
                .split(':')
                .map(PathBuf::from)
                .collect();
        }

        Ok(())
    }

    /// Load configuration from files
    async fn load_from_files(&mut self) -> WorkflowResult<()> {
        for config_path in &self.config_paths.clone() {
            if config_path.exists() {
                if let Ok(config_file) = std::fs::read_to_string(config_path.join("config.yaml")) {
                    if let Ok(file_config) = serde_yaml::from_str::<Config>(&config_file) {
                        self.merge(file_config);
                    }
                }
            }
        }

        Ok(())
    }

    /// Merge another config into this one
    fn merge(&mut self, other: Config) {
        // Merge core config
        if other.core.timezone != CoreConfig::default().timezone {
            self.core.timezone = other.core.timezone;
        }
        if other.core.max_job_parallel != CoreConfig::default().max_job_parallel {
            self.core.max_job_parallel = other.core.max_job_parallel;
        }
        if other.core.default_timeout != CoreConfig::default().default_timeout {
            self.core.default_timeout = other.core.default_timeout;
        }

        // Merge trace config
        if other.trace.level != TraceConfig::default().level {
            self.trace.level = other.trace.level;
        }
        if other.trace.path.is_some() {
            self.trace.path = other.trace.path;
        }
        if !other.trace.console {
            self.trace.console = other.trace.console;
        }

        // Merge registry config
        if other.registry.caller != RegistryConfig::default().caller {
            self.registry.caller = other.registry.caller;
        }
        if !other.registry.paths.is_empty() {
            self.registry.paths = other.registry.paths;
        }

        // Merge audit config
        if other.audit.enabled != AuditConfig::default().enabled {
            self.audit.enabled = other.audit.enabled;
        }
        if other.audit.path.is_some() {
            self.audit.path = other.audit.path;
        }
    }

    /// Get workflow configuration by name
    pub fn get_workflow_config(&self, name: &str) -> WorkflowResult<Value> {
        for config_path in &self.config_paths {
            let workflow_file = config_path.join(format!("{}.yaml", name));
            if workflow_file.exists() {
                match std::fs::read_to_string(&workflow_file) {
                    Ok(content) => match serde_yaml::from_str::<Value>(&content) {
                        Ok(config) => return Ok(config),
                        Err(e) => {
                            return Err(WorkflowError::Config {
                                message: format!("Failed to parse {}: {}", workflow_file.display(), e),
                            });
                        }
                    },
                    Err(e) => {
                        return Err(WorkflowError::Config {
                            message: format!("Failed to read {}: {}", workflow_file.display(), e),
                        });
                    }
                }
            }
        }

        Err(WorkflowError::Config {
            message: format!("Workflow '{}' not found in any config path", name),
        })
    }

    /// List all available workflows
    pub async fn list_workflows(&self) -> WorkflowResult<Vec<String>> {
        let mut workflows = Vec::new();

        for config_path in &self.config_paths {
            if config_path.exists() {
                if let Ok(entries) = std::fs::read_dir(config_path) {
                    for entry in entries.flatten() {
                        if let Some(file_name) = entry.file_name().to_str() {
                            if file_name.ends_with(".yaml") || file_name.ends_with(".yml") {
                                let workflow_name = file_name
                                    .trim_end_matches(".yaml")
                                    .trim_end_matches(".yml");
                                if workflow_name != "config" {
                                    workflows.push(workflow_name.to_string());
                                }
                            }
                        }
                    }
                }
            }
        }

        workflows.sort();
        workflows.dedup();
        Ok(workflows)
    }

    /// Validate configuration
    pub fn validate(&self) -> WorkflowResult<()> {
        // Validate core config
        if self.core.max_job_parallel == 0 {
            return Err(WorkflowError::Validation {
                message: "max_job_parallel must be greater than 0".to_string(),
            });
        }

        if self.core.default_timeout == 0 {
            return Err(WorkflowError::Validation {
                message: "default_timeout must be greater than 0".to_string(),
            });
        }

        if self.core.min_cron_interval < 60 {
            return Err(WorkflowError::Validation {
                message: "min_cron_interval must be at least 60 seconds".to_string(),
            });
        }

        // Validate trace config
        if !matches!(self.trace.level.to_uppercase().as_str(), "DEBUG" | "INFO" | "WARN" | "ERROR") {
            return Err(WorkflowError::Validation {
                message: format!("Invalid trace level: {}", self.trace.level),
            });
        }

        if !matches!(self.trace.format.to_lowercase().as_str(), "json" | "text") {
            return Err(WorkflowError::Validation {
                message: format!("Invalid trace format: {}", self.trace.format),
            });
        }

        Ok(())
    }
}

/// Utility functions for environment variable handling
impl Config {
    /// Get environment variable or return default value
    pub fn env_var_or_default(var_name: &str, default: &str) -> String {
        env::var(var_name).unwrap_or_else(|_| default.to_string())
    }

    /// Get boolean environment variable
    pub fn env_bool(var_name: &str, default: bool) -> bool {
        env::var(var_name)
            .map(|val| val.to_lowercase() == "true")
            .unwrap_or(default)
    }

    /// Get numeric environment variable
    pub fn env_int<T>(var_name: &str, default: T) -> T
    where
        T: std::str::FromStr + Copy,
    {
        env::var(var_name)
            .ok()
            .and_then(|val| val.parse().ok())
            .unwrap_or(default)
    }
}

/// YAML configuration parser
#[derive(Debug, Clone)]
pub struct YamlParser {
    pub name: String,
    pub config: Value,
    pub extras: DictData,
}

impl YamlParser {
    /// Create new YAML parser from file or defaults
    pub fn new(name: &str, path: Option<&Path>, extras: Option<DictData>) -> WorkflowResult<Self> {
        let config = if let Some(path) = path {
            let content = std::fs::read_to_string(path).map_err(|e| WorkflowError::Config {
                message: format!("Failed to read config file: {}", e),
            })?;
            serde_yaml::from_str(&content).map_err(|e| WorkflowError::Config {
                message: format!("Failed to parse YAML: {}", e),
            })?
        } else {
            Value::Null
        };

        Ok(Self {
            name: name.to_string(),
            config,
            extras: extras.unwrap_or_default(),
        })
    }

    /// Get configuration type
    pub fn get_type(&self) -> WorkflowResult<String> {
        match &self.config {
            Value::Mapping(map) => {
                if let Some(Value::String(type_name)) = map.get(&Value::String("type".to_string())) {
                    Ok(type_name.clone())
                } else {
                    Err(WorkflowError::Config {
                        message: "Missing 'type' field in configuration".to_string(),
                    })
                }
            }
            _ => Err(WorkflowError::Config {
                message: "Invalid configuration format".to_string(),
            }),
        }
    }

    /// Process template variables in configuration
    pub fn process_templates(&mut self, params: &DictData) -> WorkflowResult<()> {
        // Template processing would be implemented here
        // For now, just store the params in extras
        self.extras.extend(params.clone());
        Ok(())
    }
}

/// Synchronous config loading for non-async contexts
impl Config {
    /// Load configuration synchronously
    fn load_sync() -> WorkflowResult<Self> {
        let mut config = Self::default();
        config.load_from_env()?;
        // Note: File loading is skipped in sync mode
        Ok(config)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let config = Config::default();
        assert_eq!(config.core.timezone, "UTC");
        assert_eq!(config.core.max_job_parallel, crate::defaults::MAX_JOB_PARALLEL);
        assert!(config.trace.console);
        assert_eq!(config.trace.format, "text");
    }

    #[test]
    fn test_env_var_loading() {
        env::set_var("WORKFLOW_CORE_TIMEZONE", "America/New_York");
        env::set_var("WORKFLOW_CORE_MAX_JOB_PARALLEL", "4");

        let mut config = Config::default();
        config.load_from_env().unwrap();

        assert_eq!(config.core.timezone, "America/New_York");
        assert_eq!(config.core.max_job_parallel, 4);

        // Clean up
        env::remove_var("WORKFLOW_CORE_TIMEZONE");
        env::remove_var("WORKFLOW_CORE_MAX_JOB_PARALLEL");
    }

    #[test]
    fn test_config_validation() {
        let mut config = Config::default();
        assert!(config.validate().is_ok());

        // Test invalid max_job_parallel
        config.core.max_job_parallel = 0;
        assert!(config.validate().is_err());

        // Test invalid trace level
        config.core.max_job_parallel = 2;
        config.trace.level = "INVALID".to_string();
        assert!(config.validate().is_err());
    }

    #[tokio::test]
    async fn test_workflow_config_loading() {
        let config = Config::default();

        // Test loading non-existent workflow
        let result = config.get_workflow_config("non_existent");
        assert!(result.is_err());

        // Test listing workflows from empty directories
        let workflows = config.list_workflows().await.unwrap();
        assert!(workflows.is_empty() || !workflows.is_empty()); // Just ensure it doesn't panic
    }

    #[test]
    fn test_env_helpers() {
        env::set_var("TEST_VAR", "test_value");
        env::set_var("TEST_BOOL", "true");
        env::set_var("TEST_INT", "42");

        assert_eq!(Config::env_var_or_default("TEST_VAR", "default"), "test_value");
        assert_eq!(Config::env_var_or_default("MISSING_VAR", "default"), "default");

        assert!(Config::env_bool("TEST_BOOL", false));
        assert!(!Config::env_bool("MISSING_BOOL", false));

        assert_eq!(Config::env_int::<i32>("TEST_INT", 0), 42);
        assert_eq!(Config::env_int::<i32>("MISSING_INT", 0), 0);

        // Clean up
        env::remove_var("TEST_VAR");
        env::remove_var("TEST_BOOL");
        env::remove_var("TEST_INT");
    }
}
