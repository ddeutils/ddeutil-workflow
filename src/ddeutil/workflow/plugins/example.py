# Example plugin for the workflow system
# This demonstrates how to create a plugin with metadata and registration

from ..result import Result
from ..reusables import tag

PLUGIN_INFO = {
    "name": "example_plugin",
    "version": "0.1.0",
    "description": "Example plugin demonstrating the plugin system",
    "dependencies": [],
    "entry_points": ["example_function", "example_stage"],
}


@tag("example", alias="example_function")
def example_function(input_data: str, result: Result) -> dict:
    """Example function that can be called from workflows."""
    result.trace.info(f"Processing input: {input_data}")
    return {"processed": input_data.upper(), "length": len(input_data)}


def register_plugin():
    """Register this plugin's components with the workflow system."""
    # This function is called when the plugin is loaded
    # Here you can register custom stages, triggers, or other components
    print("[ExamplePlugin] Plugin registered successfully")
