//! Common type definitions for the workflow system.
//!
//! This module provides type aliases, utility structures, and helper functions
//! used throughout the workflow orchestration system.

use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;

/// Dictionary data type for flexible key-value storage
pub type DictData = HashMap<String, Value>;

/// Matrix type for strategy configurations
pub type Matrix = HashMap<String, Vec<Value>>;

/// String or None type alias for optional strings
pub type StrOrNone = Option<String>;

/// Regex pattern wrapper with compiled regex caching
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Re {
    /// Regex pattern string
    pub pattern: String,

    /// Compiled regex (not serialized)
    #[serde(skip)]
    pub regex: Option<Regex>,
}

impl Re {
    /// Create new regex pattern
    pub fn new(pattern: &str) -> Result<Self, regex::Error> {
        let regex = Regex::new(pattern)?;
        Ok(Self {
            pattern: pattern.to_string(),
            regex: Some(regex),
        })
    }

    /// Check if text matches the pattern
    pub fn is_match(&self, text: &str) -> bool {
        self.regex.as_ref().map_or(false, |r| r.is_match(text))
    }

    /// Replace all matches with replacement text
    pub fn replace_all(&self, text: &str, replacement: &str) -> String {
        if let Some(regex) = &self.regex {
            regex.replace_all(text, replacement).to_string()
        } else {
            text.to_string()
        }
    }

    /// Find all matches in text
    pub fn find_all(&self, text: &str) -> Vec<String> {
        if let Some(regex) = &self.regex {
            regex.find_iter(text).map(|m| m.as_str().to_string()).collect()
        } else {
            Vec::new()
        }
    }

    /// Split text by regex pattern
    pub fn split(&self, text: &str) -> Vec<String> {
        if let Some(regex) = &self.regex {
            regex.split(text).map(|s| s.to_string()).collect()
        } else {
            vec![text.to_string()]
        }
    }
}

/// Caller regex pattern for function resolution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CallerRe {
    /// Regex pattern for matching caller names
    pub pattern: String,

    /// Compiled regex (not serialized)
    #[serde(skip)]
    pub regex: Option<Regex>,
}

impl CallerRe {
    /// Create new caller regex
    pub fn new(pattern: &str) -> Result<Self, regex::Error> {
        let regex = Regex::new(pattern)?;
        Ok(Self {
            pattern: pattern.to_string(),
            regex: Some(regex),
        })
    }

    /// Check if caller name matches the pattern
    pub fn is_match(&self, text: &str) -> bool {
        self.regex.as_ref().map_or(false, |r| r.is_match(text))
    }

    /// Find all caller matches in text
    pub fn find_matches(&self, text: &str) -> Vec<String> {
        if let Some(regex) = &self.regex {
            regex.find_iter(text).map(|m| m.as_str().to_string()).collect()
        } else {
            Vec::new()
        }
    }
}

/// Environment variable configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EnvVar {
    /// Variable name
    pub name: String,

    /// Variable value
    pub value: String,

    /// Whether to export the variable
    pub export: bool,
}

impl EnvVar {
    /// Create new environment variable
    pub fn new(name: String, value: String) -> Self {
        Self {
            name,
            value,
            export: true,
        }
    }

    /// Create from key-value pair
    pub fn from_pair(name: &str, value: &str) -> Self {
        Self::new(name.to_string(), value.to_string())
    }
}

/// Volume mount configuration for containers
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VolumeMount {
    /// Host path
    pub host_path: String,

    /// Container path
    pub container_path: String,

    /// Mount mode (ro, rw)
    pub mode: String,
}

impl VolumeMount {
    /// Create new volume mount
    pub fn new(host_path: String, container_path: String) -> Self {
        Self {
            host_path,
            container_path,
            mode: "rw".to_string(),
        }
    }

    /// Create read-only mount
    pub fn read_only(host_path: String, container_path: String) -> Self {
        Self {
            host_path,
            container_path,
            mode: "ro".to_string(),
        }
    }

    /// Format as Docker volume string
    pub fn to_docker_string(&self) -> String {
        format!("{}:{}:{}", self.host_path, self.container_path, self.mode)
    }
}

