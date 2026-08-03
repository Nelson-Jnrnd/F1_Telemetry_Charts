"""Snapshot-derived timestamp playback payloads for Analysis Workbench maps."""

from __future__ import annotations

from collections import defaultdict
from math import isfinite
from statistics import median
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from f1_telemetry_charts.analysis.track_map import (
    DEFAULT_TRACK_MAP_POINT_LIMIT,
    MAX_TRACK_MAP_POINT_LIMIT,
    TrackMapPoint,
    _marker_at_distance,
    _project_points,
)
from f1_telemetry_charts.data.models import (
    LapRecord,
    SessionDataset,
    TelemetrySample,
    TimingAppRecord,
    TimingStreamRecord,
)
from f1_telemetry_charts.recipes.parameters import (
    _normalized_hex_color,
    deterministic_fallback_color,
)


PlaybackMode = Literal["time", "lap"]
PlaybackStatus = Literal["available", "unavailable", "invalid"]
MarkerStatus = Literal["active", "stale", "missing"]

DEFAULT_PLAYBACK_FRAME_LIMIT = 12
MAX_PLAYBACK_FRAME_LIMIT = 60
DEFAULT_PLAYBACK_MARKER_LIMIT = 30
MAX_PLAYBACK_MARKER_LIMIT = 60
DEFAULT_MAXIMUM_SAMPLE_GAP_SECONDS = 5.0
DEFAULT_MAXIMUM_TIMING_SAMPLE_AGE_SECONDS = 10.0
TARGET_MINI_SECTOR_LENGTH_METRES = 200.0
MIN_MINI_SECTOR_COUNT = 15
MAX_MINI_SECTOR_COUNT = 40


class PlaybackModeAvailability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool
    minimum: float | None = None
    maximum: float | None = None
    default: float | None = None
    reason: str | None = None


class LeaderLapMarker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lap_number: int = Field(ge=1)
    session_time_seconds: float = Field(ge=0)
    leader_driver: str = Field(min_length=1)


class PlaybackCursor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: PlaybackMode
    session_time_seconds: float = Field(ge=0)
    leader_lap_number: int | None = None
    leader_driver: str | None = None
    lap_offset_seconds: float | None = None


class PlaybackMarkerContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lap_number: int | None = None
    lap_time_seconds: float | None = None
    position: int | None = None
    compound: str | None = None
    stint: int | None = None
    tyre_age_laps: float | None = None
    last_lap_time_seconds: float | None = None
    best_lap_time_seconds: float | None = None
    last_sector_times_seconds: list[float | None] = Field(default_factory=list)
    best_sector_times_seconds: list[float | None] = Field(default_factory=list)
    mini_sector_states: list[Literal["fastest", "faster", "slower", "unavailable"]] = Field(
        default_factory=list
    )
    mini_sector_groups: list[Literal[0, 1, 2, 3]] = Field(default_factory=list)
    timing_app_source: str | None = None
    track_status: str | None = None
    pit_state: Literal["pit_in", "pit_out", "pit_in_out", "none"] = "none"
    gap_to_leader_seconds: float | None = None
    interval_to_ahead_seconds: float | None = None
    gap_to_leader_laps: int | None = None
    interval_to_ahead_laps: int | None = None
    gap_source: str | None = None
    gap_inferred: bool = False
    timing_status: Literal["fresh", "stale", "missing"] = "missing"
    timing_sample_age_seconds: float | None = None
    timing_position: int | None = None


class PlaybackMarker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    driver: str
    status: MarkerStatus
    reason: str | None = None
    distance_m: float | None = None
    display_x: float | None = Field(default=None, ge=0, le=100)
    display_y: float | None = Field(default=None, ge=0, le=100)
    color: str | None = None
    source_lap: int | None = None
    source_sample_count: int = 0
    interpolation_method: Literal["exact", "linear", "nearest", "missing"] = "missing"
    interpolation_status: Literal["exact", "interpolated", "stale", "missing"] = "missing"
    sample_gap_seconds: float | None = None
    context: PlaybackMarkerContext = Field(default_factory=PlaybackMarkerContext)


class PlaybackFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: PlaybackMode
    cursor_value: float
    cursor: PlaybackCursor
    lap_number: int | None = None
    session_time_seconds: float
    markers: list[PlaybackMarker] = Field(default_factory=list)
    context: dict[str, object] = Field(default_factory=dict)


class PlaybackPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PlaybackStatus
    session_id: str | None = None
    mode: PlaybackMode = "lap"
    default_mode: PlaybackMode = "lap"
    available_modes: dict[str, PlaybackModeAvailability] = Field(default_factory=dict)
    selected_drivers: list[str] = Field(default_factory=list)
    points: list[TrackMapPoint] = Field(default_factory=list)
    leader_lap_markers: list[LeaderLapMarker] = Field(default_factory=list)
    frames: list[PlaybackFrame] = Field(default_factory=list)
    bounds: dict[str, object] = Field(default_factory=dict)
    metadata: dict[str, object] = Field(default_factory=dict)
    diagnostics: list[dict[str, object]] = Field(default_factory=list)


