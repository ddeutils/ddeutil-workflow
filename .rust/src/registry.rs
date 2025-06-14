//! Registry module for workflow component registration and discovery.
//!
//! This module provides functionality to register and discover workflow components
//! such as stages, jobs, and workflows at runtime.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::{Arc, RwLock};

use crate::error::{WorkflowError, WorkflowResult};
use crate::job::Job;
use crate::stage::Stage;
use crate::types::DictData;
use crate::workflow::Workflow;

/// Component type enumeration
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ComponentType {
    /// Workflow component
    Workflow,
    /// Job component
    Job,
    /// Stage component
    Stage,
    /// Custom component
    Custom(String),
}

impl std::fmt::Display for ComponentType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ComponentType::Workflow => write!(f, "workflow"),
            ComponentType::Job => write!(f, "job"),
            ComponentType::Stage => write!(f, "stage"),
            ComponentType::Custom(name) => write!(f, "custom_{}", name),
        }
    }
}

/// Component metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComponentMetadata {
    /// Component name
    pub name: String,

    /// Component type
    pub component_type: ComponentType,

    /// Component version
    pub version: String,

    /// Component description
    pub description: Option<String>,

    /// Component author
    pub author: Option<String>,

    /// Component tags for categorization
    pub tags: Vec<String>,

    /// Component configuration schema
    pub config_schema: Option<serde_json::Value>,

    /// Whether component is deprecated
    pub deprecated: bool,

    /// Minimum required version of the workflow engine
    pub min_engine_version: Option<String>,

    /// Component dependencies
    pub dependencies: Vec<String>,

    /// Additional metadata
    pub metadata: DictData,
}

impl ComponentMetadata {
    /// Create new component metadata
    pub fn new(name: String, component_type: ComponentType, version: String) -> Self {
        Self {
            name,
            component_type,
            version,
            description: None,
            author: None,
            tags: Vec::new(),
            config_schema: None,
            deprecated: false,
            min_engine_version: None,
            dependencies: Vec::new(),
            metadata: HashMap::new(),
        }
    }

    /// Set description
    pub fn with_description(mut self, description: String) -> Self {
        self.description = Some(description);
        self
    }

    /// Set author
    pub fn with_author(mut self, author: String) -> Self {
        self.author = Some(author);
        self
    }

    /// Add tag
    pub fn with_tag(mut self, tag: String) -> Self {
        self.tags.push(tag);
        self
    }

    /// Add multiple tags
    pub fn with_tags(mut self, tags: Vec<String>) -> Self {
        self.tags.extend(tags);
        self
    }

    /// Set configuration schema
    pub fn with_config_schema(mut self, schema: serde_json::Value) -> Self {
        self.config_schema = Some(schema);
        self
    }

    /// Mark as deprecated
    pub fn deprecated(mut self) -> Self {
        self.deprecated = true;
        self
    }

    /// Set minimum engine version
    pub fn with_min_engine_version(mut self, version: String) -> Self {
        self.min_engine_version = Some(version);
        self
    }

    /// Add dependency
    pub fn with_dependency(mut self, dependency: String) -> Self {
        self.dependencies.push(dependency);
        self
    }

    /// Add metadata field
    pub fn with_metadata(mut self, key: String, value: serde_json::Value) -> Self {
        self.metadata.insert(key, value);
        self
    }

    /// Get component identifier
    pub fn identifier(&self) -> String {
        format!("{}:{}", self.name, self.version)
    }

    /// Check if component is compatible with engine version
    pub fn is_compatible(&self, engine_version: &str) -> bool {
        if let Some(min_version) = &self.min_engine_version {
            // Simple version comparison (in production, use proper semver)
            engine_version >= min_version
        } else {
            true
        }
    }

    /// Check if component has tag
    pub fn has_tag(&self, tag: &str) -> bool {
        self.tags.iter().any(|t| t == tag)
    }
}

/// Component factory trait for creating component instances
pub trait ComponentFactory: Send + Sync {
    /// Create component instance from configuration
    fn create(&self, config: &DictData) -> WorkflowResult<Box<dyn ComponentInstance>>;

    /// Get component metadata
    fn metadata(&self) -> &ComponentMetadata;

