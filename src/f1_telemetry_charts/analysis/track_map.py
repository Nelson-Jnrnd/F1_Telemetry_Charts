"""Snapshot-derived track map payloads for visual telemetry range selection."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from f1_telemetry_charts.config.models import ChartRecipeConfig
from f1_telemetry_charts.data.models import (
    CircuitCorner,
    SessionDataset,
    TrackGeometryPoint as CanonicalTrackGeometryPoint,
)
from f1_telemetry_charts.recipes.parameters import (
    ParameterDiagnostics,
    apply_lap_filters,
    parameter_value,
    section,
    selected_driver_codes,
)


DEFAULT_TRACK_MAP_POINT_LIMIT = 500
MAX_TRACK_MAP_POINT_LIMIT = 1200


class TrackMapPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    distance_m: float
    x: float
    y: float
    display_x: float = Field(ge=0, le=100)
    display_y: float = Field(ge=0, le=100)


class TrackMapMarker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    distance_m: float
    display_x: float = Field(ge=0, le=100)
    display_y: float = Field(ge=0, le=100)


class TrackMapSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_distance_m: float
    end_distance_m: float
    source: str
    start_marker: TrackMapMarker
    end_marker: TrackMapMarker
    corner: dict[str, Any] | None = None


class TrackMapCorner(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    number: int
    letter: str | None = None
    distance_m: float | None = None
    display_x: float | None = Field(default=None, ge=0, le=100)
    display_y: float | None = Field(default=None, ge=0, le=100)
    source_x: float
    source_y: float
    source_distance_m: float | None = None
    projection_status: Literal["fastf1_distance", "nearest_geometry", "unavailable"]
    projection_error: float | None = None


class TrackMapPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["available", "unavailable", "invalid"]
    recipe_id: str
    session_id: str | None = None
    selected_drivers: list[str] = Field(default_factory=list)
    source_driver: str | None = None
    source_lap: int | None = None
    geometry_metadata: dict[str, Any] = Field(default_factory=dict)
    points: list[TrackMapPoint] = Field(default_factory=list)
    corners: list[TrackMapCorner] = Field(default_factory=list)
    segment: TrackMapSegment | None = None
    bounds: dict[str, Any] = Field(default_factory=dict)
    point_count: int = 0
    original_sample_count: int = 0
    max_points: int = DEFAULT_TRACK_MAP_POINT_LIMIT
    downsampled: bool = False
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


def build_track_map_payload(
    dataset: SessionDataset,
    config: ChartRecipeConfig,
    *,
    session_id: str | None = None,
    max_points: int = DEFAULT_TRACK_MAP_POINT_LIMIT,
) -> TrackMapPayload:
    limit = min(max(2, int(max_points)), MAX_TRACK_MAP_POINT_LIMIT)
    diagnostics = ParameterDiagnostics()
    try:
        selected_drivers = selected_driver_codes(dataset, config)
    except ValueError as exc:
        return TrackMapPayload(
            status="invalid",
            recipe_id=config.recipe_id,
            session_id=session_id,
            max_points=limit,
            diagnostics=[{"field": "drivers", "message": str(exc)}],
        )

    lap_result = apply_lap_filters(dataset.laps, config)
    if lap_result.diagnostics.errors:
        return TrackMapPayload(
            status="invalid",
            recipe_id=config.recipe_id,
            session_id=session_id,
            selected_drivers=selected_drivers,
            max_points=limit,
            diagnostics=lap_result.diagnostics.errors,
        )
    diagnostics.warnings.extend(lap_result.diagnostics.warnings)
    track_geometry = dataset.track_geometry
    if track_geometry is None:
        return TrackMapPayload(
            status="unavailable",
            recipe_id=config.recipe_id,
            session_id=session_id,
            selected_drivers=selected_drivers,
            max_points=limit,
            diagnostics=[
                {
                    "field": "track_map",
                    "message": "Session track geometry is unavailable in the loaded snapshot",
                }
            ],
        )

    source_points = sorted(track_geometry.points, key=lambda point: point.distance_m)
    if len(source_points) < 2:
        return TrackMapPayload(
            status="unavailable",
            recipe_id=config.recipe_id,
            session_id=session_id,
            selected_drivers=selected_drivers,
            max_points=limit,
            diagnostics=[
                {
                    "field": "track_map",
                    "message": "Track map requires at least two positioned telemetry samples",
                }
            ],
    )

    projected = _project_points(source_points, max_points=limit)
    distance_bounds = {
        "available": True,
        "minimum": source_points[0].distance_m,
        "maximum": source_points[-1].distance_m,
    }
    corners, corner_diagnostics = _project_corners(dataset, projected)
    diagnostics.warnings.extend(corner_diagnostics)
    segment = _selected_segment(config, projected, distance_bounds, corners)
    return TrackMapPayload(
        status="available",
        recipe_id=config.recipe_id,
        session_id=session_id,
        selected_drivers=selected_drivers,
        source_driver=track_geometry.source_driver,
        source_lap=track_geometry.source_lap,
        geometry_metadata={
            "algorithm_version": track_geometry.algorithm_version,
            "aggregation_method": track_geometry.aggregation_method,
            "contributing_driver_count": track_geometry.contributing_driver_count,
            "contributing_lap_count": track_geometry.contributing_lap_count,
            "original_closure_gap": track_geometry.original_closure_gap,
            "closure_adjusted": track_geometry.closure_adjusted,
        },
        points=projected,
        corners=corners,
        segment=segment,
        bounds={
            "distance_m": distance_bounds,
            "x": _bounds([point.x for point in projected]),
            "y": _bounds([point.y for point in projected]),
            "corners": {
                "available": bool(corners),
                "count": len(corners),
                "source": dataset.circuit_info.source
                if dataset.circuit_info is not None and corners
                else None,
                "reason": None
                if corners
                else "FastF1 circuit corner metadata is unavailable in the loaded snapshot",
            },
        },
        point_count=len(projected),
        original_sample_count=track_geometry.original_sample_count,
        max_points=limit,
        downsampled=track_geometry.downsampled or len(projected) < len(source_points),
        diagnostics=diagnostics.warnings,
    )


def _project_points(
    samples: list[CanonicalTrackGeometryPoint],
    *,
    max_points: int,
) -> list[TrackMapPoint]:
    source = _downsample(samples, max_points=max_points)
    x_values = [float(sample.x) for sample in source if sample.x is not None]
    y_values = [float(sample.y) for sample in source if sample.y is not None]
    x_min = min(x_values)
    x_span = max(x_values) - x_min
    y_min = min(y_values)
    y_span = max(y_values) - y_min
    scale = max(x_span, y_span, 1.0)
    x_offset = (100.0 - (x_span / scale * 100.0)) / 2.0
    y_offset = (100.0 - (y_span / scale * 100.0)) / 2.0

    points: list[TrackMapPoint] = []
    for sample in source:
        x = float(sample.x or 0)
        y = float(sample.y or 0)
        points.append(
            TrackMapPoint(
                distance_m=float(sample.distance_m),
                x=x,
                y=y,
                display_x=x_offset + ((x - x_min) / scale * 100.0),
                display_y=100.0 - (y_offset + ((y - y_min) / scale * 100.0)),
            )
        )
    return points


def _downsample(
    samples: list[CanonicalTrackGeometryPoint],
    *,
    max_points: int,
) -> list[CanonicalTrackGeometryPoint]:
    if len(samples) <= max_points:
        return samples
    step = (len(samples) - 1) / (max_points - 1)
    indices = sorted({round(index * step) for index in range(max_points)})
    return [samples[index] for index in indices]


def _selected_segment(
    config: ChartRecipeConfig,
    points: list[TrackMapPoint],
    distance_bounds: dict[str, float | bool],
    corners: list[TrackMapCorner],
) -> TrackMapSegment:
    distance_range = parameter_value(
        config,
        "distance_range_m",
        section_name="analysis",
    )
    minimum = float(distance_bounds["minimum"])
    maximum = float(distance_bounds["maximum"])
    source = "full_lap"
    start = minimum
    end = maximum
    if isinstance(distance_range, dict):
        if distance_range.get("start") is not None:
            start = float(distance_range["start"])
        if distance_range.get("end") is not None:
            end = float(distance_range["end"])
        source = "saved_distance_range"

    selection = section(config, "selection")
    track_segment = selection.get("track_segment")
    corner_metadata: dict[str, Any] | None = None
    if isinstance(track_segment, dict):
        source = str(track_segment.get("source") or source)
        raw_corner = track_segment.get("corner")
        if isinstance(raw_corner, dict):
            corner_metadata = raw_corner

    if source == "corner_selector" and corner_metadata is not None:
        label = str(corner_metadata.get("label") or "")
        if label and not any(corner.label == label for corner in corners):
            source = "saved_distance_range"

    start = min(max(start, minimum), maximum)
    end = min(max(end, minimum), maximum)
    if end < start:
        start, end = end, start
    return TrackMapSegment(
        start_distance_m=start,
        end_distance_m=end,
        source=source,
        start_marker=_marker_at_distance(points, start),
        end_marker=_marker_at_distance(points, end),
        corner=corner_metadata if source == "corner_selector" else None,
    )


def _project_corners(
    dataset: SessionDataset,
    points: list[TrackMapPoint],
) -> tuple[list[TrackMapCorner], list[dict[str, Any]]]:
    circuit_info = dataset.circuit_info
    if circuit_info is None or not circuit_info.corners:
        return [], [
            {
                "field": "corners",
                "message": "FastF1 circuit corner metadata is unavailable in the loaded snapshot",
            }
        ]

    corners: list[TrackMapCorner] = []
    for corner in circuit_info.corners:
        projected = _project_corner(corner, points)
        corners.append(projected)
    available = [corner for corner in corners if corner.projection_status != "unavailable"]
    if not available:
        return corners, [
            {
                "field": "corners",
                "message": "FastF1 circuit corners could not be projected onto the loaded track geometry",
            }
        ]
    return corners, []


def _project_corner(
    corner: CircuitCorner,
    points: list[TrackMapPoint],
) -> TrackMapCorner:
    if corner.distance_m is not None:
        marker = _marker_at_distance(points, corner.distance_m)
        return TrackMapCorner(
            label=corner.label,
            number=corner.number,
            letter=corner.letter,
            distance_m=marker.distance_m,
            display_x=marker.display_x,
            display_y=marker.display_y,
            source_x=corner.x,
            source_y=corner.y,
            source_distance_m=corner.distance_m,
            projection_status="fastf1_distance",
        )

    if not points:
        return TrackMapCorner(
            label=corner.label,
            number=corner.number,
            letter=corner.letter,
            source_x=corner.x,
            source_y=corner.y,
            projection_status="unavailable",
        )

    nearest = min(
        points,
        key=lambda point: ((point.x - corner.x) ** 2) + ((point.y - corner.y) ** 2),
    )
    return TrackMapCorner(
        label=corner.label,
        number=corner.number,
        letter=corner.letter,
        distance_m=nearest.distance_m,
        display_x=nearest.display_x,
        display_y=nearest.display_y,
        source_x=corner.x,
        source_y=corner.y,
        projection_status="nearest_geometry",
        projection_error=(
            ((nearest.x - corner.x) ** 2) + ((nearest.y - corner.y) ** 2)
        )
        ** 0.5,
    )


def _marker_at_distance(points: list[TrackMapPoint], distance: float) -> TrackMapMarker:
    ordered = sorted(points, key=lambda point: point.distance_m)
    if distance <= ordered[0].distance_m:
        point = ordered[0]
        return TrackMapMarker(
            distance_m=distance,
            display_x=point.display_x,
            display_y=point.display_y,
        )
    if distance >= ordered[-1].distance_m:
        point = ordered[-1]
        return TrackMapMarker(
            distance_m=distance,
            display_x=point.display_x,
            display_y=point.display_y,
        )
    for left, right in zip(ordered, ordered[1:], strict=False):
        if left.distance_m <= distance <= right.distance_m:
            span = right.distance_m - left.distance_m
            ratio = 0.0 if span == 0 else (distance - left.distance_m) / span
            return TrackMapMarker(
                distance_m=distance,
                display_x=left.display_x + ((right.display_x - left.display_x) * ratio),
                display_y=left.display_y + ((right.display_y - left.display_y) * ratio),
            )
    point = ordered[-1]
    return TrackMapMarker(
        distance_m=distance,
        display_x=point.display_x,
        display_y=point.display_y,
    )


def _bounds(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"available": False, "minimum": None, "maximum": None}
    return {"available": True, "minimum": min(values), "maximum": max(values)}