def build_playback_payload(
    dataset: SessionDataset,
    *,
    session_id: str | None = None,
    mode: PlaybackMode = "lap",
    cursor: float | None = None,
    start_lap: int | None = None,
    end_lap: int | None = None,
    selected_drivers: list[str] | None = None,
    max_frames: int = DEFAULT_PLAYBACK_FRAME_LIMIT,
    max_markers: int = DEFAULT_PLAYBACK_MARKER_LIMIT,
    max_points: int = DEFAULT_TRACK_MAP_POINT_LIMIT,
    maximum_sample_gap_seconds: float = DEFAULT_MAXIMUM_SAMPLE_GAP_SECONDS,
    maximum_timing_sample_age_seconds: float = DEFAULT_MAXIMUM_TIMING_SAMPLE_AGE_SECONDS,
) -> PlaybackPayload:
    frame_limit = min(max(1, int(max_frames)), MAX_PLAYBACK_FRAME_LIMIT)
    marker_limit = min(max(1, int(max_markers)), MAX_PLAYBACK_MARKER_LIMIT)
    point_limit = min(max(2, int(max_points)), MAX_TRACK_MAP_POINT_LIMIT)
    drivers = _selected_drivers(dataset, selected_drivers)[:marker_limit]
    leader_markers = _leader_lap_markers(dataset.laps)
    available_modes = playback_availability(dataset, leader_markers)

    if not available_modes.get(mode, PlaybackModeAvailability(available=False)).available:
        reason = (
            available_modes.get(mode).reason
            if available_modes.get(mode) is not None
            else f"{mode} playback is unavailable"
        )
        return PlaybackPayload(
            status="unavailable",
            session_id=session_id,
            mode=mode,
            available_modes=available_modes,
            selected_drivers=drivers,
            leader_lap_markers=leader_markers,
            diagnostics=[{"field": "mode", "message": reason or f"{mode} playback is unavailable"}],
        )

    if dataset.track_geometry is None or dataset.track_geometry.point_count < 2:
        return PlaybackPayload(
            status="unavailable",
            session_id=session_id,
            mode=mode,
            available_modes=available_modes,
            selected_drivers=drivers,
            leader_lap_markers=leader_markers,
            diagnostics=[
                {
                    "field": "track_map",
                    "message": "Session track geometry is unavailable in the loaded snapshot",
                }
            ],
        )

    source_points = sorted(dataset.track_geometry.points, key=lambda point: point.distance_m)
    points = _project_points(source_points, max_points=point_limit)
    sample_gap = max(0.0, float(maximum_sample_gap_seconds))
    timing_sample_age = max(0.0, float(maximum_timing_sample_age_seconds))
    cursors = _requested_cursors(
        mode,
        available_modes,
        leader_markers,
        cursor=cursor,
        start_lap=start_lap,
        end_lap=end_lap,
        max_frames=frame_limit,
    )
    laps_by_driver = _laps_by_driver(dataset.laps)
    telemetry_by_driver = _positioned_telemetry_by_driver(dataset.telemetry)
    telemetry_laps_by_driver = _telemetry_laps_by_driver(dataset.telemetry)
    timing_by_driver = _timing_by_driver(dataset.timing)
    timing_app_by_driver = _timing_app_by_driver(dataset.timing_app)
    driver_colors = _playback_driver_colors(dataset)
    frames = [
        _time_frame(
            cursor_state,
            drivers,
            points,
            laps_by_driver,
            telemetry_by_driver,
            telemetry_laps_by_driver,
            timing_by_driver,
            timing_app_by_driver,
            driver_colors,
            maximum_sample_gap_seconds=sample_gap,
            maximum_timing_sample_age_seconds=timing_sample_age,
        )
        for cursor_state in cursors
    ]
    return PlaybackPayload(
        status="available",
        session_id=session_id,
        mode=mode,
        available_modes=available_modes,
        selected_drivers=drivers,
        points=points,
        leader_lap_markers=leader_markers,
        frames=frames,
        bounds={
            "session_time": {
                "available": True,
                "minimum": available_modes["time"].minimum,
                "maximum": available_modes["time"].maximum,
            },
            "laps": {
                "available": bool(leader_markers),
                "minimum": leader_markers[0].lap_number if leader_markers else None,
                "maximum": leader_markers[-1].lap_number if leader_markers else None,
            },
            "track_distance_m": {
                "available": True,
                "minimum": source_points[0].distance_m,
                "maximum": source_points[-1].distance_m,
            },
        },
        metadata={
            "track_geometry_source": {
                "source_driver": dataset.track_geometry.source_driver,
                "source_lap": dataset.track_geometry.source_lap,
                "algorithm_version": dataset.track_geometry.algorithm_version,
                "aggregation_method": dataset.track_geometry.aggregation_method,
                "contributing_driver_count": dataset.track_geometry.contributing_driver_count,
                "contributing_lap_count": dataset.track_geometry.contributing_lap_count,
                "original_closure_gap": dataset.track_geometry.original_closure_gap,
                "closure_adjusted": dataset.track_geometry.closure_adjusted,
                "original_sample_count": dataset.track_geometry.original_sample_count,
                "point_count": len(points),
                "downsampled": dataset.track_geometry.downsampled or len(points) < len(source_points),
            },
            "interpolation": {
                "method": "timestamp_linear",
                "maximum_sample_gap_seconds": sample_gap,
            },
            "timing": {
                "source": "fastf1_timing_data",
                "record_count": len(dataset.timing),
                "maximum_sample_age_seconds": timing_sample_age,
            },
            "timing_app": {
                "source": "fastf1_timing_app_data",
                "record_count": len(dataset.timing_app),
            },
        },
    )


