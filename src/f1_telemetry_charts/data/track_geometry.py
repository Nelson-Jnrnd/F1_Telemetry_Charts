"""Canonical session-level track geometry derived from telemetry position data."""

from __future__ import annotations

from collections import defaultdict
from math import hypot, isfinite
from statistics import median

from f1_telemetry_charts.data.models import (
    LapRecord,
    SessionDataset,
    TelemetrySample,
    TrackGeometry,
    TrackGeometryBounds,
    TrackGeometryPoint,
)

MAX_CANONICAL_TRACK_GEOMETRY_POINTS = 2000
TRACK_GEOMETRY_ALGORITHM_VERSION = 2
DEFAULT_AGGREGATED_TRACK_GEOMETRY_POINTS = 200
FULL_LAP_COVERAGE_RATIO = 0.97
MINIMUM_PREFERRED_LAPS = 3
SEAM_BLEND_FRACTION = 0.05


def ensure_track_geometry(dataset: SessionDataset) -> SessionDataset:
    if (
        dataset.track_geometry is not None
        and dataset.track_geometry.algorithm_version >= TRACK_GEOMETRY_ALGORITHM_VERSION
    ):
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
    accepted = _accepted_median_traces(candidates, dataset)
    if len(accepted) >= 2:
        return _median_geometry(accepted, max_points=max_points)

    (source_driver, source_lap), source_samples = max(
        candidates,
        key=lambda item: _trace_score(item, driver_order),
    )
    stored_points = _downsample(source_samples, max_points=max(2, int(max_points)))
    raw_points = [
        TrackGeometryPoint(
            distance_m=float(sample.distance_m),
            x=float(sample.x),
            y=float(sample.y),
        )
        for sample in stored_points
        if sample.x is not None and sample.y is not None
    ]
    points, closure_gap, closure_adjusted = _close_loop(raw_points)
    if len(points) < 2:
        return None

    return TrackGeometry(
        source="telemetry_position",
        reason="best_positioned_lap_by_distance_span",
        algorithm_version=TRACK_GEOMETRY_ALGORITHM_VERSION,
        aggregation_method="single_best_lap",
        source_driver=source_driver,
        source_lap=source_lap,
        contributing_driver_count=1,
        contributing_lap_count=1,
        original_closure_gap=closure_gap,
        closure_adjusted=closure_adjusted,
        points=points,
        original_sample_count=len(source_samples),
        point_count=len(points),
        downsampled=len(points) < len(source_samples),
        distance_bounds=_bounds([point.distance_m for point in points]),
        x_bounds=_bounds([point.x for point in points]),
        y_bounds=_bounds([point.y for point in points]),
    )


def _accepted_median_traces(
    candidates: list[tuple[tuple[str, int], list[TelemetrySample]]],
    dataset: SessionDataset,
) -> list[tuple[tuple[str, int], list[TelemetrySample]]]:
    longest_spans = sorted(
        (_distance_span(samples) for _, samples in candidates),
        reverse=True,
    )[:5]
    reference_span = float(median(longest_spans))
    minimum_span = reference_span * FULL_LAP_COVERAGE_RATIO
    full_coverage = [
        candidate
        for candidate in candidates
        if _distance_span(candidate[1]) >= minimum_span
    ]
    laps = {(lap.driver, lap.lap_number): lap for lap in dataset.laps}
    quality = [
        candidate
        for candidate in full_coverage
        if _acceptable_lap(laps.get(candidate[0]), require_green=False)
    ]
    preferred = [
        candidate
        for candidate in quality
        if _acceptable_lap(laps.get(candidate[0]), require_green=True)
    ]
    return preferred if len(preferred) >= MINIMUM_PREFERRED_LAPS else quality


def _acceptable_lap(lap: LapRecord | None, *, require_green: bool) -> bool:
    if lap is None:
        return False
    if (
        lap.lap_time_seconds is None
        or lap.lap_time_seconds <= 0
        or lap.is_pit_in_lap
        or lap.is_pit_out_lap
        or lap.is_deleted
        or lap.is_generated
        or lap.is_accurate is False
    ):
        return False
    if not require_green:
        return True
    status = str(lap.track_status or "").strip()
    return not status or set(status) == {"1"}


