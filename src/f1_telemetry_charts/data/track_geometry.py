"""Canonical session-level track geometry derived from telemetry position data."""

from __future__ import annotations

from collections import defaultdict
from math import isfinite

from f1_telemetry_charts.data.models import (
    SessionDataset,
    TelemetrySample,
    TrackGeometry,
    TrackGeometryBounds,
    TrackGeometryPoint,
)

MAX_CANONICAL_TRACK_GEOMETRY_POINTS = 2000


def ensure_track_geometry(dataset: SessionDataset) -> SessionDataset:
    if dataset.track_geometry is not None:
        return dataset
    track_geometry = derive_canonical_track_geometry(dataset)
    if track_geometry is None:
        return dataset
    return dataset.model_copy(update={"track_geometry": track_geometry}, deep=True)


def derive_canonical_track_geometry(
    dataset: SessionDataset,
    *,
    max_points: int = MAX_CANONICAL_TRACK_GEOMETRY_POINTS,
) -> TrackGeometry | None:
    grouped: dict[tuple[str, int], list[TelemetrySample]] = defaultdict(list)
    for sample in dataset.telemetry:
        if _valid_position(sample):
            grouped[(sample.driver, sample.lap_number)].append(sample)

    candidates = [
        ((driver, lap_number), sorted(samples, key=lambda sample: sample.distance_m))
        for (driver, lap_number), samples in grouped.items()
        if _distance_span(samples) > 0
    ]
    if not candidates:
        return None

    driver_order = {
        driver.abbreviation: index for index, driver in enumerate(dataset.drivers)
    }
    (source_driver, source_lap), source_samples = max(
        candidates,
        key=lambda item: _trace_score(item, driver_order),
    )
    stored_points = _downsample(source_samples, max_points=max(2, int(max_points)))
    points = [
        TrackGeometryPoint(
            distance_m=float(sample.distance_m),
            x=float(sample.x),
            y=float(sample.y),
        )
        for sample in stored_points
        if sample.x is not None and sample.y is not None
    ]
    if len(points) < 2:
        return None

    return TrackGeometry(
        source="telemetry_position",
        reason="best_positioned_lap_by_distance_span",
        source_driver=source_driver,
        source_lap=source_lap,
        points=points,
        original_sample_count=len(source_samples),
        point_count=len(points),
        downsampled=len(points) < len(source_samples),
        distance_bounds=_bounds([point.distance_m for point in points]),
        x_bounds=_bounds([point.x for point in points]),
        y_bounds=_bounds([point.y for point in points]),
    )


def _valid_position(sample: TelemetrySample) -> bool:
    return (
        sample.x is not None
        and sample.y is not None
        and isfinite(float(sample.x))
        and isfinite(float(sample.y))
        and isfinite(float(sample.distance_m))
    )


def _distance_span(samples: list[TelemetrySample]) -> float:
    distances = [sample.distance_m for sample in samples]
    return max(distances) - min(distances) if len(distances) >= 2 else 0.0


def _trace_score(
    item: tuple[tuple[str, int], list[TelemetrySample]],
    driver_order: dict[str, int],
) -> tuple[float, int, int, int]:
    (driver, lap_number), samples = item
    return (
        _distance_span(samples),
        len(samples),
        -driver_order.get(driver, len(driver_order)),
        -lap_number,
    )


def _downsample(
    samples: list[TelemetrySample],
    *,
    max_points: int,
) -> list[TelemetrySample]:
    if len(samples) <= max_points:
        return samples
    step = (len(samples) - 1) / (max_points - 1)
    indices = sorted({round(index * step) for index in range(max_points)})
    return [samples[index] for index in indices]


def _bounds(values: list[float]) -> TrackGeometryBounds:
    return TrackGeometryBounds(minimum=min(values), maximum=max(values))
