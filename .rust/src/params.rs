//! Parameter management module for workflow execution.
//!
//! This module provides functionality to define, validate, and manage
//! parameters that are passed to workflows, jobs, and stages.

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::str::FromStr;

use crate::error::{WorkflowError, WorkflowResult};
use crate::types::DictData;

/// Parameter type enumeration
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ParamType {
    /// String parameter
    String,
    /// Integer parameter
    Int,
    /// Float parameter
    Float,
    /// Boolean parameter
    Bool,
    /// Array parameter
    Array,
    /// Object parameter
    Object,
    /// Any type parameter
    Any,
}

impl std::fmt::Display for ParamType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ParamType::String => write!(f, "string"),
            ParamType::Int => write!(f, "int"),
            ParamType::Float => write!(f, "float"),
            ParamType::Bool => write!(f, "bool"),
            ParamType::Array => write!(f, "array"),
            ParamType::Object => write!(f, "object"),
            ParamType::Any => write!(f, "any"),
        }
    }
}

impl FromStr for ParamType {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "string" | "str" => Ok(ParamType::String),
            "int" | "integer" => Ok(ParamType::Int),
            "float" | "number" => Ok(ParamType::Float),
            "bool" | "boolean" => Ok(ParamType::Bool),
            "array" | "list" => Ok(ParamType::Array),
            "object" | "dict" => Ok(ParamType::Object),
            "any" => Ok(ParamType::Any),
            _ => Err(format!("Invalid parameter type: {}", s)),
        }
    }
}

/// Parameter definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Param {
    /// Parameter name
    pub name: String,

    /// Parameter type
    #[serde(rename = "type")]
    pub param_type: ParamType,

    /// Parameter description
    pub description: Option<String>,

    /// Default value
    pub default: Option<Value>,

    /// Whether parameter is required
    pub required: bool,

    /// Validation constraints
    pub constraints: Option<ParamConstraints>,

    /// Example values
    pub examples: Option<Vec<Value>>,
}

/// Parameter validation constraints
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParamConstraints {
    /// Minimum value (for numbers)
    pub min: Option<f64>,

    /// Maximum value (for numbers)
    pub max: Option<f64>,

    /// Minimum length (for strings/arrays)
    pub min_length: Option<usize>,

    /// Maximum length (for strings/arrays)
    pub max_length: Option<usize>,

    /// Regular expression pattern (for strings)
    pub pattern: Option<String>,

    /// Allowed values (enum)
    pub allowed_values: Option<Vec<Value>>,

    /// Custom validation expression
    pub custom: Option<String>,
}

impl Param {
    /// Create new parameter
    pub fn new(name: String, param_type: ParamType) -> Self {
        Self {
            name,
            param_type,
            description: None,
            default: None,
            required: false,
            constraints: None,
            examples: None,
        }
    }

    /// Create required parameter
    pub fn required(name: String, param_type: ParamType) -> Self {
        Self {
            name,
            param_type,
            description: None,
            default: None,
            required: true,
            constraints: None,
            examples: None,
        }
    }

    /// Set description
    pub fn with_description(mut self, description: String) -> Self {
        self.description = Some(description);
        self
    }

    /// Set default value
    pub fn with_default(mut self, default: Value) -> Self {
        self.default = Some(default);
        self
    }

    /// Set constraints
    pub fn with_constraints(mut self, constraints: ParamConstraints) -> Self {
        self.constraints = Some(constraints);
        self
    }

    /// Set examples
    pub fn with_examples(mut self, examples: Vec<Value>) -> Self {
        self.examples = Some(examples);
        self
    }

    /// Validate parameter value
    pub fn validate(&self, value: &Value) -> WorkflowResult<()> {
        // Check type compatibility
        self.validate_type(value)?;

        // Check constraints if present
        if let Some(constraints) = &self.constraints {
            self.validate_constraints(value, constraints)?;
        }

        Ok(())
    }

