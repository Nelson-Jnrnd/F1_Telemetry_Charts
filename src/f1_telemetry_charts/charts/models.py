"""Renderer-independent chart specifications."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SeriesSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    x: list[float]
    y: list[float]
    color: str | None = None


class ChartSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: str
    title: str
    x_label: str
    y_label: str
    series: list[SeriesSpec] = Field(min_length=1)
    selected_drivers: list[str]
    source_session: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
