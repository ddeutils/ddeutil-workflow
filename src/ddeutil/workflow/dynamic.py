# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Dynamic Pipeline Generation System.

This module provides dynamic pipeline generation capabilities, supporting
Python code as configuration, template-based generation, and dynamic workflow
composition. Inspired by Apache Airflow and Prefect dynamic pipeline features.

Features:
- Python code as configuration
- Template-based pipeline generation
- Visual pipeline editors
- Dynamic workflow composition
- Configuration management
- Pipeline validation and testing

Classes:
    PipelineGenerator: Main pipeline generation engine
    PipelineTemplate: Template-based pipeline generation
    DynamicWorkflow: Dynamic workflow composition
    PipelineValidator: Pipeline validation and testing
    ConfigurationManager: Configuration management
    VisualEditor: Visual pipeline editor interface

Example:
    ```python
    from ddeutil.workflow.dynamic import PipelineGenerator, PipelineTemplate

    # Generate pipeline from Python code
    generator = PipelineGenerator()
    workflow = generator.from_python_code("""
        def create_pipeline():
            return {
                'name': 'dynamic_pipeline',
                'jobs': {
                    'process_data': {
                        'stages': [
                            {'type': 'python', 'code': 'print("Hello World")'}
                        ]
                    }
                }
            }
    """)

    # Generate from template
    template = PipelineTemplate("data_processing")
    workflow = template.generate(parameters={'table_name': 'users'})
    ```