    /// Validate component configuration
    fn validate_config(&self, config: &DictData) -> WorkflowResult<()> {
        // Default implementation - override for custom validation
        let _ = config;
        Ok(())
    }
}

/// Component instance trait
pub trait ComponentInstance: Send + Sync + std::fmt::Debug {
    /// Get component name
    fn name(&self) -> &str;

    /// Get component type
    fn component_type(&self) -> ComponentType;

    /// Get component configuration
    fn config(&self) -> &DictData;
}

/// Registry entry for a component
#[derive(Debug)]
pub struct RegistryEntry {
    /// Component metadata
    pub metadata: ComponentMetadata,

    /// Component factory
    pub factory: Box<dyn ComponentFactory>,
}

impl RegistryEntry {
    /// Create new registry entry
    pub fn new(metadata: ComponentMetadata, factory: Box<dyn ComponentFactory>) -> Self {
        Self { metadata, factory }
    }

    /// Create component instance
    pub fn create_instance(&self, config: &DictData) -> WorkflowResult<Box<dyn ComponentInstance>> {
        self.factory.validate_config(config)?;
        self.factory.create(config)
    }
}

/// Component registry for managing workflow components
#[derive(Debug)]
pub struct ComponentRegistry {
    /// Registry entries by component type and name
    entries: Arc<RwLock<HashMap<ComponentType, HashMap<String, RegistryEntry>>>>,

    /// Default versions for components
    default_versions: Arc<RwLock<HashMap<String, String>>>,
}