def _median_geometry(
    accepted: list[tuple[tuple[str, int], list[TelemetrySample]]],
    *,
    max_points: int,
) -> TrackGeometry:
    point_limit = max(2, int(max_points))
    grid_count = min(
        point_limit,
        max(
            DEFAULT_AGGREGATED_TRACK_GEOMETRY_POINTS,
            max(len(samples) for _, samples in accepted),
        ),
    )
    traces_by_driver: dict[str, list[list[tuple[float, float]]]] = defaultdict(list)
    for (driver, _), samples in accepted:
        traces_by_driver[driver].append(_resample_trace(samples, grid_count=grid_count))

    driver_traces: list[list[tuple[float, float]]] = []
    for driver in sorted(traces_by_driver):
        traces = traces_by_driver[driver]
        driver_traces.append(
            [
                (
                    float(median(trace[index][0] for trace in traces)),
                    float(median(trace[index][1] for trace in traces)),
                )
                for index in range(grid_count)
            ]
        )

    session_trace = [
        (
            float(median(trace[index][0] for trace in driver_traces)),
            float(median(trace[index][1] for trace in driver_traces)),
        )
        for index in range(grid_count)
    ]
    distance_origin = float(
        median(min(sample.distance_m for sample in samples) for _, samples in accepted)
    )
    track_length = float(median(_distance_span(samples) for _, samples in accepted))
    raw_points = [
        TrackGeometryPoint(
            distance_m=distance_origin + (track_length * (index / (grid_count - 1))),
            x=coordinates[0],
            y=coordinates[1],
        )
        for index, coordinates in enumerate(session_trace)
    ]
    points, closure_gap, closure_adjusted = _close_loop(raw_points)
    original_sample_count = sum(len(samples) for _, samples in accepted)
    return TrackGeometry(
        source="telemetry_position_median",
        reason="median_of_clean_full_coverage_positioned_laps",
        algorithm_version=TRACK_GEOMETRY_ALGORITHM_VERSION,
        aggregation_method="per_driver_then_session_coordinate_median",
        source_driver=None,
        source_lap=None,
        contributing_driver_count=len(traces_by_driver),
        contributing_lap_count=len(accepted),
        original_closure_gap=closure_gap,
        closure_adjusted=closure_adjusted,
        points=points,
        original_sample_count=original_sample_count,
        point_count=len(points),
        downsampled=len(points) < original_sample_count,
        distance_bounds=_bounds([point.distance_m for point in points]),
        x_bounds=_bounds([point.x for point in points]),
        y_bounds=_bounds([point.y for point in points]),
    )


def _resample_trace(
    samples: list[TelemetrySample],
    *,
    grid_count: int,
) -> list[tuple[float, float]]:
    ordered = sorted(samples, key=lambda sample: sample.distance_m)
    start = float(ordered[0].distance_m)
    span = float(ordered[-1].distance_m) - start
    targets = [start + span * (index / (grid_count - 1)) for index in range(grid_count)]
    result: list[tuple[float, float]] = []
    right_index = 1
    for target in targets:
        while right_index < len(ordered) - 1 and ordered[right_index].distance_m < target:
            right_index += 1
        left = ordered[right_index - 1]
        right = ordered[right_index]
        distance_span = float(right.distance_m) - float(left.distance_m)
        ratio = 0.0 if distance_span == 0 else (target - float(left.distance_m)) / distance_span
        left_x, left_y = float(left.x), float(left.y)
        result.append(
            (
                left_x + ((float(right.x) - left_x) * ratio),
                left_y + ((float(right.y) - left_y) * ratio),
            )
        )
    return result


def _close_loop(
    points: list[TrackGeometryPoint],
) -> tuple[list[TrackGeometryPoint], float, bool]:
    if len(points) < 2:
        return points, 0.0, False
    first = points[0]
    last = points[-1]
    delta_x = last.x - first.x
    delta_y = last.y - first.y
    closure_gap = hypot(delta_x, delta_y)
    distance_span = last.distance_m - first.distance_m
    if distance_span <= 0:
        return points, closure_gap, False

    adjusted: list[TrackGeometryPoint] = []
    for point in points:
        progress = (point.distance_m - first.distance_m) / distance_span
        correction_x = 0.0
        correction_y = 0.0
        if progress <= SEAM_BLEND_FRACTION:
            weight = _smoothstep(1.0 - (progress / SEAM_BLEND_FRACTION))
            correction_x = delta_x * 0.5 * weight
            correction_y = delta_y * 0.5 * weight
        elif progress >= 1.0 - SEAM_BLEND_FRACTION:
            weight = _smoothstep(
                (progress - (1.0 - SEAM_BLEND_FRACTION)) / SEAM_BLEND_FRACTION
            )
            correction_x = -delta_x * 0.5 * weight
            correction_y = -delta_y * 0.5 * weight
        adjusted.append(
            TrackGeometryPoint(
                distance_m=point.distance_m,
                x=point.x + correction_x,
                y=point.y + correction_y,
            )
        )
    return adjusted, closure_gap, closure_gap > 0.0


def _smoothstep(value: float) -> float:
    bounded = min(max(value, 0.0), 1.0)
    return bounded * bounded * (3.0 - (2.0 * bounded))


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