def playback_availability(
    dataset: SessionDataset,
    leader_markers: list[LeaderLapMarker] | None = None,
) -> dict[str, PlaybackModeAvailability]:
    positioned_times = [
        sample.session_time_seconds
        for sample in dataset.telemetry
        if sample.session_time_seconds is not None
        and sample.x is not None
        and sample.y is not None
    ]
    has_time = bool(positioned_times)
    markers = leader_markers if leader_markers is not None else _leader_lap_markers(dataset.laps)
    return {
        "time": PlaybackModeAvailability(
            available=has_time,
            minimum=float(min(positioned_times)) if has_time else None,
            maximum=float(max(positioned_times)) if has_time else None,
            default=markers[0].session_time_seconds
            if markers
            else float(min(positioned_times))
            if has_time
            else None,
            reason=None
            if has_time
            else "Timestamp playback requires time-indexed position samples in the loaded snapshot",
        ),
        "lap": PlaybackModeAvailability(
            available=has_time and bool(markers),
            minimum=float(markers[0].lap_number) if markers else None,
            maximum=float(markers[-1].lap_number) if markers else None,
            default=float(markers[0].lap_number) if markers else None,
            reason=None
            if has_time and markers
            else "Lap playback requires leader lap-start timestamps and time-indexed position samples",
        ),
    }


def playback_summary(dataset: SessionDataset) -> dict[str, object]:
    leader_markers = _leader_lap_markers(dataset.laps)
    availability = playback_availability(dataset, leader_markers)
    track_geometry = dataset.track_geometry
    return {
        "available": availability["time"].available
        and track_geometry is not None
        and track_geometry.point_count >= 2,
        "default_mode": "lap",
        "modes": {key: value.model_dump(mode="json") for key, value in availability.items()},
        "leader_lap_count": len(leader_markers),
        "positioned_sample_count": len(
            [
                sample
                for sample in dataset.telemetry
                if sample.session_time_seconds is not None
                and sample.x is not None
                and sample.y is not None
            ]
        ),
        "track_map_available": track_geometry is not None and track_geometry.point_count >= 2,
    }


def _requested_cursors(
    mode: PlaybackMode,
    available_modes: dict[str, PlaybackModeAvailability],
    leader_markers: list[LeaderLapMarker],
    *,
    cursor: float | None,
    start_lap: int | None,
    end_lap: int | None,
    max_frames: int,
) -> list[PlaybackCursor]:
    if mode == "lap":
        if start_lap is not None or end_lap is not None:
            start = int(start_lap if start_lap is not None else leader_markers[0].lap_number)
            end = int(end_lap if end_lap is not None else start)
            if end < start:
                start, end = end, start
            selected = [
                marker
                for marker in leader_markers
                if start <= marker.lap_number <= end
            ][:max_frames]
        else:
            lap_number = int(round(cursor if cursor is not None else leader_markers[0].lap_number))
            selected = [_nearest_leader_lap(leader_markers, lap_number)]
        return [_cursor_from_leader_marker(marker) for marker in selected]

    time_bounds = available_modes["time"]
    minimum = float(time_bounds.minimum or 0)
    maximum = float(time_bounds.maximum or minimum)
    session_time = min(max(float(cursor if cursor is not None else time_bounds.default or minimum), minimum), maximum)
    return [_cursor_from_time(session_time, leader_markers)]


def _time_frame(
    cursor_state: PlaybackCursor,
    drivers: list[str],
    points: list[TrackMapPoint],
    laps_by_driver: dict[str, dict[int, LapRecord]],
    telemetry_by_driver: dict[str, list[TelemetrySample]],
    telemetry_laps_by_driver: dict[str, dict[int, list[TelemetrySample]]],
    timing_by_driver: dict[str, list[TimingStreamRecord]],
    timing_app_by_driver: dict[str, list[TimingAppRecord]],
    driver_colors: dict[str, str],
    *,
    maximum_sample_gap_seconds: float,
    maximum_timing_sample_age_seconds: float,
) -> PlaybackFrame:
    markers = [
        _marker_at_time(
            driver,
            cursor_state.session_time_seconds,
            points,
            laps_by_driver.get(driver, {}),
            telemetry_by_driver.get(driver, []),
            driver_colors.get(driver),
            maximum_sample_gap_seconds=maximum_sample_gap_seconds,
        )
        for driver in drivers
    ]
    markers = _markers_with_timing(
        markers,
        cursor_state.session_time_seconds,
        timing_by_driver,
        maximum_timing_sample_age_seconds=maximum_timing_sample_age_seconds,
    )
    mini_sector_states, mini_sector_groups = _mini_sector_snapshot(
        cursor_state.session_time_seconds,
        drivers,
        laps_by_driver,
        telemetry_laps_by_driver,
        track_length_metres=max((point.distance_m for point in points), default=0.0),
    )
    markers = _markers_with_analyst_context(
        markers,
        cursor_state.session_time_seconds,
        laps_by_driver,
        timing_app_by_driver,
        mini_sector_states,
        mini_sector_groups,
    )
    track_statuses = sorted(
        {
            marker.context.track_status
            for marker in markers
            if marker.context.track_status
        }
    )
    return PlaybackFrame(
        mode=cursor_state.mode,
        cursor_value=cursor_state.session_time_seconds,
        cursor=cursor_state,
        lap_number=cursor_state.leader_lap_number,
        session_time_seconds=cursor_state.session_time_seconds,
        markers=markers,
        context={
            "track_status": ",".join(track_statuses) if track_statuses else None,
            "classified_driver_count": len(
                [marker for marker in markers if marker.context.position is not None]
            ),
        },
    )