impl ComponentRegistry {
    /// Create new component registry
    pub fn new() -> Self {
        Self {
            entries: Arc::new(RwLock::new(HashMap::new())),
            default_versions: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Register component
    pub fn register(&self, entry: RegistryEntry) -> WorkflowResult<()> {
        let component_type = entry.metadata.component_type.clone();
        let component_name = entry.metadata.name.clone();
        let component_version = entry.metadata.version.clone();

        let mut entries = self.entries.write().map_err(|_| WorkflowError::Registry {
            message: "Failed to acquire write lock".to_string(),
        })?;

        // Get or create type entry
        let type_entry = entries.entry(component_type.clone()).or_insert_with(HashMap::new);

        // Generate unique key with version
        let key = format!("{}:{}", component_name, component_version);

        // Check for conflicts
        if type_entry.contains_key(&key) {
            return Err(WorkflowError::Registry {
                message: format!(
                    "Component '{}' of type '{}' version '{}' is already registered",
                    component_name, component_type, component_version
                ),
            });
        }

        // Register component
        type_entry.insert(key, entry);

        // Update default version if this is the first registration or a newer version
        let mut default_versions = self.default_versions.write().map_err(|_| WorkflowError::Registry {
            message: "Failed to acquire write lock for default versions".to_string(),
        })?;

        let default_key = format!("{}:{}", component_type, component_name);
        if !default_versions.contains_key(&default_key) {
            default_versions.insert(default_key, component_version);
        }

        Ok(())
    }

    /// Unregister component
    pub fn unregister(&self, component_type: ComponentType, name: &str, version: &str) -> WorkflowResult<()> {
        let mut entries = self.entries.write().map_err(|_| WorkflowError::Registry {
            message: "Failed to acquire write lock".to_string(),
        })?;

        if let Some(type_entry) = entries.get_mut(&component_type) {
            let key = format!("{}:{}", name, version);
            if type_entry.remove(&key).is_none() {
                return Err(WorkflowError::Registry {
                    message: format!(
                        "Component '{}' of type '{}' version '{}' not found",
                        name, component_type, version
                    ),
                });
            }
        } else {
            return Err(WorkflowError::Registry {
                message: format!("No components of type '{}' registered", component_type),
            });
        }

        Ok(())
    }

    /// Get component entry
    pub fn get(&self, component_type: ComponentType, name: &str, version: Option<&str>) -> WorkflowResult<Option<Box<dyn ComponentInstance>>> {
        let entries = self.entries.read().map_err(|_| WorkflowError::Registry {
            message: "Failed to acquire read lock".to_string(),
        })?;

        let type_entry = match entries.get(&component_type) {
            Some(entry) => entry,
            None => return Ok(None),
        };

        let version = match version {
            Some(v) => v.to_string(),
            None => {
                // Get default version
                let default_versions = self.default_versions.read().map_err(|_| WorkflowError::Registry {
                    message: "Failed to acquire read lock for default versions".to_string(),
                })?;

                let default_key = format!("{}:{}", component_type, name);
                match default_versions.get(&default_key) {
                    Some(v) => v.clone(),
                    None => return Ok(None),
                }
            }
        };

        let key = format!("{}:{}", name, version);
        match type_entry.get(&key) {
            Some(entry) => {
                // Create instance with empty config as default
                let config = HashMap::new();
                let instance = entry.create_instance(&config)?;
                Ok(Some(instance))
            }
            None => Ok(None),
        }
    }

    /// Create component instance with configuration
    pub fn create_instance(&self, component_type: ComponentType, name: &str, version: Option<&str>, config: &DictData) -> WorkflowResult<Box<dyn ComponentInstance>> {
        let entries = self.entries.read().map_err(|_| WorkflowError::Registry {
            message: "Failed to acquire read lock".to_string(),
        })?;

        let type_entry = entries.get(&component_type).ok_or_else(|| WorkflowError::Registry {
            message: format!("No components of type '{}' registered", component_type),
        })?;

        let version = match version {
            Some(v) => v.to_string(),
            None => {
                // Get default version
                let default_versions = self.default_versions.read().map_err(|_| WorkflowError::Registry {
                    message: "Failed to acquire read lock for default versions".to_string(),
                })?;

                let default_key = format!("{}:{}", component_type, name);
                default_versions.get(&default_key).ok_or_else(|| WorkflowError::Registry {
                    message: format!("No default version found for component '{}' of type '{}'", name, component_type),
                })?.clone()
            }
        };

        let key = format!("{}:{}", name, version);
        let entry = type_entry.get(&key).ok_or_else(|| WorkflowError::Registry {
            message: format!(
                "Component '{}' of type '{}' version '{}' not found",
                name, component_type, version
            ),
        })?;

        entry.create_instance(config)
    }

    /// List all components of a specific type
    pub fn list_components(&self, component_type: ComponentType) -> WorkflowResult<Vec<ComponentMetadata>> {
        let entries = self.entries.read().map_err(|_| WorkflowError::Registry {
            message: "Failed to acquire read lock".to_string(),
        })?;

        let type_entry = match entries.get(&component_type) {
            Some(entry) => entry,
            None => return Ok(Vec::new()),
        };

        let components = type_entry
            .values()
            .map(|entry| entry.metadata.clone())
            .collect();

        Ok(components)
    }

    /// List all registered component types
    pub fn list_types(&self) -> WorkflowResult<Vec<ComponentType>> {
        let entries = self.entries.read().map_err(|_| WorkflowError::Registry {
            message: "Failed to acquire read lock".to_string(),
        })?;

        Ok(entries.keys().cloned().collect())
    }

    /// Search components by tags
    pub fn search_by_tag(&self, tag: &str) -> WorkflowResult<Vec<ComponentMetadata>> {
        let entries = self.entries.read().map_err(|_| WorkflowError::Registry {
            message: "Failed to acquire read lock".to_string(),
        })?;

        let mut results = Vec::new();

        for type_entry in entries.values() {
            for entry in type_entry.values() {
                if entry.metadata.has_tag(tag) {
                    results.push(entry.metadata.clone());
                }
            }
        }

        Ok(results)
    }

    /// Get component metadata
    pub fn get_metadata(&self, component_type: ComponentType, name: &str, version: Option<&str>) -> WorkflowResult<Option<ComponentMetadata>> {
        let entries = self.entries.read().map_err(|_| WorkflowError::Registry {
            message: "Failed to acquire read lock".to_string(),
        })?;

        let type_entry = match entries.get(&component_type) {
            Some(entry) => entry,
            None => return Ok(None),
        };

        let version = match version {
            Some(v) => v.to_string(),
            None => {
                // Get default version
                let default_versions = self.default_versions.read().map_err(|_| WorkflowError::Registry {
                    message: "Failed to acquire read lock for default versions".to_string(),
                })?;

                let default_key = format!("{}:{}", component_type, name);
                match default_versions.get(&default_key) {
                    Some(v) => v.clone(),
                    None => return Ok(None),
                }
            }
        };

        let key = format!("{}:{}", name, version);
        Ok(type_entry.get(&key).map(|entry| entry.metadata.clone()))
    }

    /// Clear all registered components
    pub fn clear(&self) -> WorkflowResult<()> {
        let mut entries = self.entries.write().map_err(|_| WorkflowError::Registry {
            message: "Failed to acquire write lock".to_string(),
        })?;

        let mut default_versions = self.default_versions.write().map_err(|_| WorkflowError::Registry {
            message: "Failed to acquire write lock for default versions".to_string(),
        })?;

        entries.clear();
        default_versions.clear();

        Ok(())
    }

    /// Get registry statistics
    pub fn stats(&self) -> WorkflowResult<RegistryStats> {
        let entries = self.entries.read().map_err(|_| WorkflowError::Registry {
            message: "Failed to acquire read lock".to_string(),
        })?;

        let mut stats = RegistryStats {
            total_components: 0,
            components_by_type: HashMap::new(),
            deprecated_count: 0,
        };

        for (component_type, type_entry) in entries.iter() {
            let type_count = type_entry.len();
            stats.total_components += type_count;
            stats.components_by_type.insert(component_type.clone(), type_count);

            // Count deprecated components
            for entry in type_entry.values() {
                if entry.metadata.deprecated {
                    stats.deprecated_count += 1;
                }
            }
        }

        Ok(stats)
    }
}

impl Default for ComponentRegistry {
    fn default() -> Self {
        Self::new()
    }
}

/// Registry statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegistryStats {
    /// Total number of registered components
    pub total_components: usize,

    /// Components count by type
    pub components_by_type: HashMap<ComponentType, usize>,

    /// Number of deprecated components
    pub deprecated_count: usize,
}

/// Global component registry instance
static GLOBAL_REGISTRY: once_cell::sync::Lazy<ComponentRegistry> =
    once_cell::sync::Lazy::new(ComponentRegistry::new);

/// Get global component registry
pub fn global_registry() -> &'static ComponentRegistry {
    &GLOBAL_REGISTRY
}