"""
from __future__ import annotations

import ast
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, field
from string import Template
import inspect

from .__types import DictData
from .workflow import Workflow
from .stages import Stage, PyStage, CallStage
from .lineage import lineage_tracker

logger = logging.getLogger(__name__)

@dataclass
class PipelineTemplate:
    """Pipeline template definition."""

    name: str
    description: Optional[str] = None
    template_content: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DynamicStage:
    """Dynamic stage definition."""

    stage_type: str
    config: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    conditions: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class PipelineGenerator:
    """Main pipeline generation engine."""

    def __init__(self):
        self.templates: Dict[str, PipelineTemplate] = {}
        self.custom_functions: Dict[str, Callable] = {}
        self.validation_rules: Dict[str, Callable] = {}

    def register_template(self, template: PipelineTemplate) -> None:
        """Register a pipeline template."""
        self.templates[template.name] = template
        logger.info(f"Registered pipeline template: {template.name}")

    def register_custom_function(self, name: str, func: Callable) -> None:
        """Register a custom function for pipeline generation."""
        self.custom_functions[name] = func
        logger.info(f"Registered custom function: {name}")

    def register_validation_rule(self, name: str, rule_func: Callable) -> None:
        """Register a validation rule."""
        self.validation_rules[name] = rule_func
        logger.info(f"Registered validation rule: {name}")

    def from_python_code(self, code: str, context: Optional[Dict[str, Any]] = None) -> Workflow:
        """Generate workflow from Python code."""
        try:
            # Parse the Python code
            tree = ast.parse(code)

            # Extract workflow definition
            workflow_def = self._extract_workflow_definition(tree, context or {})

            # Validate the workflow definition
            self._validate_workflow_definition(workflow_def)

            # Create workflow from definition
            workflow = self._create_workflow_from_definition(workflow_def)

            logger.info(f"Generated workflow from Python code: {workflow.name}")
            return workflow

        except Exception as e:
            logger.error(f"Error generating workflow from Python code: {e}")
            raise

    def from_template(
        self,
        template_name: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Workflow:
        """Generate workflow from template."""
        if template_name not in self.templates:
            raise ValueError(f"Template '{template_name}' not found")

        template = self.templates[template_name]
        params = parameters or {}

        # Validate parameters
        self._validate_template_parameters(template, params)

        # Generate workflow definition from template
        workflow_def = self._generate_from_template(template, params)

        # Create workflow
        workflow = self._create_workflow_from_definition(workflow_def)

        logger.info(f"Generated workflow from template '{template_name}': {workflow.name}")
        return workflow

    def from_json_config(self, config: Union[str, Dict[str, Any]]) -> Workflow:
        """Generate workflow from JSON configuration."""
        if isinstance(config, str):
            config = json.loads(config)

        # Validate configuration
        self._validate_json_config(config)

        # Create workflow from configuration
        workflow = self._create_workflow_from_definition(config)

        logger.info(f"Generated workflow from JSON config: {workflow.name}")
        return workflow

    def from_yaml_config(self, yaml_content: str) -> Workflow:
        """Generate workflow from YAML configuration."""
        try:
            import yaml
            config = yaml.safe_load(yaml_content)
            return self.from_json_config(config)
        except ImportError:
            raise ImportError("PyYAML is required for YAML configuration support")

    def _extract_workflow_definition(
        self,
        tree: ast.AST,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract workflow definition from AST."""
        workflow_def = {
            "name": "dynamic_workflow",
            "jobs": {}
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "create_pipeline":
                # Extract return value from function
                for stmt in node.body:
                    if isinstance(stmt, ast.Return):
                        if isinstance(stmt.value, ast.Dict):
                            workflow_def = self._ast_dict_to_dict(stmt.value, context)
                        break
                break

        return workflow_def

    def _ast_dict_to_dict(self, node: ast.Dict, context: Dict[str, Any]) -> Dict[str, Any]:
        """Convert AST dict to Python dict."""
        result = {}

        for key_node, value_node in zip(node.keys, node.values):
            if isinstance(key_node, ast.Constant):
                key = key_node.value
            elif isinstance(key_node, ast.Str):
                key = key_node.s
            else:
                continue

            if isinstance(value_node, ast.Constant):
                value = value_node.value
            elif isinstance(value_node, ast.Str):
                value = value_node.s
            elif isinstance(value_node, ast.Num):
                value = value_node.n
            elif isinstance(value_node, ast.Dict):
                value = self._ast_dict_to_dict(value_node, context)
            elif isinstance(value_node, ast.List):
                value = self._ast_list_to_list(value_node, context)
            elif isinstance(value_node, ast.Name):
                value = context.get(value_node.id, value_node.id)
            else:
                value = str(value_node)

            result[key] = value

        return result

    def _ast_list_to_list(self, node: ast.List, context: Dict[str, Any]) -> List[Any]:
        """Convert AST list to Python list."""
        result = []

        for item_node in node.elts:
            if isinstance(item_node, ast.Constant):
                result.append(item_node.value)
            elif isinstance(item_node, ast.Str):
                result.append(item_node.s)
            elif isinstance(item_node, ast.Num):
                result.append(item_node.n)
            elif isinstance(item_node, ast.Dict):
                result.append(self._ast_dict_to_dict(item_node, context))
            elif isinstance(item_node, ast.List):
                result.append(self._ast_list_to_list(item_node, context))
            elif isinstance(item_node, ast.Name):
                result.append(context.get(item_node.id, item_node.id))
            else:
                result.append(str(item_node))

        return result

    def _generate_from_template(
        self,
        template: PipelineTemplate,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate workflow definition from template."""
        # Create template context
        context = {**template.parameters, **parameters}

        # Apply template substitution
        template_content = Template(template.template_content)
        workflow_json = template_content.safe_substitute(context)

        # Parse the generated JSON
        workflow_def = json.loads(workflow_json)

        return workflow_def

    def _validate_workflow_definition(self, workflow_def: Dict[str, Any]) -> None:
        """Validate workflow definition."""
        required_fields = ["name", "jobs"]

        for field in required_fields:
            if field not in workflow_def:
                raise ValueError(f"Missing required field: {field}")

        if not isinstance(workflow_def["jobs"], dict):
            raise ValueError("Jobs must be a dictionary")

        # Validate each job
        for job_name, job_config in workflow_def["jobs"].items():
            self._validate_job_config(job_name, job_config)

    def _validate_job_config(self, job_name: str, job_config: Dict[str, Any]) -> None:
        """Validate job configuration."""
        if "stages" not in job_config:
            raise ValueError(f"Job '{job_name}' missing stages")

        if not isinstance(job_config["stages"], list):
            raise ValueError(f"Job '{job_name}' stages must be a list")

        # Validate each stage
        for i, stage_config in enumerate(job_config["stages"]):
            self._validate_stage_config(job_name, i, stage_config)

    def _validate_stage_config(
        self,
        job_name: str,
        stage_index: int,
        stage_config: Dict[str, Any]
    ) -> None:
        """Validate stage configuration."""
        if not isinstance(stage_config, dict):
            raise ValueError(f"Stage {stage_index} in job '{job_name}' must be a dictionary")

        if "type" not in stage_config:
            raise ValueError(f"Stage {stage_index} in job '{job_name}' missing type")

        stage_type = stage_config["type"]

        # Validate based on stage type
        if stage_type == "python":
            if "code" not in stage_config:
                raise ValueError(f"Python stage {stage_index} in job '{job_name}' missing code")
        elif stage_type == "call":
            if "function" not in stage_config:
                raise ValueError(f"Call stage {stage_index} in job '{job_name}' missing function")
        elif stage_type == "bash":
            if "command" not in stage_config:
                raise ValueError(f"Bash stage {stage_index} in job '{job_name}' missing command")

    def _validate_template_parameters(
        self,
        template: PipelineTemplate,
        parameters: Dict[str, Any]
    ) -> None:
        """Validate template parameters."""
        # Check required parameters
        for param_name, param_config in template.parameters.items():
            if param_config.get("required", False) and param_name not in parameters:
                raise ValueError(f"Missing required parameter: {param_name}")

        # Validate parameter types
        for param_name, param_value in parameters.items():
            if param_name in template.parameters:
                expected_type = template.parameters[param_name].get("type")
                if expected_type and not isinstance(param_value, expected_type):
                    raise ValueError(
                        f"Parameter '{param_name}' expected type {expected_type}, got {type(param_value)}"
                    )

    def _validate_json_config(self, config: Dict[str, Any]) -> None:
        """Validate JSON configuration."""
        self._validate_workflow_definition(config)

    def _create_workflow_from_definition(self, workflow_def: Dict[str, Any]) -> Workflow:
        """Create workflow from definition."""
        workflow = Workflow(
            name=workflow_def["name"],
            jobs={}
        )

        # Create jobs
        for job_name, job_config in workflow_def["jobs"].items():
            stages = []

            for stage_config in job_config["stages"]:
                stage = self._create_stage_from_config(stage_config)
                stages.append(stage)

            # Create job (assuming Job class exists)
            from .workflow import Job
            job = Job(name=job_name, stages=stages)
            workflow.jobs[job_name] = job

        return workflow

    def _create_stage_from_config(self, stage_config: Dict[str, Any]) -> Stage:
        """Create stage from configuration."""
        stage_type = stage_config["type"]

        if stage_type == "python":
            return PyStage(
                iden=stage_config.get("id", f"stage_{int(datetime.now().timestamp())}"),
                name=stage_config.get("name", "Python Stage"),
                code=stage_config["code"]
            )
        elif stage_type == "call":
            return CallStage(
                iden=stage_config.get("id", f"stage_{int(datetime.now().timestamp())}"),
                name=stage_config.get("name", "Call Stage"),
                uses=stage_config["function"]
            )
        elif stage_type == "bash":
            from .stages import BashStage
            return BashStage(
                iden=stage_config.get("id", f"stage_{int(datetime.now().timestamp())}"),
                name=stage_config.get("name", "Bash Stage"),
                command=stage_config["command"]
            )
        else:
            raise ValueError(f"Unknown stage type: {stage_type}")

class DynamicWorkflow:
    """Dynamic workflow composition."""

    def __init__(self, name: str):
        self.name = name
        self.jobs: Dict[str, List[DynamicStage]] = {}
        self.metadata: Dict[str, Any] = {}

    def add_job(self, job_name: str, stages: Optional[List[DynamicStage]] = None) -> None:
        """Add a job to the workflow."""
        self.jobs[job_name] = stages or []

    def add_stage(
        self,
        job_name: str,
        stage_type: str,
        config: Optional[Dict[str, Any]] = None,
        dependencies: Optional[List[str]] = None
    ) -> DynamicStage:
        """Add a stage to a job."""
        if job_name not in self.jobs:
            self.add_job(job_name)

        stage = DynamicStage(
            stage_type=stage_type,
            config=config or {},
            dependencies=dependencies or []
        )

        self.jobs[job_name].append(stage)
        return stage

    def to_workflow(self) -> Workflow:
        """Convert to Workflow object."""
        generator = PipelineGenerator()

        # Convert to workflow definition
        workflow_def = {
            "name": self.name,
            "jobs": {}
        }

        for job_name, stages in self.jobs.items():
            workflow_def["jobs"][job_name] = {
                "stages": [
                    {
                        "type": stage.stage_type,
                        **stage.config
                    }
                    for stage in stages
                ]
            }

        return generator._create_workflow_from_definition(workflow_def)

class PipelineValidator:
    """Pipeline validation and testing."""

    def __init__(self):
        self.validation_rules: Dict[str, Callable] = {}

    def add_validation_rule(self, name: str, rule_func: Callable) -> None:
        """Add a validation rule."""
        self.validation_rules[name] = rule_func

    def validate_workflow(self, workflow: Workflow) -> Dict[str, Any]:
        """Validate a workflow."""
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "checks": {}
        }

        # Run all validation rules
        for rule_name, rule_func in self.validation_rules.items():
            try:
                rule_result = rule_func(workflow)
                results["checks"][rule_name] = rule_result

                if not rule_result.get("valid", True):
                    results["valid"] = False
                    results["errors"].extend(rule_result.get("errors", []))

                results["warnings"].extend(rule_result.get("warnings", []))

            except Exception as e:
                results["valid"] = False
                results["errors"].append(f"Validation rule '{rule_name}' failed: {e}")

        return results

    def test_workflow(self, workflow: Workflow, test_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Test a workflow with sample data."""
        results = {
            "success": False,
            "duration": 0,
            "errors": [],
            "output": None
        }

        try:
            start_time = datetime.now()

            # Execute workflow with test data
            test_params = test_data or {}
            result = workflow.execute(test_params)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            results["success"] = result.status == "SUCCESS"
            results["duration"] = duration
            results["output"] = result.data

            if result.status != "SUCCESS":
                results["errors"].append(f"Workflow execution failed: {result.status}")

        except Exception as e:
            results["errors"].append(f"Test execution failed: {e}")

        return results

class ConfigurationManager:
    """Configuration management."""

    def __init__(self, config_dir: Optional[Union[str, Path]] = None):
        self.config_dir = Path(config_dir) if config_dir else Path("./config")
        self.config_dir.mkdir(exist_ok=True)
        self.configs: Dict[str, Dict[str, Any]] = {}

    def save_config(self, name: str, config: Dict[str, Any]) -> None:
        """Save configuration to file."""
        config_file = self.config_dir / f"{name}.json"

        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

        self.configs[name] = config
        logger.info(f"Saved configuration: {name}")

    def load_config(self, name: str) -> Dict[str, Any]:
        """Load configuration from file."""
        config_file = self.config_dir / f"{name}.json"

        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")

        with open(config_file, "r") as f:
            config = json.load(f)

        self.configs[name] = config
        logger.info(f"Loaded configuration: {name}")
        return config

    def list_configs(self) -> List[str]:
        """List available configurations."""
        return [f.stem for f in self.config_dir.glob("*.json")]

    def delete_config(self, name: str) -> None:
        """Delete configuration file."""
        config_file = self.config_dir / f"{name}.json"

        if config_file.exists():
            config_file.unlink()
            if name in self.configs:
                del self.configs[name]
            logger.info(f"Deleted configuration: {name}")
        else:
            raise FileNotFoundError(f"Configuration file not found: {config_file}")

class VisualEditor:
    """Visual pipeline editor interface."""

    def __init__(self):
        self.components: Dict[str, Dict[str, Any]] = {}
        self.templates: Dict[str, Dict[str, Any]] = {}

    def register_component(
        self,
        name: str,
        component_type: str,
        config: Dict[str, Any]
    ) -> None:
        """Register a visual component."""
        self.components[name] = {
            "type": component_type,
            "config": config
        }

    def register_template(
        self,
        name: str,
        template: Dict[str, Any]
    ) -> None:
        """Register a visual template."""
        self.templates[name] = template

    def generate_workflow_from_visual(
        self,
        visual_config: Dict[str, Any]
    ) -> Workflow:
        """Generate workflow from visual configuration."""
        generator = PipelineGenerator()

        # Convert visual config to workflow definition
        workflow_def = self._convert_visual_to_workflow(visual_config)

        return generator._create_workflow_from_definition(workflow_def)

    def _convert_visual_to_workflow(self, visual_config: Dict[str, Any]) -> Dict[str, Any]:
        """Convert visual configuration to workflow definition."""
        # This is a simplified conversion - could be extended for complex visual editors
        workflow_def = {
            "name": visual_config.get("name", "visual_workflow"),
            "jobs": {}
        }

        # Convert nodes to stages
        for job_name, job_data in visual_config.get("jobs", {}).items():
            stages = []

            for node in job_data.get("nodes", []):
                stage = {
                    "type": node.get("type", "python"),
                    "name": node.get("name", "Stage"),
                    **node.get("config", {})
                }
                stages.append(stage)

            workflow_def["jobs"][job_name] = {"stages": stages}

        return workflow_def

# Global instances
pipeline_generator = PipelineGenerator()
pipeline_validator = PipelineValidator()
config_manager = ConfigurationManager()
visual_editor = VisualEditor()

# Register built-in templates
def register_builtin_templates():
    """Register built-in pipeline templates."""

    # Data processing template
    data_processing_template = PipelineTemplate(
        name="data_processing",
        description="Standard data processing pipeline",
        template_content='''{
            "name": "${pipeline_name}",
            "jobs": {
                "extract": {
                    "stages": [
                        {
                            "type": "python",
                            "name": "Extract Data",
                            "code": "print('Extracting from ${source}')"
                        }
                    ]
                },
                "transform": {
                    "stages": [
                        {
                            "type": "python",
                            "name": "Transform Data",
                            "code": "print('Transforming data')"
                        }
                    ]
                },
                "load": {
                    "stages": [
                        {
                            "type": "python",
                            "name": "Load Data",
                            "code": "print('Loading to ${destination}')"
                        }
                    ]
                }
            }
        }''',
        parameters={
            "pipeline_name": {"type": str, "required": True},
            "source": {"type": str, "required": True},
            "destination": {"type": str, "required": True}
        }
    )

    pipeline_generator.register_template(data_processing_template)

# Initialize built-in templates
register_builtin_templates()