/// Network configuration for containers
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkConfig {
    /// Network name
    pub name: String,

    /// Network driver
    pub driver: String,

    /// Additional options
    pub options: DictData,
}

impl Default for NetworkConfig {
    fn default() -> Self {
        Self {
            name: "default".to_string(),
            driver: "bridge".to_string(),
            options: HashMap::new(),
        }
    }
}

/// Resource limits for execution contexts
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceLimits {
    /// CPU limit (cores)
    pub cpu: Option<f64>,

    /// Memory limit (bytes)
    pub memory: Option<u64>,

    /// Disk limit (bytes)
    pub disk: Option<u64>,

    /// Network bandwidth limit (bytes/sec)
    pub network: Option<u64>,
}

impl Default for ResourceLimits {
    fn default() -> Self {
        Self {
            cpu: None,
            memory: None,
            disk: None,
            network: None,
        }
    }
}

/// Execution context for stages and jobs
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionContext {
    /// Working directory
    pub working_dir: Option<String>,

    /// Environment variables
    pub env: HashMap<String, String>,

    /// Resource limits
    pub limits: ResourceLimits,

    /// Timeout in seconds
    pub timeout: Option<u64>,

    /// User to run as
    pub user: Option<String>,

    /// Group to run as
    pub group: Option<String>,
}

impl Default for ExecutionContext {
    fn default() -> Self {
        Self {
            working_dir: None,
            env: HashMap::new(),
            limits: ResourceLimits::default(),
            timeout: None,
            user: None,
            group: None,
        }
    }
}

/// File path with metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FilePath {
    /// Absolute path
    pub path: String,

    /// Whether path exists
    pub exists: bool,

    /// File permissions (Unix)
    pub permissions: Option<u32>,
}

impl FilePath {
    /// Create new file path
    pub fn new(path: String) -> Self {
        let exists = std::path::Path::new(&path).exists();
        Self {
            path,
            exists,
            permissions: None,
        }
    }

    /// Check if path is absolute
    pub fn is_absolute(&self) -> bool {
        std::path::Path::new(&self.path).is_absolute()
    }

    /// Get parent directory
    pub fn parent(&self) -> Option<String> {
        std::path::Path::new(&self.path)
            .parent()
            .map(|p| p.to_string_lossy().to_string())
    }

    /// Get file name
    pub fn file_name(&self) -> Option<String> {
        std::path::Path::new(&self.path)
            .file_name()
            .map(|name| name.to_string_lossy().to_string())
    }

    /// Get file extension
    pub fn extension(&self) -> Option<String> {
        std::path::Path::new(&self.path)
            .extension()
            .map(|ext| ext.to_string_lossy().to_string())
    }
}

/// Retry configuration for failed operations
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RetryConfig {
    /// Maximum number of retries
    pub max_attempts: u32,

    /// Delay between retries in seconds
    pub delay: f64,

    /// Backoff multiplier
    pub backoff: f64,

    /// Maximum delay in seconds
    pub max_delay: f64,

    /// Jitter factor (0.0 to 1.0)
    pub jitter: f64,
}

impl Default for RetryConfig {
    fn default() -> Self {
        Self {
            max_attempts: 3,
            delay: 1.0,
            backoff: 2.0,
            max_delay: 60.0,
            jitter: 0.1,
        }
    }
}

impl RetryConfig {
    /// Calculate delay for specific attempt with backoff and jitter
    pub fn calculate_delay(&self, attempt: u32) -> f64 {
        let base_delay = self.delay * self.backoff.powi(attempt as i32);
        let max_delay = self.max_delay.min(base_delay);

        // Add jitter
        let jitter_amount = max_delay * self.jitter;
        let jitter = (rand::random::<f64>() - 0.5) * 2.0 * jitter_amount;

        (max_delay + jitter).max(0.0)
    }
}

/// Health check configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthCheck {
    /// Command to run for health check
    pub command: Vec<String>,

    /// Interval between checks in seconds
    pub interval: f64,

    /// Timeout for each check in seconds
    pub timeout: f64,

    /// Number of retries before marking unhealthy
    pub retries: u32,

    /// Start period before health checks begin
    pub start_period: f64,
}