/// Register component in global registry
pub fn register_component(entry: RegistryEntry) -> WorkflowResult<()> {
    global_registry().register(entry)
}

/// Create component instance from global registry
pub fn create_component(
    component_type: ComponentType,
    name: &str,
    version: Option<&str>,
    config: &DictData,
) -> WorkflowResult<Box<dyn ComponentInstance>> {
    global_registry().create_instance(component_type, name, version, config)
}

/// Helper macros for component registration
#[macro_export]
macro_rules! register_stage {
    ($factory:expr) => {
        $crate::registry::register_component($crate::registry::RegistryEntry::new(
            $factory.metadata().clone(),
            Box::new($factory),
        ))
    };
}

#[macro_export]
macro_rules! register_job {
    ($factory:expr) => {
        $crate::registry::register_component($crate::registry::RegistryEntry::new(
            $factory.metadata().clone(),
            Box::new($factory),
        ))
    };
}

#[macro_export]
macro_rules! register_workflow {
    ($factory:expr) => {
        $crate::registry::register_component($crate::registry::RegistryEntry::new(
            $factory.metadata().clone(),
            Box::new($factory),
        ))
    };
}

#[cfg(test)]
mod tests {
    use super::*;

    // Mock component for testing
    #[derive(Debug)]
    struct MockComponent {
        name: String,
        component_type: ComponentType,
        config: DictData,
    }

    impl ComponentInstance for MockComponent {
        fn name(&self) -> &str {
            &self.name
        }

        fn component_type(&self) -> ComponentType {
            self.component_type.clone()
        }

        fn config(&self) -> &DictData {
            &self.config
        }
    }

    struct MockFactory {
        metadata: ComponentMetadata,
    }

    impl MockFactory {
        fn new(name: String, component_type: ComponentType) -> Self {
            let metadata = ComponentMetadata::new(
                name,
                component_type,
                "1.0.0".to_string(),
            ).with_description("Mock component for testing".to_string());

            Self { metadata }
        }
    }