def _marker_at_time(
    driver: str,
    session_time: float,
    points: list[TrackMapPoint],
    laps_by_number: dict[int, LapRecord],
    samples: list[TelemetrySample],
    color: str | None,
    *,
    maximum_sample_gap_seconds: float,
) -> PlaybackMarker:
    if not samples:
        return PlaybackMarker(
            driver=driver,
            status="missing",
            reason="Time-indexed position telemetry is unavailable for this driver",
            color=_driver_color(driver, color),
            context=_context(_lap_at_time(laps_by_number, session_time)),
        )

    before = None
    after = None
    for sample in samples:
        sample_time = sample.session_time_seconds
        if sample_time is None:
            continue
        if sample_time <= session_time:
            before = sample
        if sample_time >= session_time:
            after = sample
            break

    if before is not None and before.session_time_seconds == session_time:
        return _sample_marker(
            driver,
            before,
            points,
            laps_by_number,
            color,
            status="active",
            interpolation_method="exact",
            interpolation_status="exact",
            sample_gap_seconds=0.0,
            source_sample_count=len(samples),
        )
    if after is not None and after.session_time_seconds == session_time:
        return _sample_marker(
            driver,
            after,
            points,
            laps_by_number,
            color,
            status="active",
            interpolation_method="exact",
            interpolation_status="exact",
            sample_gap_seconds=0.0,
            source_sample_count=len(samples),
        )
    if before is not None and after is not None:
        before_time = float(before.session_time_seconds or 0)
        after_time = float(after.session_time_seconds or before_time)
        gap = after_time - before_time
        if gap <= maximum_sample_gap_seconds:
            ratio = 0.0 if gap <= 0 else (session_time - before_time) / gap
            distance = before.distance_m + ((after.distance_m - before.distance_m) * ratio)
            marker = _marker_at_distance(points, distance)
            source_lap = before.lap_number if ratio < 0.5 else after.lap_number
            return PlaybackMarker(
                driver=driver,
                status="active",
                distance_m=distance,
                display_x=marker.display_x,
                display_y=marker.display_y,
                color=_driver_color(driver, color),
                source_lap=source_lap,
                source_sample_count=len(samples),
                interpolation_method="linear",
                interpolation_status="interpolated",
                sample_gap_seconds=gap,
                context=_context(_lap_at_time(laps_by_number, session_time)),
            )

    nearest = min(
        samples,
        key=lambda sample: abs(float(sample.session_time_seconds or 0) - session_time),
    )
    nearest_gap = abs(float(nearest.session_time_seconds or 0) - session_time)
    if nearest_gap <= maximum_sample_gap_seconds:
        return _sample_marker(
            driver,
            nearest,
            points,
            laps_by_number,
            color,
            status="stale",
            reason="Nearest time-indexed position sample used",
            interpolation_method="nearest",
            interpolation_status="stale",
            sample_gap_seconds=nearest_gap,
            source_sample_count=len(samples),
        )
    return PlaybackMarker(
        driver=driver,
        status="missing",
        reason="No position sample is close enough to the playback timestamp",
        color=_driver_color(driver, color),
        source_lap=nearest.lap_number,
        source_sample_count=len(samples),
        interpolation_method="missing",
        interpolation_status="missing",
        sample_gap_seconds=nearest_gap,
        context=_context(_lap_at_time(laps_by_number, session_time)),
    )


def _sample_marker(
    driver: str,
    sample: TelemetrySample,
    points: list[TrackMapPoint],
    laps_by_number: dict[int, LapRecord],
    color: str | None,
    *,
    status: MarkerStatus,
    interpolation_method: Literal["exact", "linear", "nearest", "missing"],
    interpolation_status: Literal["exact", "interpolated", "stale", "missing"],
    sample_gap_seconds: float,
    source_sample_count: int,
    reason: str | None = None,
) -> PlaybackMarker:
    marker = _marker_at_distance(points, sample.distance_m)
    return PlaybackMarker(
        driver=driver,
        status=status,
        reason=reason,
        distance_m=sample.distance_m,
        display_x=marker.display_x,
        display_y=marker.display_y,
        color=_driver_color(driver, color),
        source_lap=sample.lap_number,
        source_sample_count=source_sample_count,
        interpolation_method=interpolation_method,
        interpolation_status=interpolation_status,
        sample_gap_seconds=sample_gap_seconds,
        context=_context(_lap_at_time(laps_by_number, float(sample.session_time_seconds or 0))),
    )


def _leader_lap_markers(laps: list[LapRecord]) -> list[LeaderLapMarker]:
    by_lap: dict[int, list[LapRecord]] = defaultdict(list)
    for lap in laps:
        if lap.lap_start_time_seconds is None:
            continue
        by_lap[lap.lap_number].append(lap)
    markers: list[LeaderLapMarker] = []
    for lap_number in sorted(by_lap):
        candidates = sorted(
            by_lap[lap_number],
            key=lambda lap: (
                lap.position if lap.position is not None else 999,
                lap.lap_start_time_seconds if lap.lap_start_time_seconds is not None else float("inf"),
                lap.driver,
            ),
        )
        leader = candidates[0]
        if leader.lap_start_time_seconds is None:
            continue
        markers.append(
            LeaderLapMarker(
                lap_number=lap_number,
                session_time_seconds=leader.lap_start_time_seconds,
                leader_driver=leader.driver,
            )
        )
    return markers


