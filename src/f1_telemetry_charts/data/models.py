"""Normalized data models consumed by framework recipes."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


class LapRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    driver: str = Field(min_length=1)
    lap_number: int = Field(ge=1)
    lap_time_seconds: float | None = None
    compound: str | None = None
    stint: int | None = None
    position: int | None = None
    is_pit_in_lap: bool = False
    is_pit_out_lap: bool = False


class TelemetrySample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    driver: str = Field(min_length=1)
    lap_number: int = Field(ge=1)
    distance_m: float = Field(ge=0)
    speed_kph: float | None = None
    throttle_percent: float | None = Field(default=None, ge=0, le=100)
    brake: bool | None = None
    gear: int | None = None


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
    weather: list[WeatherSample] = Field(default_factory=list)
    provenance: SourceProvenance
    missing_data: list[MissingDataField] = Field(default_factory=list)

    def filter_drivers(self, driver_codes: list[str]) -> "SessionDataset":
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
            },
            deep=True,
        )
