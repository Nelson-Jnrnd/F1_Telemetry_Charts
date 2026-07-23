"""Renderer-independent chart specifications."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SeriesSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    x: list[float]
    y: list[float]
    color: str | None = None
    render_mode: Literal["line", "step"] = "line"


class VerticalMarkerSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    label: str | None = None
    color: str | None = None
    alpha: float = Field(default=0.35, ge=0, le=1)
    line_style: str = "--"


class ShadedRegionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x_start: float
    x_end: float
    label: str | None = None
    color: str = "#d9e2ec"
    alpha: float = Field(default=0.18, ge=0, le=1)


class HorizontalBarSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    y: float
    x_start: float
    x_end: float
    label: str | None = None
    color: str | None = None
    alpha: float = Field(default=0.85, ge=0, le=1)


class ChartSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: str
    title: str
    x_label: str
    y_label: str
    series: list[SeriesSpec] = Field(default_factory=list)
    selected_drivers: list[str]
    source_session: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    y_axis_inverted: bool = False
    x_axis_inverted: bool = False
    vertical_markers: list[VerticalMarkerSpec] = Field(default_factory=list)
    shaded_regions: list[ShadedRegionSpec] = Field(default_factory=list)
    horizontal_bars: list[HorizontalBarSpec] = Field(default_factory=list)
