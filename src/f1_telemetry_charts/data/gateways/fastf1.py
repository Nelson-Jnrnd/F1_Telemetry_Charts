"""FastF1-backed session gateway.

FastF1 is imported lazily inside the gateway so framework models, recipes, and
tests do not depend on FastF1 unless this gateway is used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from f1_telemetry_charts.data.gateways.base import DataGatewayError
from f1_telemetry_charts.data.models import (
    DriverMetadata,
    LapRecord,
    MissingDataField,
    SessionDataset,
    SessionMetadata,
    SessionQuery,
    SourceProvenance,
    WeatherSample,
)


class FastF1SessionGateway:
    def __init__(self, cache_dir: str | Path, *, cache_only: bool = False):
        self.cache_dir = Path(cache_dir)
        self.cache_only = cache_only

    def load_session(self, query: SessionQuery) -> SessionDataset:
        try:
            import fastf1
        except ImportError as exc:
            raise DataGatewayError(
                "FastF1 is not installed. Install the FastF1 dependency before "
                "using FastF1SessionGateway."
            ) from exc

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        fastf1.Cache.enable_cache(str(self.cache_dir))

        try:
            session = fastf1.get_session(query.season, query.event, query.session)
            session.load(laps=True, telemetry=False, weather=True, messages=False)
        except Exception as exc:
            raise DataGatewayError(
                f"FastF1 could not load {query.season} {query.event} {query.session}: {exc}"
            ) from exc

        return _session_to_dataset(session=session, query=query, cache_only=self.cache_only)


def _session_to_dataset(
    *, session: Any, query: SessionQuery, cache_only: bool
) -> SessionDataset:
    laps = session.laps
    if query.drivers:
        laps = laps.pick_drivers(query.drivers)

    driver_rows = getattr(session, "results", None)
    drivers = _drivers_from_results(driver_rows, query.drivers)
    lap_records = _lap_records_from_laps(laps)
    weather = _weather_samples_from_session(session)
    missing_data = []
    if not weather:
        missing_data.append(
            MissingDataField(field="weather", reason="No weather samples available")
        )
    missing_data.append(
        MissingDataField(
            field="telemetry",
            reason="Telemetry loading is deferred to a later gateway slice",
        )
    )

    return SessionDataset(
        metadata=SessionMetadata(
            season=query.season,
            event=query.event,
            session=query.session,
            round_number=getattr(getattr(session, "event", None), "RoundNumber", None),
            official_name=str(getattr(session, "name", query.session)),
        ),
        drivers=drivers,
        laps=lap_records,
        telemetry=[],
        weather=weather,
        provenance=SourceProvenance(
            provider="FastF1",
            cache_status="cache-only" if cache_only else "hit",
            source_path=None,
            fetched_from_network=not cache_only,
        ),
        missing_data=missing_data,
    )


def _drivers_from_results(results: Any, fallback_drivers: list[str]) -> list[DriverMetadata]:
    drivers: list[DriverMetadata] = []
    if results is not None:
        for _, row in results.iterrows():
            abbreviation = _string_or_none(row.get("Abbreviation"))
            if abbreviation and abbreviation in fallback_drivers:
                drivers.append(
                    DriverMetadata(
                        driver_number=_string_or_none(row.get("DriverNumber")),
                        abbreviation=abbreviation,
                        full_name=_string_or_none(row.get("FullName")),
                        team_name=_string_or_none(row.get("TeamName")),
                        team_color=_string_or_none(row.get("TeamColor")),
                    )
                )
    if drivers:
        return drivers
    return [DriverMetadata(abbreviation=driver) for driver in fallback_drivers]


def _lap_records_from_laps(laps: Any) -> list[LapRecord]:
    records: list[LapRecord] = []
    for _, row in laps.iterrows():
        lap_time = row.get("LapTime")
        lap_time_seconds = (
            float(lap_time.total_seconds()) if hasattr(lap_time, "total_seconds") else None
        )
        records.append(
            LapRecord(
                driver=str(row.get("Driver")),
                lap_number=int(row.get("LapNumber")),
                lap_time_seconds=lap_time_seconds,
                compound=_string_or_none(row.get("Compound")),
                stint=_int_or_none(row.get("Stint")),
                position=_int_or_none(row.get("Position")),
                is_pit_in_lap=row.get("PitInTime") is not None,
                is_pit_out_lap=row.get("PitOutTime") is not None,
            )
        )
    return records


def _weather_samples_from_session(session: Any) -> list[WeatherSample]:
    weather_data = getattr(session, "weather_data", None)
    if weather_data is None:
        return []

    samples: list[WeatherSample] = []
    for _, row in weather_data.iterrows():
        time_value = row.get("Time")
        time_seconds = (
            float(time_value.total_seconds()) if hasattr(time_value, "total_seconds") else 0
        )
        samples.append(
            WeatherSample(
                time_seconds=time_seconds,
                air_temp_c=_float_or_none(row.get("AirTemp")),
                track_temp_c=_float_or_none(row.get("TrackTemp")),
                humidity_percent=_float_or_none(row.get("Humidity")),
                rainfall=_bool_or_none(row.get("Rainfall")),
            )
        )
    return samples


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text and text.lower() != "nan" else None


def _int_or_none(value: Any) -> int | None:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)
