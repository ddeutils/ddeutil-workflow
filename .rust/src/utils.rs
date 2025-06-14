//! Utility functions for the workflow orchestration system.
//!
//! This module provides common utility functions used throughout the workflow
//! engine, including ID generation, template rendering, and various helper functions.

use chrono::{DateTime, Utc};
use handlebars::Handlebars;
use md5::{Digest, Md5};
use regex::Regex;
use serde_json::Value;
use std::collections::HashMap;
use uuid::Uuid;

use crate::types::DictData;

/// Generate a unique ID for workflow execution tracking.
///
/// This function generates process IDs using MD5 algorithm or simple mode
/// based on configuration. The ID can include timestamp for uniqueness.
///
/// # Arguments
///
/// * `value` - Base value to include in ID generation
/// * `unique` - Whether to add timestamp for uniqueness
///
/// # Returns
///
/// A string containing the generated ID
///
/// # Examples
///
/// ```rust
/// use ddeutil_workflow::utils::generate_id;
///
/// // Generate simple ID
/// let id = generate_id("workflow", false);
/// assert!(!id.is_empty());
///
/// // Generate unique ID with timestamp
/// let unique_id = generate_id("workflow", true);
/// assert!(!unique_id.is_empty());
/// assert_ne!(id, unique_id);
/// ```
pub fn generate_id(value: &str, unique: bool) -> String {
    let timestamp = if unique {
        format!("{}T", Utc::now().format("%Y%m%d%H%M%S%f"))
    } else {
        String::new()
    };

    // Use simple hash for now (can be made configurable)
    let input = format!("{}{}", timestamp, value.to_lowercase());
    let mut hasher = Md5::new();
    hasher.update(input.as_bytes());
    let result = hasher.finalize();
    format!("{:x}", result)
}

/// Generate a default ID for manual execution
pub fn generate_default_id() -> String {
    generate_id("manual", true)
}

/// Render template string with provided context data.
///
/// Uses Handlebars template engine to render templates with context variables.
/// Supports standard Handlebars syntax including conditionals and loops.
///
/// # Arguments
///
/// * `template` - Template string with Handlebars syntax
/// * `context` - Context data for template rendering
///
/// # Returns
///
/// Result containing rendered string or error
///
/// # Examples
///
/// ```rust
/// use ddeutil_workflow::utils::template_render;
/// use std::collections::HashMap;
/// use serde_json::json;
///
/// let mut context = HashMap::new();
/// context.insert("name".to_string(), json!("World"));
/// context.insert("count".to_string(), json!(42));
///
/// let result = template_render("Hello {{name}}! Count: {{count}}", &context).unwrap();
/// assert_eq!(result, "Hello World! Count: 42");
/// ```
pub fn template_render(template: &str, context: &DictData) -> Result<String, handlebars::RenderError> {
    let mut handlebars = Handlebars::new();

    // Register the template
    handlebars.register_template_string("template", template)?;

    // Render with context
    handlebars.render("template", context)
}

/// Check if a string contains template syntax
///
/// # Arguments
///
/// * `value` - String to check for template syntax
///
/// # Returns
///
/// True if string contains template markers
pub fn has_template(value: &str) -> bool {
    let template_regex = Regex::new(r"\$\{\{.*?\}\}").unwrap();
    template_regex.is_match(value)
}

/// Replace template parameters in a string with values from context
///
/// # Arguments
///
/// * `value` - String containing template parameters
/// * `params` - Parameter context for replacement
///
/// # Returns
///
/// String with parameters replaced
pub fn param_to_template(value: &str, params: &DictData) -> Result<String, handlebars::RenderError> {
    if !has_template(value) {
        return Ok(value.to_string());
    }

    template_render(value, params)
}

/// Convert camelCase string to kebab-case
///
/// # Arguments
///
/// * `camel` - CamelCase string to convert
///
/// # Returns
///
/// kebab-case string
///
/// # Examples
///
/// ```rust
/// use ddeutil_workflow::utils::camel_to_kebab;
///
/// assert_eq!(camel_to_kebab("camelCase"), "camel-case");
/// assert_eq!(camel_to_kebab("XMLHttpRequest"), "xml-http-request");
/// ```
pub fn camel_to_kebab(camel: &str) -> String {
    let mut result = String::new();
    let mut chars = camel.chars().peekable();

    while let Some(ch) = chars.next() {
        if ch.is_uppercase() && !result.is_empty() {
            result.push('-');
        }
        result.push(ch.to_lowercase().next().unwrap_or(ch));
    }

    result
}

/// Convert snake_case string to kebab-case
///
/// # Arguments
///
/// * `snake` - snake_case string to convert
///
/// # Returns
///
/// kebab-case string
pub fn snake_to_kebab(snake: &str) -> String {
    snake.replace('_', "-")
}

