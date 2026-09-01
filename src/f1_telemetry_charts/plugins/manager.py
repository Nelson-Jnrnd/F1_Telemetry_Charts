"""Trusted recipe plugin discovery and registry integration."""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from importlib.metadata import entry_points
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from f1_telemetry_charts.config.models import PluginConfig
from f1_telemetry_charts.recipes.base import ChartRecipe
from f1_telemetry_charts.recipes.registry import (
    ALL_SUPPORTED_SESSION_TYPES,
    RecipeMetadata,
    RecipeRegistry,
    default_recipe_registry,
)
from f1_telemetry_charts.plugins.models import (
    LoadedPlugin,
    PluginDefinition,
    PluginRecipeDefinition,
    PluginStatus,
)


class PluginDiscoveryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    local_paths: list[Path] = Field(default_factory=list)
    entry_points_enabled: bool = False

    @classmethod
    def from_config(cls, config: PluginConfig) -> "PluginDiscoveryConfig":
        return cls(
            enabled=config.enabled,
            local_paths=config.local_paths,
            entry_points_enabled=config.entry_points_enabled,
        )


class PluginManager:
    def __init__(self, discovery: PluginDiscoveryConfig):
        self.discovery = discovery

    def discover(self) -> list[PluginStatus]:
        if not self.discovery.enabled:
            return []
        statuses: list[PluginStatus] = []
        statuses.extend(self._discover_local_paths())
        if self.discovery.entry_points_enabled:
            statuses.extend(self._discover_entry_points())
        return _mark_duplicate_recipes(statuses)

    def loaded_plugins(self) -> list[LoadedPlugin]:
        return [
            plugin
            for plugin in (self._load_status(status) for status in self.discover())
            if plugin is not None
        ]

    def build_registry(self) -> RecipeRegistry:
        registry = default_recipe_registry()
        if not self.discovery.enabled:
            return registry
        for loaded in self.loaded_plugins():
            for recipe in loaded.definition.recipes:
                factory = _load_factory(recipe.factory, loaded.base_path)
                registry.register(
                    RecipeMetadata(
                        recipe_id=recipe.recipe_id,
                        display_name=recipe.display_name,
                        required_dataset_fields=tuple(recipe.required_dataset_fields),
                        output_artifact_types=tuple(recipe.output_artifact_types),
                        source=loaded.definition.plugin_id,
                        supported_session_types=tuple(recipe.supported_session_types)
                        or ALL_SUPPORTED_SESSION_TYPES,
                        preview_asset=recipe.preview_asset,
                        icon=recipe.icon or "chart",
                    ),
                    factory,
                )
        return registry

    def _discover_local_paths(self) -> list[PluginStatus]:
        statuses: list[PluginStatus] = []
        for raw_path in self.discovery.local_paths:
            path = raw_path.expanduser().resolve()
            metadata_path = path / "f1tc-plugin.json" if path.is_dir() else path
            if not metadata_path.exists():
                statuses.append(
                    PluginStatus(
                        plugin_id=path.name,
                        source_type="local_path",
                        source_location=str(path),
                        status="invalid",
                        errors=["Plugin metadata file not found."],
                    )
                )
                continue
            status = _read_plugin_status(metadata_path)
            statuses.append(_validate_status_factories(status, metadata_path.parent))
        return statuses

    def _discover_entry_points(self) -> list[PluginStatus]:
        statuses: list[PluginStatus] = []
        for entry_point in entry_points(group="f1_telemetry_charts.plugins"):
            try:
                loaded = entry_point.load()
                definition = loaded() if callable(loaded) else loaded
                plugin = PluginDefinition.model_validate(definition)
            except Exception as exc:
                statuses.append(
                    PluginStatus(
                        plugin_id=entry_point.name,
                        source_type="entry_point",
                        source_location=entry_point.value,
                        status="invalid",
                        errors=[str(exc)],
                    )
                )
                continue
            statuses.append(
                PluginStatus(
                    plugin_id=plugin.plugin_id,
                    display_name=plugin.display_name,
                    version=plugin.version,
                    provider=plugin.provider,
                    source_type="entry_point",
                    source_location=entry_point.value,
                    status="valid",
                    recipes=plugin.recipes,
                )
            )
        return statuses

    def _load_status(self, status: PluginStatus) -> LoadedPlugin | None:
        if status.status != "valid":
            return None
        definition = PluginDefinition(
            plugin_id=status.plugin_id,
            display_name=status.display_name or status.plugin_id,
            version=status.version or "0.0.0",
            provider=status.provider or "unknown",
            recipes=status.recipes,
        )
        base_path = None
        if status.source_type == "local_path":
            source = Path(status.source_location)
            base_path = source if source.is_dir() else source.parent
        return LoadedPlugin(
            definition=definition,
            source_type=status.source_type,
            source_location=status.source_location,
            base_path=base_path,
        )