    /// Validate parameter type
    fn validate_type(&self, value: &Value) -> WorkflowResult<()> {
        let matches = match (&self.param_type, value) {
            (ParamType::String, Value::String(_)) => true,
            (ParamType::Int, Value::Number(n)) => n.is_i64(),
            (ParamType::Float, Value::Number(_)) => true,
            (ParamType::Bool, Value::Bool(_)) => true,
            (ParamType::Array, Value::Array(_)) => true,
            (ParamType::Object, Value::Object(_)) => true,
            (ParamType::Any, _) => true,
            _ => false,
        };

        if !matches {
            return Err(WorkflowError::Validation {
                message: format!(
                    "Parameter '{}' expected type '{}' but got '{}'",
                    self.name,
                    self.param_type,
                    value_type_name(value)
                ),
            });
        }

        Ok(())
    }

    /// Validate parameter constraints
    fn validate_constraints(&self, value: &Value, constraints: &ParamConstraints) -> WorkflowResult<()> {
        // Validate numeric constraints
        if let Value::Number(n) = value {
            if let Some(min) = constraints.min {
                if n.as_f64().unwrap_or(0.0) < min {
                    return Err(WorkflowError::Validation {
                        message: format!(
                            "Parameter '{}' value {} is less than minimum {}",
                            self.name,
                            n,
                            min
                        ),
                    });
                }
            }

            if let Some(max) = constraints.max {
                if n.as_f64().unwrap_or(0.0) > max {
                    return Err(WorkflowError::Validation {
                        message: format!(
                            "Parameter '{}' value {} is greater than maximum {}",
                            self.name,
                            n,
                            max
                        ),
                    });
                }
            }
        }

        // Validate string/array length constraints
        let length = match value {
            Value::String(s) => Some(s.len()),
            Value::Array(a) => Some(a.len()),
            _ => None,
        };

        if let Some(len) = length {
            if let Some(min_len) = constraints.min_length {
                if len < min_len {
                    return Err(WorkflowError::Validation {
                        message: format!(
                            "Parameter '{}' length {} is less than minimum {}",
                            self.name,
                            len,
                            min_len
                        ),
                    });
                }
            }

            if let Some(max_len) = constraints.max_length {
                if len > max_len {
                    return Err(WorkflowError::Validation {
                        message: format!(
                            "Parameter '{}' length {} is greater than maximum {}",
                            self.name,
                            len,
                            max_len
                        ),
                    });
                }
            }
        }

        // Validate string pattern
        if let (Value::String(s), Some(pattern)) = (value, &constraints.pattern) {
            let regex = regex::Regex::new(pattern).map_err(|e| WorkflowError::Validation {
                message: format!("Invalid regex pattern '{}': {}", pattern, e),
            })?;

            if !regex.is_match(s) {
                return Err(WorkflowError::Validation {
                    message: format!(
                        "Parameter '{}' value '{}' does not match pattern '{}'",
                        self.name,
                        s,
                        pattern
                    ),
                });
            }
        }

        // Validate allowed values
        if let Some(allowed) = &constraints.allowed_values {
            if !allowed.contains(value) {
                return Err(WorkflowError::Validation {
                    message: format!(
                        "Parameter '{}' value is not in allowed values: {:?}",
                        self.name,
                        allowed
                    ),
                });
            }
        }

        Ok(())
    }

    /// Get parameter value or default
    pub fn get_value_or_default(&self, provided: Option<&Value>) -> WorkflowResult<Value> {
        match provided {
            Some(value) => {
                self.validate(value)?;
                Ok(value.clone())
            }
            None => {
                if self.required {
                    Err(WorkflowError::Validation {
                        message: format!("Required parameter '{}' is missing", self.name),
                    })
                } else if let Some(default) = &self.default {
                    Ok(default.clone())
                } else {
                    Ok(Value::Null)
                }
            }
        }
    }
}

/// Parameter schema for workflows
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParamSchema {
    /// Parameter definitions
    pub params: HashMap<String, Param>,

    /// Parameter groups for organization
    pub groups: Option<HashMap<String, Vec<String>>>,
}

impl ParamSchema {
    /// Create new parameter schema
    pub fn new() -> Self {
        Self {
            params: HashMap::new(),
            groups: None,
        }
    }

    /// Add parameter to schema
    pub fn add_param(&mut self, param: Param) {
        self.params.insert(param.name.clone(), param);
    }

