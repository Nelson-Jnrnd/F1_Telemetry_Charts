"""Plugin metadata models."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PluginRecipeDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    required_dataset_fields: list[str] = Field(default_factory=list)
    factory: str = Field(min_length=1)
    output_artifact_types: list[str] = Field(default_factory=lambda: ["png", "json"])


class PluginDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plugin_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    recipes: list[PluginRecipeDefinition] = Field(default_factory=list)


class PluginStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plugin_id: str
    display_name: str | None = None
    version: str | None = None
    provider: str | None = None
    source_type: Literal["local_path", "entry_point"]
    source_location: str
    status: Literal["valid", "invalid"]
    recipes: list[PluginRecipeDefinition] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class LoadedPlugin(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    definition: PluginDefinition
    source_type: Literal["local_path", "entry_point"]
    source_location: str
    base_path: Path | None = None