def build_recipe_registry(config: PluginConfig | None = None) -> RecipeRegistry:
    if config is None:
        return default_recipe_registry()
    return PluginManager(PluginDiscoveryConfig.from_config(config)).build_registry()


def _read_plugin_status(metadata_path: Path) -> PluginStatus:
    try:
        raw = json.loads(metadata_path.read_text(encoding="utf-8"))
        plugin = PluginDefinition.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        return PluginStatus(
            plugin_id=metadata_path.stem,
            source_type="local_path",
            source_location=str(metadata_path),
            status="invalid",
            errors=[str(exc)],
        )
    return PluginStatus(
        plugin_id=plugin.plugin_id,
        display_name=plugin.display_name,
        version=plugin.version,
        provider=plugin.provider,
        source_type="local_path",
        source_location=str(metadata_path),
        status="valid",
        recipes=plugin.recipes,
    )


def _mark_duplicate_recipes(statuses: list[PluginStatus]) -> list[PluginStatus]:
    seen: dict[str, str] = {
        recipe_id: "core" for recipe_id in default_recipe_registry().list_recipe_ids()
    }
    updated: list[PluginStatus] = []
    for status in statuses:
        errors = list(status.errors)
        for recipe in status.recipes:
            owner = seen.get(recipe.recipe_id)
            if owner is not None:
                errors.append(
                    f"Duplicate recipe ID '{recipe.recipe_id}' conflicts with {owner}."
                )
            else:
                seen[recipe.recipe_id] = status.plugin_id
        updated.append(
            status.model_copy(
                update={"status": "invalid" if errors else status.status, "errors": errors}
            )
        )
    return updated


def _validate_status_factories(status: PluginStatus, base_path: Path | None) -> PluginStatus:
    if status.status != "valid":
        return status
    errors = list(status.errors)
    for recipe in status.recipes:
        try:
            _load_factory(recipe.factory, base_path)
        except Exception as exc:
            errors.append(f"{recipe.recipe_id}: {exc}")
    if errors:
        return status.model_copy(update={"status": "invalid", "errors": errors})
    return status


def _load_factory(
    import_target: str,
    base_path: Path | None,
) -> Callable[[], ChartRecipe]:
    module_name, separator, attribute = import_target.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError(f"Invalid plugin factory import target: {import_target}")
    if base_path is not None:
        sys.path.insert(0, str(base_path))
    try:
        module = _import_module(module_name, base_path)
        factory = getattr(module, attribute)
    finally:
        if base_path is not None:
            try:
                sys.path.remove(str(base_path))
            except ValueError:
                pass
    if not callable(factory):
        raise TypeError(f"Plugin factory is not callable: {import_target}")
    return factory


def _import_module(module_name: str, base_path: Path | None):
    if base_path is not None:
        module_file = base_path / f"{module_name}.py"
        if module_file.exists():
            unique_name = f"_f1tc_plugin_{base_path.name}_{module_name}"
            spec = importlib.util.spec_from_file_location(unique_name, module_file)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot import plugin module: {module_file}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    return importlib.import_module(module_name)