    /// Add parameter group
    pub fn add_group(&mut self, group_name: String, param_names: Vec<String>) {
        if self.groups.is_none() {
            self.groups = Some(HashMap::new());
        }
        self.groups.as_mut().unwrap().insert(group_name, param_names);
    }

    /// Validate all parameters
    pub fn validate(&self, values: &DictData) -> WorkflowResult<DictData> {
        let mut validated = HashMap::new();

        // Validate provided parameters
        for (name, param) in &self.params {
            let provided_value = values.get(name);
            let final_value = param.get_value_or_default(provided_value)?;

            if final_value != Value::Null {
                validated.insert(name.clone(), final_value);
            }
        }

        // Check for unknown parameters
        for name in values.keys() {
            if !self.params.contains_key(name) {
                return Err(WorkflowError::Validation {
                    message: format!("Unknown parameter: '{}'", name),
                });
            }
        }

        Ok(validated)
    }

    /// Get parameter by name
    pub fn get_param(&self, name: &str) -> Option<&Param> {
        self.params.get(name)
    }

    /// List all parameter names
    pub fn param_names(&self) -> Vec<&String> {
        self.params.keys().collect()
    }

    /// List required parameters
    pub fn required_params(&self) -> Vec<&Param> {
        self.params.values().filter(|p| p.required).collect()
    }

    /// Generate JSON schema
    pub fn to_json_schema(&self) -> Value {
        let mut properties = serde_json::Map::new();
        let mut required = Vec::new();

        for (name, param) in &self.params {
            let mut prop = serde_json::Map::new();

            // Add type
            let type_str = match param.param_type {
                ParamType::String => "string",
                ParamType::Int => "integer",
                ParamType::Float => "number",
                ParamType::Bool => "boolean",
                ParamType::Array => "array",
                ParamType::Object => "object",
                ParamType::Any => "any",
            };
            prop.insert("type".to_string(), Value::String(type_str.to_string()));

            // Add description
            if let Some(desc) = &param.description {
                prop.insert("description".to_string(), Value::String(desc.clone()));
            }

            // Add default
            if let Some(default) = &param.default {
                prop.insert("default".to_string(), default.clone());
            }

            // Add constraints
            if let Some(constraints) = &param.constraints {
                if let Some(min) = constraints.min {
                    prop.insert("minimum".to_string(), Value::Number(serde_json::Number::from_f64(min).unwrap()));
                }
                if let Some(max) = constraints.max {
                    prop.insert("maximum".to_string(), Value::Number(serde_json::Number::from_f64(max).unwrap()));
                }
                if let Some(min_len) = constraints.min_length {
                    prop.insert("minLength".to_string(), Value::Number(serde_json::Number::from(min_len)));
                }
                if let Some(max_len) = constraints.max_length {
                    prop.insert("maxLength".to_string(), Value::Number(serde_json::Number::from(max_len)));
                }
                if let Some(pattern) = &constraints.pattern {
                    prop.insert("pattern".to_string(), Value::String(pattern.clone()));
                }
                if let Some(allowed) = &constraints.allowed_values {
                    prop.insert("enum".to_string(), Value::Array(allowed.clone()));
                }
            }

            properties.insert(name.clone(), Value::Object(prop));

            if param.required {
                required.push(Value::String(name.clone()));
            }
        }

        let mut schema = serde_json::Map::new();
        schema.insert("type".to_string(), Value::String("object".to_string()));
        schema.insert("properties".to_string(), Value::Object(properties));

        if !required.is_empty() {
            schema.insert("required".to_string(), Value::Array(required));
        }

        Value::Object(schema)
    }
}

impl Default for ParamSchema {
    fn default() -> Self {
        Self::new()
    }
}

/// Helper function to get value type name
fn value_type_name(value: &Value) -> &'static str {
    match value {
        Value::Null => "null",
        Value::Bool(_) => "boolean",
        Value::Number(_) => "number",
        Value::String(_) => "string",
        Value::Array(_) => "array",
        Value::Object(_) => "object",
    }
}

/// Helper functions for creating common parameter types
pub mod helpers {
    use super::*;

    /// Create string parameter
    pub fn string_param(name: &str) -> Param {
        Param::new(name.to_string(), ParamType::String)
    }

    /// Create required string parameter
    pub fn required_string(name: &str) -> Param {
        Param::required(name.to_string(), ParamType::String)
    }