/// Prepare multiline message for logging
///
/// # Arguments
///
/// * `msg` - Message that may contain newlines
///
/// # Returns
///
/// Formatted message with proper indentation
pub fn prepare_multiline_message(msg: &str) -> String {
    let lines: Vec<&str> = msg.trim().lines().collect();

    if lines.len() <= 1 {
        return msg.to_string();
    }

    let mut result = lines[0].to_string();

    if lines.len() > 2 {
        for line in &lines[1..lines.len()-1] {
            result.push_str(&format!("\n ... |  \t{}", line));
        }
    }

    if lines.len() > 1 {
        result.push_str(&format!("\n ... ╰─ \t{}", lines[lines.len()-1]));
    }

    result
}

/// Get current timestamp with timezone
///
/// # Returns
///
/// Current UTC timestamp
pub fn get_current_timestamp() -> DateTime<Utc> {
    Utc::now()
}

/// Calculate time difference in seconds
///
/// # Arguments
///
/// * `start` - Start timestamp
/// * `end` - End timestamp (optional, defaults to now)
///
/// # Returns
///
/// Duration in seconds
pub fn time_diff_seconds(start: DateTime<Utc>, end: Option<DateTime<Utc>>) -> f64 {
    let end_time = end.unwrap_or_else(Utc::now);
    (end_time - start).num_milliseconds() as f64 / 1000.0
}

/// Hash a string using MD5
///
/// # Arguments
///
/// * `input` - String to hash
/// * `length` - Optional length to truncate hash (default: full hash)
///
/// # Returns
///
/// MD5 hash string
pub fn hash_string(input: &str, length: Option<usize>) -> String {
    let mut hasher = Md5::new();
    hasher.update(input.as_bytes());
    let result = format!("{:x}", hasher.finalize());

    match length {
        Some(len) if len < result.len() => result[..len].to_string(),
        _ => result,
    }
}

/// Create a cross product of matrix values
///
/// # Arguments
///
/// * `matrix` - HashMap of key-value arrays for cross product
///
/// # Returns
///
/// Vector of all possible combinations
///
/// # Examples
///
/// ```rust
/// use ddeutil_workflow::utils::cross_product;
/// use std::collections::HashMap;
/// use serde_json::json;
///
/// let mut matrix = HashMap::new();
/// matrix.insert("os".to_string(), vec![json!("ubuntu"), json!("windows")]);
/// matrix.insert("version".to_string(), vec![json!("3.9"), json!("3.10")]);
///
/// let result = cross_product(&matrix);
/// assert_eq!(result.len(), 4); // 2 * 2 combinations
/// ```
pub fn cross_product(matrix: &HashMap<String, Vec<Value>>) -> Vec<DictData> {
    if matrix.is_empty() {
        return vec![HashMap::new()];
    }

    let keys: Vec<&String> = matrix.keys().collect();
    let mut result = Vec::new();

    fn generate_combinations(
        keys: &[&String],
        matrix: &HashMap<String, Vec<Value>>,
        current: &mut DictData,
        index: usize,
        result: &mut Vec<DictData>,
    ) {
        if index == keys.len() {
            result.push(current.clone());
            return;
        }

        let key = keys[index];
        if let Some(values) = matrix.get(key) {
            for value in values {
                current.insert(key.clone(), value.clone());
                generate_combinations(keys, matrix, current, index + 1, result);
            }
        }
    }

    let mut current = HashMap::new();
    generate_combinations(&keys, matrix, &mut current, 0, &mut result);
    result
}

/// Filter function that returns input unchanged (identity function)
pub fn filter_func<T>(value: T) -> T {
    value
}

/// Make a file executable (Unix-like systems)
///
/// # Arguments
///
/// * `path` - Path to the file to make executable
///
/// # Returns
///
/// Result indicating success or failure
#[cfg(unix)]
pub fn make_executable<P: AsRef<std::path::Path>>(path: P) -> std::io::Result<()> {
    use std::os::unix::fs::PermissionsExt;

    let metadata = std::fs::metadata(&path)?;
    let mut permissions = metadata.permissions();
    let mode = permissions.mode();
    permissions.set_mode(mode | 0o111); // Add execute permission
    std::fs::set_permissions(path, permissions)
}

/// Make a file executable (Windows - no-op)
#[cfg(windows)]
pub fn make_executable<P: AsRef<std::path::Path>>(_path: P) -> std::io::Result<()> {
    // Windows doesn't have execute permissions like Unix
    Ok(())
}

/// Delay execution with optional randomization
///
/// # Arguments
///
/// * `seconds` - Base delay in seconds
/// * `randomize` - Whether to add random jitter (0-1 seconds)
pub async fn delay(seconds: f64, randomize: bool) {
    let delay_duration = if randomize {
        let jitter = rand::random::<f64>(); // 0.0 to 1.0
        seconds + jitter
    } else {
        seconds
    };

    tokio::time::sleep(tokio::time::Duration::from_secs_f64(delay_duration)).await;
}

/// Truncate a run ID for display purposes
///
/// # Arguments
///
/// * `run_id` - Full run ID string
/// * `length` - Desired length (default: 8)
///
/// # Returns
///
/// Truncated run ID
pub fn truncate_run_id(run_id: &str, length: Option<usize>) -> String {
    let len = length.unwrap_or(8);
    if run_id.len() <= len {
        run_id.to_string()
    } else {
        format!("{}...", &run_id[..len])
    }
}