    impl ComponentFactory for MockFactory {
        fn create(&self, config: &DictData) -> WorkflowResult<Box<dyn ComponentInstance>> {
            Ok(Box::new(MockComponent {
                name: self.metadata.name.clone(),
                component_type: self.metadata.component_type.clone(),
                config: config.clone(),
            }))
        }

        fn metadata(&self) -> &ComponentMetadata {
            &self.metadata
        }
    }

    #[test]
    fn test_component_metadata() {
        let metadata = ComponentMetadata::new(
            "test-stage".to_string(),
            ComponentType::Stage,
            "1.0.0".to_string(),
        )
        .with_description("Test stage component".to_string())
        .with_author("Test Author".to_string())
        .with_tag("test".to_string())
        .with_tag("stage".to_string());

        assert_eq!(metadata.name, "test-stage");
        assert_eq!(metadata.component_type, ComponentType::Stage);
        assert_eq!(metadata.version, "1.0.0");
        assert_eq!(metadata.identifier(), "test-stage:1.0.0");
        assert!(metadata.has_tag("test"));
        assert!(metadata.has_tag("stage"));
        assert!(!metadata.has_tag("unknown"));
    }

    #[test]
    fn test_registry_registration() {
        let registry = ComponentRegistry::new();

        let factory = MockFactory::new("test-stage".to_string(), ComponentType::Stage);
        let entry = RegistryEntry::new(factory.metadata.clone(), Box::new(factory));

        let result = registry.register(entry);
        assert!(result.is_ok());

        // Test duplicate registration
        let factory2 = MockFactory::new("test-stage".to_string(), ComponentType::Stage);
        let entry2 = RegistryEntry::new(factory2.metadata.clone(), Box::new(factory2));

        let result = registry.register(entry2);
        assert!(result.is_err());
    }

    #[test]
    fn test_component_creation() {
        let registry = ComponentRegistry::new();

        let factory = MockFactory::new("test-stage".to_string(), ComponentType::Stage);
        let entry = RegistryEntry::new(factory.metadata.clone(), Box::new(factory));

        registry.register(entry).unwrap();

        let config = HashMap::new();
        let instance = registry.create_instance(
            ComponentType::Stage,
            "test-stage",
            Some("1.0.0"),
            &config,
        );

        assert!(instance.is_ok());
        let instance = instance.unwrap();
        assert_eq!(instance.name(), "test-stage");
        assert_eq!(instance.component_type(), ComponentType::Stage);
    }

    #[test]
    fn test_component_listing() {
        let registry = ComponentRegistry::new();

        // Register multiple components
        let factory1 = MockFactory::new("stage1".to_string(), ComponentType::Stage);
        let entry1 = RegistryEntry::new(factory1.metadata.clone(), Box::new(factory1));
        registry.register(entry1).unwrap();

        let factory2 = MockFactory::new("stage2".to_string(), ComponentType::Stage);
        let entry2 = RegistryEntry::new(factory2.metadata.clone(), Box::new(factory2));
        registry.register(entry2).unwrap();

        let components = registry.list_components(ComponentType::Stage).unwrap();
        assert_eq!(components.len(), 2);

        let types = registry.list_types().unwrap();
        assert!(types.contains(&ComponentType::Stage));
    }

    #[test]
    fn test_registry_stats() {
        let registry = ComponentRegistry::new();

        let factory = MockFactory::new("test-stage".to_string(), ComponentType::Stage);
        let entry = RegistryEntry::new(factory.metadata.clone(), Box::new(factory));
        registry.register(entry).unwrap();

        let stats = registry.stats().unwrap();
        assert_eq!(stats.total_components, 1);
        assert_eq!(stats.components_by_type.get(&ComponentType::Stage), Some(&1));
        assert_eq!(stats.deprecated_count, 0);
    }

    #[test]
    fn test_tag_search() {
        let registry = ComponentRegistry::new();

        let factory = MockFactory::new("test-stage".to_string(), ComponentType::Stage);
        let mut metadata = factory.metadata.clone();
        metadata = metadata.with_tag("production".to_string());

        let entry = RegistryEntry::new(metadata, Box::new(factory));
        registry.register(entry).unwrap();

        let results = registry.search_by_tag("production").unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].name, "test-stage");

        let empty_results = registry.search_by_tag("nonexistent").unwrap();
        assert_eq!(empty_results.len(), 0);
    }
}