def _cursor_from_leader_marker(marker: LeaderLapMarker) -> PlaybackCursor:
    return PlaybackCursor(
        mode="lap",
        session_time_seconds=marker.session_time_seconds,
        leader_lap_number=marker.lap_number,
        leader_driver=marker.leader_driver,
        lap_offset_seconds=0.0,
    )


def _cursor_from_time(
    session_time: float,
    leader_markers: list[LeaderLapMarker],
) -> PlaybackCursor:
    previous = None
    for marker in leader_markers:
        if marker.session_time_seconds <= session_time:
            previous = marker
        else:
            break
    return PlaybackCursor(
        mode="time",
        session_time_seconds=session_time,
        leader_lap_number=previous.lap_number if previous is not None else None,
        leader_driver=previous.leader_driver if previous is not None else None,
        lap_offset_seconds=round(session_time - previous.session_time_seconds, 3)
        if previous is not None
        else None,
    )


def _nearest_leader_lap(
    leader_markers: list[LeaderLapMarker],
    lap_number: int,
) -> LeaderLapMarker:
    return min(leader_markers, key=lambda marker: abs(marker.lap_number - lap_number))


def _context(lap: LapRecord | None) -> PlaybackMarkerContext:
    if lap is None:
        return PlaybackMarkerContext()
    return PlaybackMarkerContext(
        lap_number=lap.lap_number,
        lap_time_seconds=lap.lap_time_seconds,
        position=lap.position,
        compound=lap.compound,
        stint=lap.stint,
        track_status=lap.track_status,
        pit_state=_pit_state(lap),
    )


def _markers_with_timing(
    markers: list[PlaybackMarker],
    session_time: float,
    timing_by_driver: dict[str, list[TimingStreamRecord]],
    *,
    maximum_timing_sample_age_seconds: float,
) -> list[PlaybackMarker]:
    enriched: list[PlaybackMarker] = []
    for marker in markers:
        timing, age = _timing_at_time(
            timing_by_driver.get(marker.driver, []),
            session_time,
        )
        context = marker.context
        if timing is None or age is None:
            enriched.append(
                marker.model_copy(
                    update={
                        "context": context.model_copy(
                            update={
                                "gap_source": "missing",
                                "gap_inferred": False,
                                "timing_status": "missing",
                                "timing_sample_age_seconds": None,
                                "timing_position": None,
                            }
                        )
                    }
                )
            )
            continue
        leader_anchor = timing.position == 1 and timing.gap_to_leader_seconds == 0
        timing_status = (
            "fresh"
            if leader_anchor or age <= maximum_timing_sample_age_seconds
            else "stale"
        )
        enriched.append(
            marker.model_copy(
                update={
                    "context": context.model_copy(
                        update={
                            "position": timing.position or context.position,
                            "gap_to_leader_seconds": timing.gap_to_leader_seconds,
                            "interval_to_ahead_seconds": timing.interval_to_ahead_seconds,
                            "gap_to_leader_laps": timing.gap_to_leader_laps,
                            "interval_to_ahead_laps": timing.interval_to_ahead_laps,
                            "gap_source": timing.source,
                            "gap_inferred": False,
                            "timing_status": timing_status,
                            "timing_sample_age_seconds": round(age, 3),
                            "timing_position": timing.position,
                        }
                    )
                }
            )
        )
    return sorted(enriched, key=_marker_timing_sort_key)


def _timing_at_time(
    records: list[TimingStreamRecord],
    session_time: float,
) -> tuple[TimingStreamRecord | None, float | None]:
    candidate = None
    for record in records:
        if record.session_time_seconds <= session_time:
            candidate = record
        else:
            break
    if candidate is None:
        return None, None
    return candidate, session_time - candidate.session_time_seconds


def _markers_with_analyst_context(
    markers: list[PlaybackMarker],
    session_time: float,
    laps_by_driver: dict[str, dict[int, LapRecord]],
    timing_app_by_driver: dict[str, list[TimingAppRecord]],
    mini_sector_states: dict[
        str,
        list[Literal["fastest", "faster", "slower", "unavailable"]],
    ],
    mini_sector_groups: list[Literal[0, 1, 2, 3]],
) -> list[PlaybackMarker]:
    enriched: list[PlaybackMarker] = []
    for marker in markers:
        laps = sorted(
            laps_by_driver.get(marker.driver, {}).values(),
            key=lambda lap: lap.lap_number,
        )
        completed = [
            lap
            for lap in laps
            if lap.lap_end_time_seconds is not None
            and lap.lap_end_time_seconds <= session_time
        ]
        valid_completed = [
            lap
            for lap in completed
            if lap.lap_time_seconds is not None and not lap.is_deleted
        ]
        last_lap = valid_completed[-1] if valid_completed else None
        best_lap = (
            min(valid_completed, key=lambda lap: float(lap.lap_time_seconds or float("inf")))
            if valid_completed
            else None
        )
        app = _timing_app_state_at_time(
            timing_app_by_driver.get(marker.driver, []),
            session_time,
        )
        tyre_age_laps = _tyre_age_at_time(app, laps, session_time)
        context = marker.context
        enriched.append(
            marker.model_copy(
                update={
                    "context": context.model_copy(
                        update={
                            "compound": app.get("compound") or context.compound,
                            "stint": app.get("stint")
                            if app.get("stint") is not None
                            else context.stint,
                            "tyre_age_laps": tyre_age_laps,
                            "last_lap_time_seconds": app.get("lap_time_seconds")
                            if app.get("lap_time_seconds") is not None
                            else last_lap.lap_time_seconds
                            if last_lap is not None
                            else None,
                            "best_lap_time_seconds": best_lap.lap_time_seconds
                            if best_lap is not None
                            else None,
                            "last_sector_times_seconds": _sector_times(last_lap),
                            "best_sector_times_seconds": _best_sector_times(valid_completed),
                            "timing_app_source": app.get("source"),
                            "pit_state": _pit_state_at_time(laps, session_time),
                            "mini_sector_states": mini_sector_states.get(
                                marker.driver,
                                ["unavailable"] * len(mini_sector_groups),
                            ),
                            "mini_sector_groups": mini_sector_groups,
                        }
                    )
                }
            )
        )
    return enriched