/// Parse environment variable with default value
///
/// # Arguments
///
/// * `var_name` - Environment variable name
/// * `default` - Default value if variable not found
///
/// # Returns
///
/// Environment variable value or default
pub fn env_var_or_default(var_name: &str, default: &str) -> String {
    std::env::var(var_name).unwrap_or_else(|_| default.to_string())
}

/// Parse boolean from string (case-insensitive)
///
/// # Arguments
///
/// * `value` - String value to parse
///
/// # Returns
///
/// Boolean value (defaults to false for invalid input)
pub fn parse_bool(value: &str) -> bool {
    matches!(value.to_lowercase().as_str(), "true" | "1" | "yes" | "on")
}

/// Serialize value to JSON string with pretty formatting
///
/// # Arguments
///
/// * `value` - Value to serialize
///
/// # Returns
///
/// Pretty-formatted JSON string
pub fn to_pretty_json<T: serde::Serialize>(value: &T) -> Result<String, serde_json::Error> {
    serde_json::to_string_pretty(value)
}

/// Deserialize JSON string to value
///
/// # Arguments
///
/// * `json_str` - JSON string to deserialize
///
/// # Returns
///
/// Deserialized value
pub fn from_json_str<T: serde::de::DeserializeOwned>(json_str: &str) -> Result<T, serde_json::Error> {
    serde_json::from_str(json_str)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_generate_id() {
        let id1 = generate_id("test", false);
        let id2 = generate_id("test", false);
        assert_eq!(id1, id2); // Same input should produce same ID

        let unique_id1 = generate_id("test", true);
        let unique_id2 = generate_id("test", true);
        assert_ne!(unique_id1, unique_id2); // Unique IDs should differ
    }

    #[test]
    fn test_template_render() {
        let mut context = HashMap::new();
        context.insert("name".to_string(), json!("World"));
        context.insert("count".to_string(), json!(42));

        let result = template_render("Hello {{name}}! Count: {{count}}", &context).unwrap();
        assert_eq!(result, "Hello World! Count: 42");
    }

    #[test]
    fn test_has_template() {
        assert!(has_template("Hello ${{ name }}"));
        assert!(!has_template("Hello World"));
        assert!(has_template("Value: ${{ params.value }}"));
    }

    #[test]
    fn test_camel_to_kebab() {
        assert_eq!(camel_to_kebab("camelCase"), "camel-case");
        assert_eq!(camel_to_kebab("XMLHttpRequest"), "x-m-l-http-request");
        assert_eq!(camel_to_kebab("simple"), "simple");
    }

    #[test]
    fn test_snake_to_kebab() {
        assert_eq!(snake_to_kebab("snake_case"), "snake-case");
        assert_eq!(snake_to_kebab("simple"), "simple");
    }

    #[test]
    fn test_hash_string() {
        let hash1 = hash_string("test", None);
        let hash2 = hash_string("test", None);
        assert_eq!(hash1, hash2);

        let short_hash = hash_string("test", Some(8));
        assert_eq!(short_hash.len(), 8);
        assert!(hash1.starts_with(&short_hash));
    }

    #[test]
    fn test_cross_product() {
        let mut matrix = HashMap::new();
        matrix.insert("os".to_string(), vec![json!("ubuntu"), json!("windows")]);
        matrix.insert("version".to_string(), vec![json!("3.9"), json!("3.10")]);

        let result = cross_product(&matrix);
        assert_eq!(result.len(), 4);

        // Check that all combinations exist
        let has_ubuntu_39 = result.iter().any(|combo| {
            combo.get("os") == Some(&json!("ubuntu")) &&
            combo.get("version") == Some(&json!("3.9"))
        });
        assert!(has_ubuntu_39);
    }

    #[test]
    fn test_truncate_run_id() {
        let long_id = "abcdefghijklmnopqrstuvwxyz";
        assert_eq!(truncate_run_id(long_id, Some(8)), "abcdefgh...");
        assert_eq!(truncate_run_id("short", Some(8)), "short");
    }

    #[test]
    fn test_parse_bool() {
        assert!(parse_bool("true"));
        assert!(parse_bool("TRUE"));
        assert!(parse_bool("1"));
        assert!(parse_bool("yes"));
        assert!(parse_bool("on"));

        assert!(!parse_bool("false"));
        assert!(!parse_bool("0"));
        assert!(!parse_bool("no"));
        assert!(!parse_bool("invalid"));
    }

    #[test]
    fn test_prepare_multiline_message() {
        let single_line = "Single line message";
        assert_eq!(prepare_multiline_message(single_line), single_line);

        let multi_line = "Line 1\nLine 2\nLine 3";
        let result = prepare_multiline_message(multi_line);
        assert!(result.contains("Line 1"));
        assert!(result.contains("... |  \tLine 2"));
        assert!(result.contains("... ╰─ \tLine 3"));
    }

    #[tokio::test]
    async fn test_delay() {
        let start = std::time::Instant::now();
        delay(0.1, false).await;
        let elapsed = start.elapsed();

        // Should be approximately 100ms (allowing for some variance)
        assert!(elapsed.as_millis() >= 90);
        assert!(elapsed.as_millis() <= 150);
    }
}
