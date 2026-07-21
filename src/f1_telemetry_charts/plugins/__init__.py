"""Trusted recipe plugin discovery."""

from f1_telemetry_charts.plugins.manager import (
    PluginDiscoveryConfig,
    PluginManager,
    build_recipe_registry,
)
from f1_telemetry_charts.plugins.models import (
    PluginDefinition,
    PluginRecipeDefinition,
    PluginStatus,
)

__all__ = [
    "PluginDefinition",
    "PluginDiscoveryConfig",
    "PluginManager",
    "PluginRecipeDefinition",
    "PluginStatus",
    "build_recipe_registry",
]
