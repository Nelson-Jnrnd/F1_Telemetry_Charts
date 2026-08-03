"""Normalized data models consumed by framework recipes."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ALL_DRIVER_CODES = {"*", "ALL"}


def requests_all_drivers(driver_codes: list[str]) -> bool:
    return any(driver.upper() in ALL_DRIVER_CODES for driver in driver_codes)


class SessionQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    season: int = Field(ge=1950)
    event: str = Field(min_length=1)
    session: str = Field(min_length=1)
    drivers: list[str] = Field(min_length=1)


class SessionMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    season: int
    event: str
    session: str
    round_number: int | None = None
    official_name: str | None = None


class DriverMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    driver_number: str | None = None
    abbreviation: str = Field(min_length=1)
    full_name: str | None = None
    team_name: str | None = None
    team_color: str | None = None


class StyleColor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    color: str = Field(min_length=1)
    source: str = Field(min_length=1)
    label: str | None = None
    fallback: bool = False


class SessionStyleMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    driver_colors: dict[str, StyleColor] = Field(default_factory=dict)
    team_colors: dict[str, StyleColor] = Field(default_factory=dict)
    compound_colors: dict[str, StyleColor] = Field(default_factory=dict)


class LapRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    driver: str = Field(min_length=1)
    lap_number: int = Field(ge=1)
    lap_start_time_seconds: float | None = Field(default=None, ge=0)
    lap_end_time_seconds: float | None = Field(default=None, ge=0)
    lap_time_seconds: float | None = None
    compound: str | None = None
    stint: int | None = None
    position: int | None = None
    is_pit_in_lap: bool = False
    is_pit_out_lap: bool = False
    pit_in_time_seconds: float | None = Field(default=None, ge=0)
    pit_out_time_seconds: float | None = Field(default=None, ge=0)
    is_deleted: bool = False
    is_generated: bool = False
    is_accurate: bool | None = None
    sector_1_time_seconds: float | None = None
    sector_2_time_seconds: float | None = None
    sector_3_time_seconds: float | None = None
    track_status: str | None = None


class TelemetrySample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    driver: str = Field(min_length=1)
    lap_number: int = Field(ge=1)
    distance_m: float = Field(ge=0)
    session_time_seconds: float | None = Field(default=None, ge=0)
    x: float | None = None
    y: float | None = None
    z: float | None = None
    position_status: str | None = None
    speed_kph: float | None = None
    throttle_percent: float | None = Field(default=None, ge=0, le=100)
    brake: bool | None = None
    gear: int | None = None


class TimingStreamRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    driver: str = Field(min_length=1)
    session_time_seconds: float = Field(ge=0)
    position: int | None = Field(default=None, ge=1)
    gap_to_leader_seconds: float | None = None
    interval_to_ahead_seconds: float | None = None
    gap_to_leader_laps: int | None = Field(default=None, ge=1)
    interval_to_ahead_laps: int | None = Field(default=None, ge=1)
    source: str = Field(default="fastf1_timing_data", min_length=1)
    gap_parse_status: Literal["parsed", "leader", "missing", "unparseable"] = "missing"
    interval_parse_status: Literal["parsed", "leader", "missing", "unparseable"] = "missing"


class TimingAppRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    driver: str = Field(min_length=1)
    session_time_seconds: float = Field(ge=0)
    lap_number: int | None = Field(default=None, ge=0)
    lap_time_seconds: float | None = Field(default=None, ge=0)
    stint: int | None = Field(default=None, ge=0)
    total_laps: float | None = Field(default=None, ge=0)
    compound: str | None = None
    start_laps: float | None = Field(default=None, ge=0)
    source: str = Field(default="fastf1_timing_app_data", min_length=1)


class TrackGeometryPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    distance_m: float = Field(ge=0)
    x: float
    y: float


class TrackGeometryBounds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum: float
    maximum: float


class TrackGeometry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    source_driver: str = Field(min_length=1)
    source_lap: int = Field(ge=1)
    points: list[TrackGeometryPoint] = Field(min_length=2)
    original_sample_count: int = Field(ge=2)
    point_count: int = Field(ge=2)
    downsampled: bool = False
    distance_bounds: TrackGeometryBounds
    x_bounds: TrackGeometryBounds
    y_bounds: TrackGeometryBounds


class CircuitCorner(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int = Field(ge=1)
    letter: str | None = None
    label: str = Field(min_length=1)
    x: float
    y: float
    angle_degrees: float | None = None
    distance_m: float | None = Field(default=None, ge=0)


class CircuitInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    rotation_degrees: float | None = None
    corners: list[CircuitCorner] = Field(default_factory=list)


class WeatherSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_seconds: float = Field(ge=0)
    air_temp_c: float | None = None
    track_temp_c: float | None = None
    humidity_percent: float | None = Field(default=None, ge=0, le=100)
    rainfall: bool | None = None


class MissingDataField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: Literal["metadata", "drivers", "laps", "telemetry", "weather"]
    reason: str = Field(min_length=1)


class SourceProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    cache_status: Literal["fixture", "hit", "miss", "cache-only", "unavailable"]
    source_path: Path | None = None
    fetched_from_network: bool = False


class SessionDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: SessionMetadata
    drivers: list[DriverMetadata]
    laps: list[LapRecord]
    telemetry: list[TelemetrySample] = Field(default_factory=list)
    timing: list[TimingStreamRecord] = Field(default_factory=list)
    timing_app: list[TimingAppRecord] = Field(default_factory=list)
    weather: list[WeatherSample] = Field(default_factory=list)
    style: SessionStyleMetadata = Field(default_factory=SessionStyleMetadata)
    track_geometry: TrackGeometry | None = None
    circuit_info: CircuitInfo | None = None
    provenance: SourceProvenance
    missing_data: list[MissingDataField] = Field(default_factory=list)

    def filter_drivers(self, driver_codes: list[str]) -> "SessionDataset":
        if requests_all_drivers(driver_codes):
            return self.model_copy(deep=True)
        requested = set(driver_codes)
        return self.model_copy(
            update={
                "drivers": [
                    driver for driver in self.drivers if driver.abbreviation in requested
                ],
                "laps": [lap for lap in self.laps if lap.driver in requested],
                "telemetry": [
                    sample for sample in self.telemetry if sample.driver in requested
                ],
                "timing": [
                    record for record in self.timing if record.driver in requested
                ],
                "timing_app": [
                    record for record in self.timing_app if record.driver in requested
                ],
            },
            deep=True,
        )