    /// Create integer parameter
    pub fn int_param(name: &str) -> Param {
        Param::new(name.to_string(), ParamType::Int)
    }

    /// Create boolean parameter with default false
    pub fn bool_param(name: &str) -> Param {
        Param::new(name.to_string(), ParamType::Bool)
            .with_default(Value::Bool(false))
    }

    /// Create array parameter
    pub fn array_param(name: &str) -> Param {
        Param::new(name.to_string(), ParamType::Array)
    }

    /// Create enum parameter from allowed values
    pub fn enum_param(name: &str, allowed_values: Vec<Value>) -> Param {
        let constraints = ParamConstraints {
            allowed_values: Some(allowed_values),
            min: None,
            max: None,
            min_length: None,
            max_length: None,
            pattern: None,
            custom: None,
        };

        Param::new(name.to_string(), ParamType::String)
            .with_constraints(constraints)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_param_type_parsing() {
        assert_eq!("string".parse::<ParamType>().unwrap(), ParamType::String);
        assert_eq!("int".parse::<ParamType>().unwrap(), ParamType::Int);
        assert_eq!("bool".parse::<ParamType>().unwrap(), ParamType::Bool);
        assert!("invalid".parse::<ParamType>().is_err());
    }

    #[test]
    fn test_param_creation() {
        let param = Param::required("name".to_string(), ParamType::String)
            .with_description("User name".to_string())
            .with_default(Value::String("anonymous".to_string()));

        assert_eq!(param.name, "name");
        assert_eq!(param.param_type, ParamType::String);
        assert!(param.required);
        assert_eq!(param.description, Some("User name".to_string()));
    }

    #[test]
    fn test_param_validation() {
        let param = Param::required("age".to_string(), ParamType::Int);

        // Valid value
        assert!(param.validate(&Value::Number(serde_json::Number::from(25))).is_ok());

        // Invalid type
        assert!(param.validate(&Value::String("25".to_string())).is_err());
    }

    #[test]
    fn test_param_constraints() {
        let constraints = ParamConstraints {
            min: Some(0.0),
            max: Some(100.0),
            min_length: None,
            max_length: None,
            pattern: None,
            allowed_values: None,
            custom: None,
        };

        let param = Param::required("score".to_string(), ParamType::Int)
            .with_constraints(constraints);

        // Valid value
        assert!(param.validate(&Value::Number(serde_json::Number::from(75))).is_ok());

        // Too low
        assert!(param.validate(&Value::Number(serde_json::Number::from(-5))).is_err());

        // Too high
        assert!(param.validate(&Value::Number(serde_json::Number::from(150))).is_err());
    }

    #[test]
    fn test_param_schema() {
        let mut schema = ParamSchema::new();

        schema.add_param(
            Param::required("name".to_string(), ParamType::String)
                .with_description("User name".to_string())
        );

        schema.add_param(
            Param::new("age".to_string(), ParamType::Int)
                .with_default(Value::Number(serde_json::Number::from(0)))
        );

        // Valid input
        let mut input = HashMap::new();
        input.insert("name".to_string(), Value::String("John".to_string()));
        input.insert("age".to_string(), Value::Number(serde_json::Number::from(30)));

        let result = schema.validate(&input);
        assert!(result.is_ok());

        // Missing required parameter
        let mut invalid_input = HashMap::new();
        invalid_input.insert("age".to_string(), Value::Number(serde_json::Number::from(30)));

        let result = schema.validate(&invalid_input);
        assert!(result.is_err());
    }

    #[test]
    fn test_helper_functions() {
        use helpers::*;

        let string_param = string_param("name");
        assert_eq!(string_param.param_type, ParamType::String);
        assert!(!string_param.required);

        let required_param = required_string("email");
        assert_eq!(required_param.param_type, ParamType::String);
        assert!(required_param.required);

        let bool_param = bool_param("enabled");
        assert_eq!(bool_param.param_type, ParamType::Bool);
        assert_eq!(bool_param.default, Some(Value::Bool(false)));

        let enum_param = enum_param("env", vec![
            Value::String("dev".to_string()),
            Value::String("prod".to_string()),
        ]);
        assert!(enum_param.constraints.is_some());
    }
}