def _timing_app_state_at_time(
    records: list[TimingAppRecord],
    session_time: float,
) -> dict[str, object]:
    state: dict[str, object] = {}
    active_stint: int | None = None
    for record in records:
        if record.session_time_seconds > session_time:
            break
        if record.stint is not None and record.stint != active_stint:
            active_stint = record.stint
            state = {"stint": record.stint}
        for field in (
            "lap_number",
            "lap_time_seconds",
            "stint",
            "total_laps",
            "compound",
            "start_laps",
            "source",
        ):
            value = getattr(record, field)
            if value is not None:
                state[field] = value
    return state


def _tyre_age_at_time(
    timing_app_state: dict[str, object],
    laps: list[LapRecord],
    session_time: float,
) -> float | None:
    live_total = timing_app_state.get("total_laps")
    if isinstance(live_total, (int, float)) and isfinite(float(live_total)):
        return max(0.0, float(live_total))

    started_laps = [
        lap
        for lap in laps
        if (
            lap.lap_start_time_seconds is not None
            and lap.lap_start_time_seconds <= session_time
        )
        or (
            lap.lap_start_time_seconds is None
            and lap.lap_end_time_seconds is not None
            and lap.lap_end_time_seconds <= session_time
        )
    ]
    if not started_laps:
        return None

    active_lap = max(started_laps, key=lambda lap: lap.lap_number)
    active_stint = timing_app_state.get("stint")
    if not isinstance(active_stint, int):
        active_stint = active_lap.stint
    if active_stint is None:
        return None

    stint_lap_count = sum(
        1
        for lap in started_laps
        if lap.stint == active_stint and lap.lap_number <= active_lap.lap_number
    )
    if stint_lap_count <= 0:
        return None

    start_laps = timing_app_state.get("start_laps")
    if isinstance(start_laps, (int, float)) and isfinite(float(start_laps)):
        return max(0.0, float(start_laps) + stint_lap_count - 1)
    return float(stint_lap_count)


def _sector_times(lap: LapRecord | None) -> list[float | None]:
    if lap is None:
        return [None, None, None]
    return [
        lap.sector_1_time_seconds,
        lap.sector_2_time_seconds,
        lap.sector_3_time_seconds,
    ]


def _best_sector_times(laps: list[LapRecord]) -> list[float | None]:
    sectors = [
        [lap.sector_1_time_seconds for lap in laps if lap.sector_1_time_seconds is not None],
        [lap.sector_2_time_seconds for lap in laps if lap.sector_2_time_seconds is not None],
        [lap.sector_3_time_seconds for lap in laps if lap.sector_3_time_seconds is not None],
    ]
    return [min(values) if values else None for values in sectors]


