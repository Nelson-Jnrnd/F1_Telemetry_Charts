"""Renderer-independent chart specifications."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SeriesSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = None
    x: list[float]
    y: list[float]
    color: str | None = None
    edge_color: str | None = None
    render_mode: Literal["line", "step", "scatter", "excluded", "excluded_strip"] = "line"
    line_style: str = "-"
    marker: str | None = None
    marker_size: float = Field(default=22, gt=0)


class VerticalMarkerSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    label: str | None = None
    color: str | None = None
    alpha: float = Field(default=0.35, ge=0, le=1)
    line_style: str = "--"
    annotation: str | None = None


class HorizontalMarkerSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    y: float
    label: str | None = None
    color: str | None = None
    alpha: float = Field(default=0.35, ge=0, le=1)
    line_style: str = "--"
    line_width: float = Field(default=1.0, gt=0)


class ShadedRegionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x_start: float
    x_end: float
    label: str | None = None
    color: str = "#d9e2ec"
    alpha: float = Field(default=0.18, ge=0, le=1)
    annotation: str | None = None


class TextAnnotationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    text: str
    color: str = "#111827"
    font_size: float = Field(default=8, gt=0)
    font_weight: Literal["normal", "bold"] = "normal"
    horizontal_alignment: Literal["left", "center", "right"] = "left"


class HorizontalBarSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    y: float
    x_start: float
    x_end: float
    label: str | None = None
    color: str | None = None
    alpha: float = Field(default=0.85, ge=0, le=1)
    height: float = Field(default=0.8, gt=0)
    edge_color: str | None = None
    hatch: str | None = None


class BoxSummarySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    q1: float
    median: float
    q3: float
    width: float = Field(default=0.28, gt=0)
    face_color: str | None = None
    edge_color: str = "#111827"
    alpha: float = Field(default=0.2, ge=0, le=1)


class InfoBlockSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    text: str = Field(min_length=1)
    font_size: float = Field(default=8, gt=0)
    horizontal_alignment: Literal["left", "center", "right"] = "center"


class PanelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    x_label: str
    y_label: str
    series: list[SeriesSpec] = Field(default_factory=list)
    vertical_markers: list[VerticalMarkerSpec] = Field(default_factory=list)
    horizontal_markers: list[HorizontalMarkerSpec] = Field(default_factory=list)
    shaded_regions: list[ShadedRegionSpec] = Field(default_factory=list)
    horizontal_bars: list[HorizontalBarSpec] = Field(default_factory=list)
    box_summaries: list[BoxSummarySpec] = Field(default_factory=list)
    info_blocks: list[InfoBlockSpec] = Field(default_factory=list)
    annotations: list[TextAnnotationSpec] = Field(default_factory=list)
    summary_lines: list[str] = Field(default_factory=list)
    x_tick_labels: dict[float, str] = Field(default_factory=dict)
    y_tick_labels: dict[float, str] = Field(default_factory=dict)
    y_axis_inverted: bool = False
    x_limits: tuple[float, float] | None = None
    y_limits: tuple[float, float] | None = None
    state_message: str | None = None
    show_axes: bool = True
    height_ratio: float = Field(default=1.0, gt=0)


class ChartSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: str
    title: str
    subtitle: str | None = None
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
    horizontal_markers: list[HorizontalMarkerSpec] = Field(default_factory=list)
    shaded_regions: list[ShadedRegionSpec] = Field(default_factory=list)
    horizontal_bars: list[HorizontalBarSpec] = Field(default_factory=list)
    box_summaries: list[BoxSummarySpec] = Field(default_factory=list)
    annotations: list[TextAnnotationSpec] = Field(default_factory=list)
    x_tick_labels: dict[float, str] = Field(default_factory=dict)
    y_tick_labels: dict[float, str] = Field(default_factory=dict)
    summary_lines: list[str] = Field(default_factory=list)
    x_limits: tuple[float, float] | None = None
    y_limits: tuple[float, float] | None = None
    legend_order: list[str] = Field(default_factory=list)
    legend_location: str = "best"
    panels: list[PanelSpec] = Field(default_factory=list)
