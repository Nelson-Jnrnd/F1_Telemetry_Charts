"""Typed configuration models."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SessionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    season: int = Field(ge=1950)
    event: str = Field(min_length=1)
    session: str = Field(min_length=1)


class DriverSelectionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    drivers: list[str] = Field(min_length=1)


class DataCacheConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    directory: Path = Field(default=Path(".cache/fastf1"))
    mode: Literal["cache-or-fetch", "cache-only"] = "cache-or-fetch"
    fixture_path: Path | None = None


class ChartRecipeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: str = Field(min_length=1)
    enabled: bool = True
    title: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    preset_id: str | None = None


class ThemeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "technical_editorial"
    figure_width: float = Field(default=16.0, gt=0)
    figure_height: float = Field(default=9.0, gt=0)
    dpi: int = Field(default=300, ge=72, le=600)
    background_color: str = "#ffffff"
    foreground_color: str = "#1f2933"
    grid: bool = True


class ExportConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    formats: list[Literal["png", "json"]] = Field(default_factory=lambda: ["png", "json"])


class PluginConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    local_paths: list[Path] = Field(default_factory=list)
    entry_points_enabled: bool = False


class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    project_id: str = Field(min_length=1)
    session: SessionConfig
    driver_selection: DriverSelectionConfig
    data_cache: DataCacheConfig = Field(default_factory=DataCacheConfig)
    recipes: list[ChartRecipeConfig] = Field(min_length=1)
    theme: ThemeConfig = Field(default_factory=ThemeConfig)
    exports: ExportConfig = Field(default_factory=ExportConfig)
    plugins: PluginConfig = Field(default_factory=PluginConfig)
    output_dir: Path = Path("runs")