def _mini_sector_snapshot(
    session_time: float,
    drivers: list[str],
    laps_by_driver: dict[str, dict[int, LapRecord]],
    telemetry_laps_by_driver: dict[str, dict[int, list[TelemetrySample]]],
    *,
    track_length_metres: float,
) -> tuple[
    dict[str, list[Literal["fastest", "faster", "slower", "unavailable"]]],
    list[Literal[0, 1, 2, 3]],
]:
    if not drivers or track_length_metres <= 0:
        return {}, []
    segment_count = min(
        max(
            int(round(track_length_metres / TARGET_MINI_SECTOR_LENGTH_METRES)),
            MIN_MINI_SECTOR_COUNT,
        ),
        MAX_MINI_SECTOR_COUNT,
    )
    boundaries = [
        track_length_metres * index / segment_count
        for index in range(segment_count + 1)
    ]
    times_by_driver_lap: dict[str, dict[int, list[float]]] = defaultdict(dict)
    sector_one_distances: list[float] = []
    sector_two_distances: list[float] = []

    for driver in drivers:
        laps = laps_by_driver.get(driver, {})
        for lap_number, lap in laps.items():
            if (
                lap.lap_end_time_seconds is None
                or lap.lap_end_time_seconds > session_time
                or lap.is_deleted
            ):
                continue
            samples = telemetry_laps_by_driver.get(driver, {}).get(lap_number, [])
            segment_times = _equal_distance_segment_times(
                samples,
                boundaries,
                lap_start_time=lap.lap_start_time_seconds,
                lap_end_time=lap.lap_end_time_seconds,
            )
            if segment_times is None:
                continue
            times_by_driver_lap[driver][lap_number] = segment_times
            if (
                lap.lap_start_time_seconds is not None
                and lap.sector_1_time_seconds is not None
            ):
                sector_one = _distance_at_session_time(
                    samples,
                    lap.lap_start_time_seconds + lap.sector_1_time_seconds,
                )
                if sector_one is not None:
                    sector_one_distances.append(sector_one)
            if (
                lap.lap_start_time_seconds is not None
                and lap.sector_1_time_seconds is not None
                and lap.sector_2_time_seconds is not None
            ):
                sector_two = _distance_at_session_time(
                    samples,
                    lap.lap_start_time_seconds
                    + lap.sector_1_time_seconds
                    + lap.sector_2_time_seconds,
                )
                if sector_two is not None:
                    sector_two_distances.append(sector_two)

    if not times_by_driver_lap:
        return {}, []
    sector_one_boundary = median(sector_one_distances) if sector_one_distances else None
    sector_two_boundary = median(sector_two_distances) if sector_two_distances else None
    groups: list[Literal[0, 1, 2, 3]] = []
    for index in range(segment_count):
        midpoint = (boundaries[index] + boundaries[index + 1]) / 2
        if sector_one_boundary is None or sector_two_boundary is None:
            group = 0
        else:
            group = 1 if midpoint < sector_one_boundary else 2 if midpoint < sector_two_boundary else 3
        groups.append(group)

    session_best = [
        min(
            segment_times[index]
            for laps in times_by_driver_lap.values()
            for segment_times in laps.values()
        )
        for index in range(segment_count)
    ]
    states: dict[
        str,
        list[Literal["fastest", "faster", "slower", "unavailable"]],
    ] = {}
    for driver in drivers:
        driver_laps = times_by_driver_lap.get(driver, {})
        if not driver_laps:
            states[driver] = ["unavailable"] * segment_count
            continue
        last_lap_number = max(driver_laps)
        last_times = driver_laps[last_lap_number]
        personal_best = [
            min(segment_times[index] for segment_times in driver_laps.values())
            for index in range(segment_count)
        ]
        driver_states: list[
            Literal["fastest", "faster", "slower", "unavailable"]
        ] = []
        for index, value in enumerate(last_times):
            if abs(value - session_best[index]) <= 0.001:
                driver_states.append("fastest")
            elif abs(value - personal_best[index]) <= 0.001:
                driver_states.append("faster")
            else:
                driver_states.append("slower")
        states[driver] = driver_states
    return states, groups


def _equal_distance_segment_times(
    samples: list[TelemetrySample],
    boundaries: list[float],
    *,
    lap_start_time: float | None = None,
    lap_end_time: float | None = None,
) -> list[float] | None:
    ordered = sorted(
        (
            sample
            for sample in samples
            if sample.session_time_seconds is not None
        ),
        key=lambda sample: sample.distance_m,
    )
    if len(ordered) < 2:
        return None
    if (
        lap_start_time is not None
        and ordered[0].distance_m > boundaries[0]
        and lap_start_time < float(ordered[0].session_time_seconds or 0)
    ):
        ordered.insert(
            0,
            TelemetrySample(
                driver=ordered[0].driver,
                lap_number=ordered[0].lap_number,
                distance_m=boundaries[0],
                session_time_seconds=lap_start_time,
            ),
        )
    if (
        lap_end_time is not None
        and ordered[-1].distance_m < boundaries[-1]
        and lap_end_time > float(ordered[-1].session_time_seconds or 0)
    ):
        ordered.append(
            TelemetrySample(
                driver=ordered[-1].driver,
                lap_number=ordered[-1].lap_number,
                distance_m=boundaries[-1],
                session_time_seconds=lap_end_time,
            )
        )
    if boundaries[0] < ordered[0].distance_m or boundaries[-1] > ordered[-1].distance_m:
        return None
    values: list[float] = []
    sample_index = 0
    for boundary in boundaries:
        while (
            sample_index + 1 < len(ordered)
            and ordered[sample_index + 1].distance_m < boundary
        ):
            sample_index += 1
        if sample_index + 1 >= len(ordered):
            return None
        before = ordered[sample_index]
        after = ordered[sample_index + 1]
        span = after.distance_m - before.distance_m
        ratio = 0.0 if span <= 0 else (boundary - before.distance_m) / span
        before_time = float(before.session_time_seconds or 0)
        after_time = float(after.session_time_seconds or before_time)
        values.append(before_time + (after_time - before_time) * ratio)
    durations = [
        values[index + 1] - values[index]
        for index in range(len(values) - 1)
    ]
    if any(duration <= 0 for duration in durations):
        return None
    return durations


def _distance_at_session_time(
    samples: list[TelemetrySample],
    session_time: float,
) -> float | None:
    ordered = sorted(
        (
            sample
            for sample in samples
            if sample.session_time_seconds is not None
        ),
        key=lambda sample: float(sample.session_time_seconds or 0),
    )
    for before, after in zip(ordered, ordered[1:]):
        before_time = float(before.session_time_seconds or 0)
        after_time = float(after.session_time_seconds or before_time)
        if before_time <= session_time <= after_time:
            span = after_time - before_time
            ratio = 0.0 if span <= 0 else (session_time - before_time) / span
            return before.distance_m + (after.distance_m - before.distance_m) * ratio
    return None


