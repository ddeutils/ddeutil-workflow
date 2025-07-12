import importlib
import os
import pkgutil
from pathlib import Path

PLUGIN_REGISTRY = {}

PLUGIN_DIR = Path(__file__).parent


def load_plugins():
    """Dynamically discover and load plugins from the plugins directory."""
    for _, name, _ in pkgutil.iter_modules([str(PLUGIN_DIR)]):
        try:
            module = importlib.import_module(f"ddeutil.workflow.plugins.{name}")
            if hasattr(module, "PLUGIN_INFO"):
                info = module.PLUGIN_INFO
                PLUGIN_REGISTRY[name] = info
            if hasattr(module, "register_plugin"):
                module.register_plugin()
        except Exception as e:
            print(f"[PluginLoader] Failed to load plugin {name}: {e}")


# Example plugin metadata standard:
# Each plugin module should define:
# PLUGIN_INFO = {
#     'name': 'my_plugin',
#     'version': '0.1.0',
#     'description': 'Description of the plugin',
#     'dependencies': [],
#     'entry_points': ['custom_stage', 'custom_trigger'],
# }