impl Default for HealthCheck {
    fn default() -> Self {
        Self {
            command: vec!["echo".to_string(), "healthy".to_string()],
            interval: 30.0,
            timeout: 10.0,
            retries: 3,
            start_period: 0.0,
        }
    }
}

/// Utility functions for type conversion
pub mod convert {
    use super::*;

    /// Convert Value to String
    pub fn value_to_string(value: &Value) -> String {
        match value {
            Value::String(s) => s.clone(),
            Value::Number(n) => n.to_string(),
            Value::Bool(b) => b.to_string(),
            _ => serde_json::to_string(value).unwrap_or_default(),
        }
    }

    /// Convert Value to bool
    pub fn value_to_bool(value: &Value) -> bool {
        match value {
            Value::Bool(b) => *b,
            Value::String(s) => s.to_lowercase() == "true",
            Value::Number(n) => n.as_f64().unwrap_or(0.0) != 0.0,
            _ => false,
        }
    }

    /// Convert Value to f64
    pub fn value_to_f64(value: &Value) -> Option<f64> {
        match value {
            Value::Number(n) => n.as_f64(),
            Value::String(s) => s.parse().ok(),
            _ => None,
        }
    }

    /// Convert Value to i64
    pub fn value_to_i64(value: &Value) -> Option<i64> {
        match value {
            Value::Number(n) => n.as_i64(),
            Value::String(s) => s.parse().ok(),
            _ => None,
        }
    }

    /// Convert DictData to environment variables
    pub fn dict_to_env(dict: &DictData) -> HashMap<String, String> {
        dict.iter()
            .map(|(k, v)| (k.clone(), value_to_string(v)))
            .collect()
    }

    /// Convert environment variables to DictData
    pub fn env_to_dict(env: &HashMap<String, String>) -> DictData {
        env.iter()
            .map(|(k, v)| (k.clone(), Value::String(v.clone())))
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_re() {
        let re = Re::new(r"\d+").unwrap();
        assert!(re.is_match("123"));
        assert!(!re.is_match("abc"));

        let matches = re.find_all("123 abc 456");
        assert_eq!(matches, vec!["123", "456"]);
    }

    #[test]
    fn test_caller_re() {
        let caller_re = CallerRe::new(r"tasks/\w+").unwrap();
        assert!(caller_re.is_match("tasks/extract"));
        assert!(!caller_re.is_match("other/extract"));
    }

    #[test]
    fn test_volume_mount() {
        let mount = VolumeMount::new("/host".to_string(), "/container".to_string());
        assert_eq!(mount.to_docker_string(), "/host:/container:rw");

        let ro_mount = VolumeMount::read_only("/host".to_string(), "/container".to_string());
        assert_eq!(ro_mount.to_docker_string(), "/host:/container:ro");
    }

    #[test]
    fn test_file_path() {
        let file_path = FilePath::new("/tmp/test.txt".to_string());
        assert_eq!(file_path.file_name(), Some("test.txt".to_string()));
        assert_eq!(file_path.extension(), Some("txt".to_string()));
    }

    #[test]
    fn test_retry_config() {
        let config = RetryConfig::default();
        assert_eq!(config.max_attempts, 3);

        let delay1 = config.calculate_delay(0);
        let delay2 = config.calculate_delay(1);
        assert!(delay2 > delay1); // Should increase with backoff
    }

    #[test]
    fn test_convert_functions() {
        use convert::*;

        let value = Value::String("123".to_string());
        assert_eq!(value_to_string(&value), "123");
        assert_eq!(value_to_i64(&value), Some(123));

        let bool_value = Value::Bool(true);
        assert!(value_to_bool(&bool_value));

        let dict = {
            let mut map = DictData::new();
            map.insert("key".to_string(), Value::String("value".to_string()));
            map
        };
        let env = dict_to_env(&dict);
        assert_eq!(env.get("key"), Some(&"value".to_string()));
    }
}