def _pit_state_at_time(
    laps: list[LapRecord],
    session_time: float,
) -> Literal["pit_in", "none"]:
    events: list[tuple[float, Literal["pit_in", "pit_out"]]] = []
    for lap in laps:
        if lap.pit_in_time_seconds is not None and lap.pit_in_time_seconds <= session_time:
            events.append((lap.pit_in_time_seconds, "pit_in"))
        if lap.pit_out_time_seconds is not None and lap.pit_out_time_seconds <= session_time:
            events.append((lap.pit_out_time_seconds, "pit_out"))
    if not events:
        return "none"
    _, latest = max(events, key=lambda event: (event[0], event[1] == "pit_out"))
    return "pit_in" if latest == "pit_in" else "none"


def _marker_timing_sort_key(marker: PlaybackMarker) -> tuple[int, int, float, str]:
    timing_position = marker.context.timing_position
    lap_position = marker.context.position
    position = timing_position if timing_position is not None else lap_position
    status_rank = {"active": 0, "stale": 1, "missing": 2}[marker.status]
    return (
        position if position is not None else 999,
        status_rank,
        marker.distance_m if marker.distance_m is not None else float("inf"),
        marker.driver,
    )


def _pit_state(lap: LapRecord) -> Literal["pit_in", "pit_out", "pit_in_out", "none"]:
    if lap.is_pit_in_lap and lap.is_pit_out_lap:
        return "pit_in_out"
    if lap.is_pit_in_lap:
        return "pit_in"
    if lap.is_pit_out_lap:
        return "pit_out"
    return "none"


def _selected_drivers(dataset: SessionDataset, selected_drivers: list[str] | None) -> list[str]:
    available = [driver.abbreviation for driver in dataset.drivers]
    if not selected_drivers:
        return available
    requested = [driver for driver in selected_drivers if driver in available]
    return requested or available


def _laps_by_driver(laps: list[LapRecord]) -> dict[str, dict[int, LapRecord]]:
    grouped: dict[str, dict[int, LapRecord]] = defaultdict(dict)
    for lap in laps:
        grouped[lap.driver][lap.lap_number] = lap
    return grouped


def _timing_by_driver(
    records: list[TimingStreamRecord],
) -> dict[str, list[TimingStreamRecord]]:
    grouped: dict[str, list[TimingStreamRecord]] = defaultdict(list)
    for record in sorted(records, key=lambda item: (item.driver, item.session_time_seconds)):
        grouped[record.driver].append(record)
    return grouped


def _timing_app_by_driver(
    records: list[TimingAppRecord],
) -> dict[str, list[TimingAppRecord]]:
    grouped: dict[str, list[TimingAppRecord]] = defaultdict(list)
    for record in sorted(records, key=lambda item: (item.driver, item.session_time_seconds)):
        grouped[record.driver].append(record)
    return grouped


def _lap_at_time(laps_by_number: dict[int, LapRecord], session_time: float) -> LapRecord | None:
    for lap in sorted(laps_by_number.values(), key=lambda item: item.lap_number):
        start = lap.lap_start_time_seconds
        end = lap.lap_end_time_seconds
        if start is None:
            continue
        if end is None:
            end = start + (lap.lap_time_seconds or 0)
        if start <= session_time < end:
            return lap
    return None


def _positioned_telemetry_by_driver(
    samples: list[TelemetrySample],
) -> dict[str, list[TelemetrySample]]:
    grouped: dict[str, list[TelemetrySample]] = defaultdict(list)
    for sample in samples:
        if sample.session_time_seconds is None or sample.x is None or sample.y is None:
            continue
        grouped[sample.driver].append(sample)
    return {
        driver: sorted(driver_samples, key=lambda item: item.session_time_seconds or 0)
        for driver, driver_samples in grouped.items()
    }


def _telemetry_laps_by_driver(
    samples: list[TelemetrySample],
) -> dict[str, dict[int, list[TelemetrySample]]]:
    grouped: dict[str, dict[int, list[TelemetrySample]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for sample in samples:
        if sample.session_time_seconds is None:
            continue
        grouped[sample.driver][sample.lap_number].append(sample)
    return {
        driver: {
            lap_number: sorted(lap_samples, key=lambda sample: sample.distance_m)
            for lap_number, lap_samples in laps.items()
        }
        for driver, laps in grouped.items()
    }


def _driver_color(driver: str, color: str | None) -> str:
    return color or deterministic_fallback_color(driver)


def _playback_driver_colors(dataset: SessionDataset) -> dict[str, str]:
    colors: dict[str, str] = {}
    drivers_by_code = {driver.abbreviation: driver for driver in dataset.drivers}
    for driver_code, driver in drivers_by_code.items():
        style = dataset.style.driver_colors.get(driver_code)
        color = _normalized_hex_color(style.color) if style is not None else None
        if color is not None:
            colors[driver_code] = color
            continue

        session_team_color = _normalized_hex_color(driver.team_color)
        if session_team_color is not None:
            colors[driver_code] = session_team_color
            continue

        team_name = driver.team_name
        team_style = dataset.style.team_colors.get(team_name or "") if team_name else None
        team_color = _normalized_hex_color(team_style.color) if team_style is not None else None
        if team_color is not None:
            colors[driver_code] = team_color
            continue

        colors[driver_code] = deterministic_fallback_color(driver_code)
    return colors
